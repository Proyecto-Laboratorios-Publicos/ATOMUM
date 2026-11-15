# security/port_scanner/core.py
"""
Motor asíncrono de escaneo de puertos TCP con Banner Grabbing y Mapeo de Vulnerabilidades.
"""
import asyncio
import socket
from typing import Callable, Iterable, List, Tuple, Optional

PortResult = Tuple[str, int, bool]
BannerResult = Tuple[str, int, bool, str, str]  # Añadimos la columna de vulnerabilidades
OnOpenCallback = Callable[[BannerResult], None]
OnCloseCallback = Callable[[PortResult], None]
OnErrorCallback = Callable[[str, Exception], None]

def _check_known_vulnerabilities(port: int, banner: str) -> str:
    """Heurística rápida para asociar banners/versiones a CVEs o riesgos conocidos."""
    banner_lower = banner.lower()
    vulns = []

    # Ejemplo histórico para la versión de OpenSSH que suele devolver scanme.nmap.org
    if "openssh_6.6.1" in banner_lower:
        vulns.append("CVE-2015-5600 (Keyboard-Interactive Brute Force)")
        vulns.append("CVE-2016-0777 (Roaming Information Leak)")
    
    if port == 21 and ("ftp" in banner_lower or "vsftpd 2.3.4" in banner_lower):
        vulns.append("CVE-2011-2523 (vsftpd 2.3.4 Backdoor)")

    if port == 80 or port == 443:
        if "apache" in banner_lower:
            vulns.append("Revisar CVEs específicos de versión Apache")
        elif "nginx" in banner_lower:
            vulns.append("Revisar directivas de configuración Nginx")

    if not vulns:
        return "Sin vulnerabilidades críticas conocidas en base estática"
    
    return " | ".join(vulns)

async def _grab_banner(host: str, port: int, timeout: float) -> Tuple[str, str]:
    """Captura el banner e identifica vulnerabilidades asociadas."""
    banner = ""
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )
        try:
            if port in (80, 8080):
                writer.write(b"HEAD / HTTP/1.0\r\nHost: " + host.encode() + b"\r\n\r\n")
                await writer.drain()
            
            data = await asyncio.wait_for(reader.read(512), timeout=1.0)
            if data:
                banner = data.decode("utf-8", errors="ignore").strip().split("\n")[0]
        except Exception:
            pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
    except Exception:
        pass
    
    final_banner = banner if banner else "Servicio Activo (Sin banner explícito)"
    vulns = _check_known_vulnerabilities(port, final_banner)
    return final_banner, vulns

async def _probe(
    host: str,
    port: int,
    timeout: float,
    *,
    on_open: Optional[OnOpenCallback] = None,
    on_close: Optional[OnCloseCallback] = None,
    on_error: Optional[OnErrorCallback] = None
) -> None:
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass

        banner, vulns = await _grab_banner(host, port, timeout)

        if on_open:
            on_open((host, port, True, banner, vulns))

    except asyncio.TimeoutError as exc:
        if on_close:
            on_close((host, port, False))
    except (ConnectionRefusedError, OSError) as exc:
        if on_close:
            on_close((host, port, False))
    except Exception as exc:
        if on_close:
            on_close((host, port, False))

class PortScanner:
    def __init__(
        self,
        concurrency: int = 300,
        timeout: float = 2.0,
        on_open: Optional[OnOpenCallback] = None,
        on_close: Optional[OnCloseCallback] = None,
        on_error: Optional[OnErrorCallback] = None
    ):
        self.concurrency = max(1, concurrency)
        self.timeout = timeout
        self.on_open = on_open
        self.on_close = on_close
        self.on_error = on_error
        self._semaphore = asyncio.Semaphore(self.concurrency)
        self._results: List[BannerResult] = []

    async def _bounded_probe(self, host: str, port: int) -> None:
        async with self._semaphore:
            def _local_on_open(res: BannerResult):
                self._results.append(res)
                if self.on_open:
                    self.on_open(res)

            def _local_on_close(res: PortResult):
                if self.on_close:
                    self.on_close(res)

            await _probe(
                host,
                port,
                self.timeout,
                on_open=_local_on_open,
                on_close=_local_on_close,
                on_error=self.on_error
            )

    async def scan_ports(self, host: str, ports: Iterable[int]) -> List[BannerResult]:
        self._results.clear()
        tasks = [self._bounded_probe(host, port) for port in ports]
        await asyncio.gather(*tasks)
        return self._results

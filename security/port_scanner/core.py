# security/port_scanner/core.py
"""
Motor asíncrono de escaneo de puertos TCP con Banner Grabbing de doble pasada,
mapeo extendido de servicios y correlación de CVEs conocidos.
"""
import asyncio
import socket
from typing import Callable, Iterable, List, Tuple, Optional

PortResult = Tuple[str, int, bool]
BannerResult = Tuple[str, int, bool, str, str, str]  # (host, port, is_open, banner, service, vulns)
OnOpenCallback = Callable[[BannerResult], None]
OnCloseCallback = Callable[[PortResult], None]
OnErrorCallback = Callable[[str, Exception], None]

def _identify_service(port: int, banner: str) -> str:
    """Mapea puertos comunes y analiza banners para sugerir el servicio real."""
    banner_lower = banner.lower()
    
    if port == 21 or "ftp" in banner_lower: return "FTP"
    if port == 22 or "ssh" in banner_lower: return "SSH"
    if port == 25 or "smtp" in banner_lower: return "SMTP"
    if port == 53 or "dns" in banner_lower: return "DNS"
    if port in (80, 8080, 8000) or "http" in banner_lower: return "HTTP"
    if port == 443 or "https" in banner_lower: return "HTTPS"
    if port == 3306 or "mysql" in banner_lower: return "MySQL"
    if port == 5432 or "postgres" in banner_lower: return "PostgreSQL"
    if port == 6379 or "redis" in banner_lower: return "Redis"
    if port == 9929 or "nmap" in banner_lower: return "Nmap Scripting / Ping"
    
    return "Servicio Genérico / TCP"

def _check_known_vulnerabilities(port: int, banner: str) -> str:
    """Heurística rápida para asociar banners/versiones a CVEs o riesgos conocidos."""
    banner_lower = banner.lower()
    vulns = []

    if "openssh_6.6.1" in banner_lower:
        vulns.append("CVE-2015-5600 (Keyboard-Interactive Brute Force)")
        vulns.append("CVE-2016-0777 (Roaming Information Leak)")
    
    if port == 21 and ("ftp" in banner_lower or "vsftpd 2.3.4" in banner_lower):
        vulns.append("CVE-2011-2523 (vsftpd 2.3.4 Backdoor)")

    if port in (80, 443, 8080):
        if "apache" in banner_lower:
            vulns.append("Revisar CVEs específicos de versión Apache")
        elif "nginx" in banner_lower:
            vulns.append("Revisar directivas de configuración Nginx")

    if not vulns:
        return "Bajo Riesgo / Sin CVE crítico directo"
    
    return " | ".join(vulns)

async def _deep_grab_banner(host: str, port: int, timeout: float = 3.0) -> Tuple[str, str, str]:
    """Captura el banner de bienvenida y determina servicio y vulnerabilidades."""
    banner = ""
    for attempt in range(2):
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=timeout
            )
            try:
                if port in (80, 8080):
                    writer.write(b"HEAD / HTTP/1.0\r\nHost: " + host.encode() + b"\r\n\r\n")
                    await writer.drain()
                
                data = await asyncio.wait_for(reader.read(1024), timeout=timeout)
                if data:
                    banner = data.decode("utf-8", errors="ignore").strip().split("\n")[0]
                    if banner:
                        break
            except Exception:
                pass
            finally:
                writer.close()
                try:
                    await writer.wait_closed()
                except Exception:
                    pass
        except Exception:
            await asyncio.sleep(0.5)

        if banner:
            break

    final_banner = banner if banner else "Servicio Activo (Sin banner explícito)"
    service = _identify_service(port, final_banner)
    vulns = _check_known_vulnerabilities(port, final_banner)
    return final_banner, service, vulns

class PortScanner:
    def __init__(
        self,
        concurrency: int = 500,
        timeout: float = 1.5,
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
            is_open = False
            try:
                future = asyncio.open_connection(host, port)
                _, writer = await asyncio.wait_for(future, timeout=self.timeout)
                is_open = True
                writer.close()
                try:
                    await writer.wait_closed()
                except Exception:
                    pass
            except Exception:
                is_open = False

            if is_open:
                banner, service, vulns = await _deep_grab_banner(host, port)
                result: BannerResult = (host, port, True, banner, service, vulns)
                self._results.append(result)
                if self.on_open:
                    self.on_open(result)
            else:
                if self.on_close:
                    self.on_close((host, port, False))

    async def scan_ports(self, host: str, ports: Iterable[int]) -> List[BannerResult]:
        self._results.clear()
        tasks = [self._bounded_probe(host, port) for port in ports]
        await asyncio.gather(*tasks)
        return self._results

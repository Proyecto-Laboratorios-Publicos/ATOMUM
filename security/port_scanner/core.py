# security/port_scanner/core.py
"""
Motor asíncrono de escaneo de puertos TCP con detección de servicios,
banner grabbing adaptativo, soporte TLS, inferencia de SO y correlación de riesgos/CVEs.
"""

import asyncio
import re
import ssl
from typing import Callable, Iterable, List, Optional, Tuple

PortResult = Tuple[str, int, bool]
# (host, port, is_open, banner, service, os_guess, vulns)
BannerResult = Tuple[str, int, bool, str, str, str, str]
OnOpenCallback = Callable[[BannerResult], None]
OnCloseCallback = Callable[[PortResult], None]
OnErrorCallback = Callable[[str, Exception], None]

PORT_SERVICE_MAP = {
    21: "FTP",
    22: "SSH",
    23: "Telnet",
    25: "SMTP",
    53: "DNS",
    80: "HTTP",
    110: "POP3",
    143: "IMAP",
    443: "HTTPS",
    445: "SMB",
    1433: "MSSQL",
    3306: "MySQL",
    3389: "RDP",
    5432: "PostgreSQL",
    6379: "Redis",
    8000: "HTTP-Alt",
    8080: "HTTP-Proxy",
    8443: "HTTPS-Alt",
    9929: "Nmap Scripting / Ping",
    27017: "MongoDB",
}

TLS_PORTS = {443, 465, 636, 853, 993, 995, 8443}
HTTP_PORTS = {80, 443, 8000, 8080, 8443}


def _identify_service(port: int, banner: str) -> str:
    """Mapea puertos comunes y analiza banners para identificar el servicio."""
    banner_lower = banner.lower()

    if "ssh" in banner_lower:
        return "SSH"
    if "ftp" in banner_lower:
        return "FTP"
    if "smtp" in banner_lower or "esmtp" in banner_lower:
        return "SMTP"
    if "http/" in banner_lower or banner_lower.startswith("http"):
        return "HTTPS" if port in TLS_PORTS else "HTTP"
    if "mysql" in banner_lower or "mariadb" in banner_lower:
        return "MySQL / MariaDB"
    if "postgres" in banner_lower:
        return "PostgreSQL"
    if "redis" in banner_lower:
        return "Redis"
    if "mongodb" in banner_lower:
        return "MongoDB"
    if "rdp" in banner_lower or port == 3389:
        return "RDP"
    if "nmap" in banner_lower or port == 9929:
        return "Nmap Scripting / Ping"

    return PORT_SERVICE_MAP.get(port, "Servicio Genérico / TCP")


def _detect_os(banner: str, port: int) -> str:
    """Infiere de manera heurística el Sistema Operativo evitando falsos positivos."""
    banner_lower = banner.lower()

    if "ubuntu" in banner_lower:
        return "Linux (Ubuntu)"
    if "debian" in banner_lower:
        return "Linux (Debian)"
    if any(token in banner_lower for token in ("centos", "red hat", "rhel", "rocky", "alma")):
        return "Linux (RHEL/CentOS)"
    if re.search(r"\bel\d+\b", banner_lower):
        return "Linux (Enterprise Linux)"
    if any(token in banner_lower for token in ("win32", "win64", "windows", "microsoft", "iis")):
        return "Microsoft Windows"
    if "darwin" in banner_lower or "macos" in banner_lower:
        return "macOS / Darwin"
    if "freebsd" in banner_lower:
        return "FreeBSD"
    if "openssh" in banner_lower:
        return "Unix / Linux (OpenSSH)"

    if port in (3389, 445, 1433):
        return "Microsoft Windows (Inferencia por puerto)"
    if port in (22, 21, 5432, 6379):
        return "Unix / Linux / POSIX (Probable)"
    if port in (80, 443, 8080, 8443):
        return "Multiplataforma / Web Stack"

    return "Desconocido / No determinado"


def _check_known_vulnerabilities(port: int, banner: str) -> str:
    """Evalúa riesgos conocidos y versiones críticas a partir del banner."""
    banner_lower = banner.lower()
    vulns: List[str] = []

    if "openssh_6.6.1" in banner_lower:
        vulns.append("CVE-2015-5600 (Keyboard-Interactive Brute Force)")
        vulns.append("CVE-2016-0777 (Roaming Information Leak)")
    elif "openssh_7." in banner_lower or "openssh_8.0" in banner_lower:
        vulns.append("Verificar parches OpenSSH antiguos (enumeración/auth)")

    if port == 21 and ("vsftpd 2.3.4" in banner_lower or "ftp" in banner_lower):
        if "vsftpd 2.3.4" in banner_lower:
            vulns.append("CVE-2011-2523 (vsftpd 2.3.4 Backdoor - Crítico)")
        else:
            vulns.append("FTP sin cifrado detectado (riesgo de credenciales en claro)")

    if port == 23:
        vulns.append("Telnet expuesto sin cifrado (riesgo de intercepción de tráfico)")

    if port == 6379 and "redis" in banner_lower:
        vulns.append("Redis expuesto: verificar autenticación (requirepass) y bind")

    if port == 27017 and "mongodb" in banner_lower:
        vulns.append("MongoDB expuesto: verificar control de acceso y autenticación")

    if port in HTTP_PORTS:
        if "apache" in banner_lower:
            vulns.append("Revisar CVEs específicos de versión Apache y cabeceras de seguridad")
        elif "nginx" in banner_lower:
            vulns.append("Revisar versión Nginx, exposición de headers y configuración TLS")
        elif "certificado sin validar" in banner_lower or "autofirmado" in banner_lower:
            vulns.append("Revisar validez/confianza del certificado TLS en el objetivo")

    if not vulns:
        return "Bajo Riesgo / Sin CVE crítico directo"
    return " | ".join(vulns)


async def _grab_banner_from_stream(
    host: str,
    port: int,
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    timeout: float,
    tls_info: str = "",
) -> str:
    """Intenta leer un banner inicial y, si es necesario, envía un probe acotado."""
    read_timeout = min(timeout, 1.5)

    try:
        data = await asyncio.wait_for(reader.read(1024), timeout=read_timeout)
        if data:
            first_line = data.decode("utf-8", errors="ignore").strip().splitlines()
            if first_line and first_line[0].strip():
                banner = first_line[0].strip()[:240]
                return f"{banner} [{tls_info}]" if tls_info else banner
    except (asyncio.TimeoutError, ConnectionResetError, OSError):
        pass

    probe: Optional[bytes] = None
    if port in HTTP_PORTS:
        probe = (
            f"HEAD / HTTP/1.1\r\nHost: {host}\r\nUser-Agent: ATOMUM-Scanner/2.0\r\nConnection: close\r\n\r\n"
        ).encode("utf-8", errors="ignore")
    elif port in (25, 110, 143):
        probe = b"\r\n"

    if probe:
        try:
            writer.write(probe)
            await writer.drain()
            data = await asyncio.wait_for(reader.read(1024), timeout=read_timeout)
            if data:
                lines = [ln.strip() for ln in data.decode("utf-8", errors="ignore").splitlines() if ln.strip()]
                if lines:
                    server_hdr = next((ln for ln in lines if ln.lower().startswith("server:")), None)
                    summary = server_hdr or lines[0]
                    banner = summary[:240]
                    return f"{banner} [{tls_info}]" if tls_info else banner
        except (asyncio.TimeoutError, ConnectionResetError, OSError):
            pass

    if tls_info:
        return f"TLS Activo [{tls_info}]"
    return "Servicio Activo (Sin banner explícito)"


class PortScanner:
    def __init__(
        self,
        concurrency: int = 200,
        timeout: float = 1.5,
        on_open: Optional[OnOpenCallback] = None,
        on_close: Optional[OnCloseCallback] = None,
        on_error: Optional[OnErrorCallback] = None,
    ):
        self.concurrency = max(1, concurrency)
        self.timeout = max(0.2, timeout)
        self.on_open = on_open
        self.on_close = on_close
        self.on_error = on_error
        self._semaphore = asyncio.Semaphore(self.concurrency)
        self._results: List[BannerResult] = []

    def _build_ssl_context(self, verify: bool = True) -> ssl.SSLContext:
        ctx = ssl.create_default_context() if verify else ssl._create_unverified_context()
        ctx.check_hostname = verify
        ctx.verify_mode = ssl.CERT_REQUIRED if verify else ssl.CERT_NONE
        return ctx

    async def _connect_with_optional_tls(
        self, host: str, port: int
    ) -> Tuple[Optional[asyncio.StreamReader], Optional[asyncio.StreamWriter], str]:
        """Abre conexión TCP y negocia TLS si corresponde al puerto."""
        tls_label = ""
        if port in TLS_PORTS:
            for verify in (True, False):
                writer: Optional[asyncio.StreamWriter] = None
                try:
                    ssl_ctx = self._build_ssl_context(verify=verify)
                    reader, writer = await asyncio.wait_for(
                        asyncio.open_connection(host, port, ssl=ssl_ctx, server_hostname=host),
                        timeout=self.timeout,
                    )
                    ssl_obj = writer.get_extra_info("ssl_object")
                    proto = ssl_obj.version() if ssl_obj and ssl_obj.version() else "TLS"
                    cipher_info = ssl_obj.cipher() if ssl_obj else None
                    cipher_name = cipher_info[0] if cipher_info else ""
                    cert_note = "" if verify else ", cert no verificado"
                    tls_label = f"{proto}{f' / {cipher_name}' if cipher_name else ''}{cert_note}"
                    return reader, writer, tls_label
                except ssl.SSLCertVerificationError:
                    if writer:
                        writer.close()
                        await writer.wait_closed()
                    continue
                except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
                    if writer:
                        writer.close()
                        await writer.wait_closed()
                    return None, None, ""
                except Exception as exc:
                    if writer:
                        writer.close()
                        await writer.wait_closed()
                    if self.on_error:
                        self.on_error(f"{host}:{port}", exc)
                    return None, None, ""

        writer = None
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=self.timeout,
            )
            return reader, writer, ""
        except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
            if writer:
                writer.close()
                await writer.wait_closed()
            return None, None, ""
        except Exception as exc:
            if writer:
                writer.close()
                await writer.wait_closed()
            if self.on_error:
                self.on_error(f"{host}:{port}", exc)
            return None, None, ""

    async def _bounded_probe(self, host: str, port: int) -> None:
        async with self._semaphore:
            reader, writer, tls_info = await self._connect_with_optional_tls(host, port)
            if reader is None or writer is None:
                if self.on_close:
                    self.on_close((host, port, False))
                return

            try:
                banner = await _grab_banner_from_stream(
                    host=host,
                    port=port,
                    reader=reader,
                    writer=writer,
                    timeout=self.timeout,
                    tls_info=tls_info,
                )
                service = _identify_service(port, banner)
                os_guess = _detect_os(banner, port)
                vulns = _check_known_vulnerabilities(port, banner)

                result: BannerResult = (host, port, True, banner, service, os_guess, vulns)
                self._results.append(result)
                if self.on_open:
                    self.on_open(result)
            finally:
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass

    async def scan_ports(self, host: str, ports: Iterable[int]) -> List[BannerResult]:
        self._results.clear()
        tasks = [self._bounded_probe(host, port) for port in ports]
        await asyncio.gather(*tasks)
        return self._results

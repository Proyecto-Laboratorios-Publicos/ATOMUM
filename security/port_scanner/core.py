from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from security.cve_cbom import (
    CBOMAnalyzer,
    OfflineCPERepository,
    enrich_service_finding,
)

PortResult = Tuple[str, int, bool, Optional[str]]
BannerResult = Tuple[str, int, bool, Optional[str], str, str, str]

COMMON_SERVICE_MAP = {
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
    27017: "MongoDB",
}


def _find_cpe_database() -> Optional[Path]:
    """Busca cpe_database.json en ubicaciones esperadas sin fallar si no existe."""
    here = Path(__file__).resolve()
    candidates = [
        here.parent.parent / "cpe_database.json",          # security/cpe_database.json
        here.parent.parent.parent / "cpe_database.json",   # <repo>/cpe_database.json
        here.parent.parent.parent / "data" / "cpe_database.json",
        Path.cwd() / "security" / "cpe_database.json",
        Path.cwd() / "cpe_database.json",
    ]
    for path in candidates:
        if path.is_file():
            return path
    return None


def _guess_os_and_service(port: int, banner: Optional[str]) -> Tuple[str, str]:
    """Estima servicio y posible sistema operativo a partir del puerto y banner."""
    service = COMMON_SERVICE_MAP.get(port, f"TCP/{port}")
    banner_text = (banner or "").strip()
    banner_lower = banner_text.lower()
    os_guess = "Desconocido"

    if "ubuntu" in banner_lower:
        os_guess = "Linux (Ubuntu)"
    elif "debian" in banner_lower:
        os_guess = "Linux (Debian)"
    elif "centos" in banner_lower or "red hat" in banner_lower or "rhel" in banner_lower:
        os_guess = "Linux (RHEL/CentOS)"
    elif "alpine" in banner_lower:
        os_guess = "Linux (Alpine)"
    elif "linux" in banner_lower or "openssh" in banner_lower:
        os_guess = "Linux"
    elif "windows" in banner_lower or "microsoft" in banner_lower or "iis" in banner_lower:
        os_guess = "Windows"
    elif "freebsd" in banner_lower:
        os_guess = "FreeBSD"

    if banner_text:
        first_token = banner_text.split()[0]
        if "/" in first_token and port in COMMON_SERVICE_MAP:
            service = f"{service} ({first_token})"

    return service, os_guess


def _check_known_vulnerabilities(port: int, banner: Optional[str]) -> str:
    """Heurística rápida de riesgos/CVEs conocidos por puerto y banner."""
    findings: List[str] = []
    b = (banner or "").lower()

    if port == 21:
        findings.append("Servicio FTP (riesgo de tráfico/credenciales en claro si no usa FTPS/SFTP)")
    elif port == 23:
        findings.append("Servicio Telnet sin cifrado (alto riesgo de intercepción)")
    elif port == 445:
        findings.append("SMB expuesto (verificar segmentación, SMBv1 y parches críticos)")
    elif port == 3389:
        findings.append("RDP expuesto (verificar MFA, NLA y restricción de origen)")
    elif port == 6379:
        findings.append("Redis expuesto (verificar autenticación y bind a red privada)")
    elif port == 27017:
        findings.append("MongoDB expuesto (verificar autenticación y acceso restringido)")

    if "vsftpd 2.3.4" in b:
        findings.append("CVE-2011-2523 (vsftpd 2.3.4 backdoor)")
    if "openssh" in b:
        for old_ver in ("6.", "7.0", "7.1", "7.2", "7.3", "7.4", "7.5", "7.6", "7.7"):
            if f"openssh_{old_ver}" in b or f"openssh {old_ver}" in b:
                findings.append(f"OpenSSH {old_ver} desactualizado (revisar CVEs aplicables)")
                break
    if "apache/2.2" in b or "apache/2.4.49" in b or "apache/2.4.50" in b:
        findings.append("Versión de Apache con historial de CVEs relevantes (verificar actualización)")

    return " | ".join(findings) if findings else "Sin CVE crítico directo en heurística base"


class PortScanner:
    """Escáner TCP asíncrono con banner grabbing y correlación opcional CPE/CVE."""

    def __init__(
        self,
        concurrency: int = 150,
        timeout: float = 1.5,
        banner_timeout: float = 1.0,
        on_open: Optional[Callable[[BannerResult], None]] = None,
        on_close: Optional[Callable[[PortResult], None]] = None,
        cpe_db_path: Optional[str | Path] = None,
    ) -> None:
        self.concurrency = max(1, concurrency)
        self.timeout = max(0.2, timeout)
        self.banner_timeout = max(0.1, banner_timeout)
        self.on_open = on_open
        self.on_close = on_close
        self.semaphore = asyncio.Semaphore(self.concurrency)
        self._crypto_analyzer = CBOMAnalyzer()
        self._cpe_repo: Optional[OfflineCPERepository] = self._load_cpe_repo(cpe_db_path)

    def _load_cpe_repo(self, cpe_db_path: Optional[str | Path]) -> Optional[OfflineCPERepository]:
        target_path = Path(cpe_db_path) if cpe_db_path else _find_cpe_database()
        if not target_path:
            return None
        try:
            return OfflineCPERepository.from_json_file(target_path)
        except Exception:
            return None

    async def _grab_banner(
        self,
        host: str,
        port: int,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> Optional[str]:
        try:
            data = await asyncio.wait_for(reader.read(256), timeout=self.banner_timeout)
            if data:
                lines = [
                    ln.strip()
                    for ln in data.decode("utf-8", errors="replace").splitlines()
                    if ln.strip()
                ]
                if lines:
                    return lines[0][:240]
        except Exception:
            pass

        if port in {80, 443, 8000, 8080, 8443}:
            try:
                probe = (
                    f"HEAD / HTTP/1.1\r\nHost: {host}\r\n"
                    f"User-Agent: ATOMUM-Scanner/2.0\r\nConnection: close\r\n\r\n"
                ).encode("utf-8", errors="ignore")
                writer.write(probe)
                await writer.drain()
                data = await asyncio.wait_for(reader.read(512), timeout=self.banner_timeout)
                if data:
                    lines = [
                        ln.strip()
                        for ln in data.decode("utf-8", errors="replace").splitlines()
                        if ln.strip()
                    ]
                    if lines:
                        server_hdr = next(
                            (ln for ln in lines if ln.lower().startswith("server:")),
                            None,
                        )
                        return (server_hdr or lines[0])[:240]
            except Exception:
                pass

        return None

    def _enrich_vulns(self, host: str, port: int, banner: Optional[str], base_vulns: str) -> str:
        if not banner or self._cpe_repo is None:
            return base_vulns

        try:
            enriched = enrich_service_finding(
                target=host,
                port=port,
                banner=banner,
                repository=self._cpe_repo,
                crypto_analyzer=self._crypto_analyzer,
                observed_crypto=None,
            )
            cves: List[str] = enriched.get("cves") or []
            matches = enriched.get("cpe_matches") or []

            parts: List[str] = []
            if "Sin CVE crítico directo" not in base_vulns:
                parts.append(base_vulns)

            if cves:
                new_cves = [c for c in cves if c not in base_vulns]
                if new_cves:
                    parts.append(f"CVEs (CPE): {', '.join(new_cves[:8])}")
            elif matches:
                top_match = matches[0]
                if top_match.cpe_uri and top_match.cpe_uri not in base_vulns:
                    parts.append(f"CPE: {top_match.cpe_uri}")

            return " | ".join(parts) if parts else base_vulns
        except Exception:
            return base_vulns

    async def _probe_port(self, host: str, port: int) -> None:
        async with self.semaphore:
            writer: Optional[asyncio.StreamWriter] = None
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(host=host, port=port),
                    timeout=self.timeout,
                )
                banner = await self._grab_banner(host=host, port=port, reader=reader, writer=writer)
                service, os_guess = _guess_os_and_service(port=port, banner=banner)
                base_vulns = _check_known_vulnerabilities(port=port, banner=banner)
                vulns = self._enrich_vulns(host=host, port=port, banner=banner, base_vulns=base_vulns)

                if self.on_open is not None:
                    result: BannerResult = (
                        host,
                        port,
                        True,
                        banner,
                        service,
                        os_guess,
                        vulns,
                    )
                    self.on_open(result)
            except Exception:
                if self.on_close is not None:
                    closed_result: PortResult = (host, port, False, None)
                    self.on_close(closed_result)
            finally:
                if writer is not None:
                    writer.close()
                    try:
                        await writer.wait_closed()
                    except Exception:
                        pass

    async def scan_ports(self, host: str, ports: List[int]) -> None:
        unique_ports = list(dict.fromkeys(ports))
        if not unique_ports:
            return
        tasks = [asyncio.create_task(self._probe_port(host=host, port=p)) for p in unique_ports]
        await asyncio.gather(*tasks, return_exceptions=True)

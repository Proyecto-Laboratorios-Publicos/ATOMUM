from __future__ import annotations

import asyncio
import ssl
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class PortState(str, Enum):
    CONFIRMED_OPEN = "confirmed_open"
    CLOSED = "closed"
    FILTERED_OR_AMBIGUOUS = "filtered_or_ambiguous"


@dataclass
class PortProbeResult:
    host: str
    port: int
    state: PortState
    latency_ms: float
    banner: Optional[str] = None
    evidence_confirmed: bool = False
    detail: str = ""
    extra: Dict[str, object] = field(default_factory=dict)


@dataclass
class ScanSummary:
    host: str
    confirmed_open: List[PortProbeResult]
    filtered_or_ambiguous_count: int
    closed_count: int
    edge_anomaly_detected: bool
    anomaly_reason: Optional[str] = None


TLS_PORTS = {443, 465, 636, 853, 993, 995, 8443}
HTTP_PORTS = {80, 443, 8000, 8080, 8443}


def _sanitize_banner(raw: str, max_len: int = 240) -> str:
    """Limpia caracteres de control y recorta el banner a una longitud segura."""
    cleaned = "".join(ch if ch.isprintable() else " " for ch in raw)
    return " ".join(cleaned.split())[:max_len]


class HardenedPortDetector:
    """Sonda TCP asíncrona orientada a reducir falsos positivos en CDNs, WAFs y redes filtradas."""

    def __init__(
        self,
        timeout: float = 1.5,
        banner_timeout: float = 1.0,
        max_concurrency: int = 15,
        per_probe_delay: float = 0.02,
        anomaly_open_threshold: int = 25,
        enable_active_probe: bool = True,
    ) -> None:
        self.timeout = max(0.2, timeout)
        self.banner_timeout = max(0.1, banner_timeout)
        self.semaphore = asyncio.Semaphore(max(1, max_concurrency))
        self.per_probe_delay = max(0.0, per_probe_delay)
        self.anomaly_open_threshold = max(1, anomaly_open_threshold)
        self.enable_active_probe = enable_active_probe

    def _build_ssl_context(self, verify: bool = True) -> ssl.SSLContext:
        ctx = ssl.create_default_context() if verify else ssl._create_unverified_context()
        ctx.check_hostname = verify
        ctx.verify_mode = ssl.CERT_REQUIRED if verify else ssl.CERT_NONE
        return ctx

    async def _close_writer(self, writer: Optional[asyncio.StreamWriter]) -> None:
        if writer is None:
            return
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass

    async def _open_stream(
        self, host: str, port: int
    ) -> tuple[Optional[asyncio.StreamReader], Optional[asyncio.StreamWriter], Dict[str, object]]:
        meta: Dict[str, object] = {}
        if port in TLS_PORTS:
            for verify in (True, False):
                writer: Optional[asyncio.StreamWriter] = None
                try:
                    ssl_ctx = self._build_ssl_context(verify=verify)
                    reader, writer = await asyncio.wait_for(
                        asyncio.open_connection(
                            host=host,
                            port=port,
                            ssl=ssl_ctx,
                            server_hostname=host,
                        ),
                        timeout=self.timeout,
                    )
                    ssl_obj = writer.get_extra_info("ssl_object")
                    if ssl_obj:
                        meta["tls_version"] = ssl_obj.version()
                        cipher_info = ssl_obj.cipher()
                        if cipher_info:
                            meta["cipher_suite"] = cipher_info[0]
                    meta["tls_cert_verified"] = verify
                    return reader, writer, meta
                except ssl.SSLCertVerificationError:
                    await self._close_writer(writer)
                    continue
                except Exception:
                    await self._close_writer(writer)
                    raise

        writer = None
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host=host, port=port),
                timeout=self.timeout,
            )
            return reader, writer, meta
        except Exception:
            await self._close_writer(writer)
            raise

    async def _read_banner_or_probe(
        self,
        host: str,
        port: int,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        meta: Dict[str, object],
    ) -> Optional[str]:
        try:
            data = await asyncio.wait_for(reader.read(256), timeout=self.banner_timeout)
            if data:
                lines = [ln.strip() for ln in data.decode("utf-8", errors="replace").splitlines() if ln.strip()]
                if lines:
                    meta["probe_mode"] = "passive"
                    return _sanitize_banner(lines[0])
        except (asyncio.TimeoutError, TimeoutError, OSError):
            pass

        if self.enable_active_probe and port in HTTP_PORTS:
            payload = (
                f"HEAD / HTTP/1.1\r\nHost: {host}\r\n"
                f"User-Agent: ATOMUM-Detector/2.0\r\nConnection: close\r\n\r\n"
            ).encode("utf-8", errors="ignore")
            try:
                writer.write(payload)
                await writer.drain()
                data = await asyncio.wait_for(reader.read(512), timeout=self.banner_timeout)
                if data:
                    lines = [ln.strip() for ln in data.decode("utf-8", errors="replace").splitlines() if ln.strip()]
                    if lines:
                        meta["probe_mode"] = "http_head"
                        server_hdr = next((ln for ln in lines if ln.lower().startswith("server:")), None)
                        return _sanitize_banner(server_hdr or lines[0])
            except (asyncio.TimeoutError, TimeoutError, OSError):
                pass

        if meta.get("tls_version"):
            meta["probe_mode"] = "tls_handshake"
            cert_status = "cert_ok" if meta.get("tls_cert_verified") else "cert_unverified"
            return _sanitize_banner(f"TLS {meta['tls_version']} ({cert_status})")

        return None

    async def probe_port(self, host: str, port: int) -> PortProbeResult:
        async with self.semaphore:
            if self.per_probe_delay > 0:
                await asyncio.sleep(self.per_probe_delay)

            start = time.perf_counter()
            writer: Optional[asyncio.StreamWriter] = None
            extra: Dict[str, object] = {}

            try:
                reader, writer, extra = await self._open_stream(host=host, port=port)
                latency_ms = round((time.perf_counter() - start) * 1000, 2)

                assert reader is not None and writer is not None
                banner_text = await self._read_banner_or_probe(
                    host=host,
                    port=port,
                    reader=reader,
                    writer=writer,
                    meta=extra,
                )

                evidence_confirmed = (
                    bool(banner_text)
                    or port in HTTP_PORTS
                    or bool(extra.get("tls_version"))
                )
                detail = (
                    f"Evidencia obtenida ({extra.get('probe_mode', 'tcp')})."
                    if banner_text
                    else "Conexión TCP completada sin banner inicial."
                )
                return PortProbeResult(
                    host=host,
                    port=port,
                    state=PortState.CONFIRMED_OPEN,
                    latency_ms=latency_ms,
                    banner=banner_text,
                    evidence_confirmed=evidence_confirmed,
                    detail=detail,
                    extra=extra,
                )
            except ConnectionRefusedError as exc:
                latency_ms = round((time.perf_counter() - start) * 1000, 2)
                return PortProbeResult(
                    host=host,
                    port=port,
                    state=PortState.CLOSED,
                    latency_ms=latency_ms,
                    evidence_confirmed=True,
                    detail=f"Rechazo explícito de conexión: {exc}",
                    extra=extra,
                )
            except (asyncio.TimeoutError, TimeoutError) as exc:
                latency_ms = round((time.perf_counter() - start) * 1000, 2)
                return PortProbeResult(
                    host=host,
                    port=port,
                    state=PortState.FILTERED_OR_AMBIGUOUS,
                    latency_ms=latency_ms,
                    evidence_confirmed=False,
                    detail=f"Timeout / sin respuesta concluyente: {exc or 'timeout'}",
                    extra=extra,
                )
            except OSError as exc:
                latency_ms = round((time.perf_counter() - start) * 1000, 2)
                return PortProbeResult(
                    host=host,
                    port=port,
                    state=PortState.FILTERED_OR_AMBIGUOUS,
                    latency_ms=latency_ms,
                    evidence_confirmed=False,
                    detail=f"Respuesta de red no concluyente (OS/filtrado): {exc}",
                    extra=extra,
                )
            finally:
                await self._close_writer(writer)

    async def scan_ports(self, host: str, ports: List[int]) -> ScanSummary:
        unique_ports = list(dict.fromkeys(ports))
        tasks = [self.probe_port(host=host, port=p) for p in unique_ports]
        results = await asyncio.gather(*tasks)

        confirmed_open = [r for r in results if r.state == PortState.CONFIRMED_OPEN]
        filtered_or_ambiguous = [r for r in results if r.state == PortState.FILTERED_OR_AMBIGUOUS]
        closed = [r for r in results if r.state == PortState.CLOSED]

        no_banner_open = sum(1 for r in confirmed_open if not r.banner)
        edge_anomaly = (
            len(confirmed_open) >= self.anomaly_open_threshold
            and no_banner_open >= int(len(confirmed_open) * 0.7)
        )
        anomaly_reason = None
        if edge_anomaly:
            anomaly_reason = (
                f"Posible comportamiento de CDN/WAF/borde o filtrado: {len(confirmed_open)} "
                f"puertos con conexión inicial y {no_banner_open} sin banner distintivo."
            )

        return ScanSummary(
            host=host,
            confirmed_open=confirmed_open,
            filtered_or_ambiguous_count=len(filtered_or_ambiguous),
            closed_count=len(closed),
            edge_anomaly_detected=edge_anomaly,
            anomaly_reason=anomaly_reason,
        )

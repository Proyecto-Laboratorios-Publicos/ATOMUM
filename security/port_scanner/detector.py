from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Dict, List, Optional, Tuple


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


class HardenedPortDetector:
    """Sonda TCP asíncrona orientada a reducir falsos positivos en CDNs, WAFs y redes filtradas."""

    def __init__(
        self,
        timeout: float = 1.5,
        banner_timeout: float = 1.0,
        max_concurrency: int = 15,
        per_probe_delay: float = 0.02,
        anomaly_open_threshold: int = 25,
    ) -> None:
        self.timeout = timeout
        self.banner_timeout = banner_timeout
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.per_probe_delay = per_probe_delay
        self.anomaly_open_threshold = anomaly_open_threshold

    async def probe_port(self, host: str, port: int) -> PortProbeResult:
        async with self.semaphore:
            if self.per_probe_delay > 0:
                await asyncio.sleep(self.per_probe_delay)

            start = time.perf_counter()
            writer: Optional[asyncio.StreamWriter] = None
            try:
                conn_coro = asyncio.open_connection(host=host, port=port)
                reader, writer = await asyncio.wait_for(conn_coro, timeout=self.timeout)
                latency_ms = round((time.perf_counter() - start) * 1000, 2)

                banner_text: Optional[str] = None
                try:
                    # Intento pasivo y acotado de lectura inicial de banner
                    data = await asyncio.wait_for(
                        reader.read(256), timeout=self.banner_timeout
                    )
                    if data:
                        banner_text = data.decode("utf-8", errors="replace").strip()
                except (asyncio.TimeoutError, OSError):
                    banner_text = None

                # Un puerto con banner o en puerto web/TLS estándar tiene mayor señal;
                # sin banner en puertos arbitrarios, queda marcado como conexión abierta sin banner.
                evidence_confirmed = bool(banner_text) or port in {80, 443, 8080, 8443}
                detail = (
                    "Banner capturado tras conexión TCP."
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
                )

            finally:
                if writer is not None:
                    try:
                        writer.close()
                        await writer.wait_closed()
                    except Exception:
                        pass

    async def scan_ports(self, host: str, ports: List[int]) -> ScanSummary:
        tasks = [self.probe_port(host=host, port=p) for p in ports]
        results = await asyncio.gather(*tasks)

        confirmed_open = [r for r in results if r.state == PortState.CONFIRMED_OPEN]
        filtered_or_ambiguous = [
            r for r in results if r.state == PortState.FILTERED_OR_AMBIGUOUS
        ]
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

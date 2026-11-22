from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from security.port_scanner.detector import (
    HardenedPortDetector,
    PortState,
)


class _DummyReader:
    def __init__(self, payload: bytes = b"", hang: bool = False) -> None:
        self._payload = payload
        self._hang = hang

    async def read(self, n: int = 256) -> bytes:
        if self._hang:
            await asyncio.sleep(5.0)
        return self._payload[:n]


class _DummyWriter:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        return None


class TestHardenedPortDetector:
    def test_confirmed_open_with_banner_sets_evidence_confirmed(self):
        detector = HardenedPortDetector(
            timeout=0.5,
            banner_timeout=0.2,
            max_concurrency=5,
            per_probe_delay=0.0,
        )
        writer = _DummyWriter()
        reader = _DummyReader(payload=b"SSH-2.0-OpenSSH_9.6\r\n")

        async def fake_open_connection(host: str, port: int):
            return reader, writer

        with patch("asyncio.open_connection", side_effect=fake_open_connection):
            res = asyncio.run(detector.probe_port("127.0.0.1", 22))

        assert res.state == PortState.CONFIRMED_OPEN
        assert res.banner == "SSH-2.0-OpenSSH_9.6"
        assert res.evidence_confirmed is True
        assert writer.closed is True

    def test_confirmed_open_without_banner_on_non_web_port_marks_unconfirmed_evidence(self):
        detector = HardenedPortDetector(
            timeout=0.5,
            banner_timeout=0.05,
            max_concurrency=5,
            per_probe_delay=0.0,
        )
        writer = _DummyWriter()
        reader = _DummyReader(payload=b"", hang=True)

        async def fake_open_connection(host: str, port: int):
            return reader, writer

        with patch("asyncio.open_connection", side_effect=fake_open_connection):
            res = asyncio.run(detector.probe_port("127.0.0.1", 12345))

        assert res.state == PortState.CONFIRMED_OPEN
        assert res.banner is None
        assert res.evidence_confirmed is False
        assert writer.closed is True

    def test_closed_on_connection_refused(self):
        detector = HardenedPortDetector(per_probe_delay=0.0)

        async def fake_open_connection(host: str, port: int):
            raise ConnectionRefusedError("Connection refused")

        with patch("asyncio.open_connection", side_effect=fake_open_connection):
            res = asyncio.run(detector.probe_port("127.0.0.1", 8081))

        assert res.state == PortState.CLOSED
        assert res.evidence_confirmed is True

    def test_filtered_or_ambiguous_on_timeout_and_oserror(self):
        detector = HardenedPortDetector(timeout=0.05, per_probe_delay=0.0)

        async def fake_timeout(host: str, port: int):
            await asyncio.sleep(1.0)
            return _DummyReader(), _DummyWriter()

        with patch("asyncio.open_connection", side_effect=fake_timeout):
            res_timeout = asyncio.run(detector.probe_port("198.51.100.10", 443))

        assert res_timeout.state == PortState.FILTERED_OR_AMBIGUOUS
        assert res_timeout.evidence_confirmed is False

        async def fake_oserror(host: str, port: int):
            raise OSError("No route to host")

        with patch("asyncio.open_connection", side_effect=fake_oserror):
            res_os = asyncio.run(detector.probe_port("198.51.100.10", 444))

        assert res_os.state == PortState.FILTERED_OR_AMBIGUOUS
        assert res_os.evidence_confirmed is False

    def test_scan_ports_detects_edge_or_cdn_anomaly_on_mass_no_banner_opens(self):
        detector = HardenedPortDetector(
            timeout=0.3,
            banner_timeout=0.05,
            max_concurrency=10,
            per_probe_delay=0.0,
            anomaly_open_threshold=10,
        )

        # Puertos 1000..1011 conectan sin banner (patrón típico de borde/WAF/CDN)
        # Puerto 1012 devuelve rechazo limpio (CLOSED)
        # Puerto 1013 da timeout (FILTERED_OR_AMBIGUOUS)
        async def fake_open_connection(host: str, port: int):
            if 1000 <= port <= 1011:
                return _DummyReader(payload=b""), _DummyWriter()
            if port == 1012:
                raise ConnectionRefusedError("refused")
            raise asyncio.TimeoutError()

        ports = list(range(1000, 1014))
        with patch("asyncio.open_connection", side_effect=fake_open_connection):
            summary = asyncio.run(detector.scan_ports("198.51.100.50", ports))

        assert len(summary.confirmed_open) == 12
        assert summary.closed_count == 1
        assert summary.filtered_or_ambiguous_count == 1
        assert summary.edge_anomaly_detected is True
        assert summary.anomaly_reason is not None
        assert "CDN/WAF/borde" in summary.anomaly_reason

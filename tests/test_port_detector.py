from __future__ import annotations

import asyncio
from unittest.mock import patch

from security.port_scanner.detector import (
    HardenedPortDetector,
    PortState,
    _sanitize_banner,
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
    def test_sanitize_banner_cleans_control_chars_and_truncates(self) -> None:
        raw = "SSH-2.0-OpenSSH_9.6\x00\x07\r\n   Ubuntu-3ubuntu0.6   "
        assert _sanitize_banner(raw) == "SSH-2.0-OpenSSH_9.6 Ubuntu-3ubuntu0.6"
        assert len(_sanitize_banner("X" * 300, max_len=100)) == 100

    def test_confirmed_open_with_banner_sets_evidence_confirmed(self) -> None:
        reader = _DummyReader(b"SSH-2.0-OpenSSH_9.6\r\n")
        writer = _DummyWriter()

        async def _fake_open_connection(host: str, port: int):
            return reader, writer

        detector = HardenedPortDetector(per_probe_delay=0.0)
        with patch("asyncio.open_connection", side_effect=_fake_open_connection):
            result = asyncio.run(detector.probe_port("127.0.0.1", 22))

        assert result.state == PortState.CONFIRMED_OPEN
        assert result.banner == "SSH-2.0-OpenSSH_9.6"
        assert result.evidence_confirmed is True
        assert writer.closed is True

    def test_confirmed_open_without_banner_on_non_web_port_marks_unconfirmed_evidence(self) -> None:
        reader = _DummyReader(b"")
        writer = _DummyWriter()

        async def _fake_open_connection(host: str, port: int):
            return reader, writer

        detector = HardenedPortDetector(per_probe_delay=0.0, enable_active_probe=False)
        with patch("asyncio.open_connection", side_effect=_fake_open_connection):
            result = asyncio.run(detector.probe_port("127.0.0.1", 9999))

        assert result.state == PortState.CONFIRMED_OPEN
        assert result.banner is None
        assert result.evidence_confirmed is False
        assert writer.closed is True

    def test_closed_on_connection_refused(self) -> None:
        async def _refused(host: str, port: int):
            raise ConnectionRefusedError("Connection refused")

        detector = HardenedPortDetector(per_probe_delay=0.0)
        with patch("asyncio.open_connection", side_effect=_refused):
            result = asyncio.run(detector.probe_port("127.0.0.1", 22))

        assert result.state == PortState.CLOSED
        assert result.evidence_confirmed is True

    def test_filtered_or_ambiguous_on_timeout_and_oserror(self) -> None:
        hanging_reader = _DummyReader(hang=True)
        hanging_writer = _DummyWriter()

        async def _slow_open(host: str, port: int):
            return hanging_reader, hanging_writer

        detector = HardenedPortDetector(timeout=0.05, banner_timeout=0.05, per_probe_delay=0.0)
        with patch("asyncio.open_connection", side_effect=_slow_open):
            res_timeout = asyncio.run(detector.probe_port("127.0.0.1", 8080))
        assert res_timeout.state == PortState.FILTERED_OR_AMBIGUOUS
        assert res_timeout.evidence_confirmed is False
        assert hanging_writer.closed is True

        async def _os_err(host: str, port: int):
            raise OSError("No route to host")

        with patch("asyncio.open_connection", side_effect=_os_err):
            res_oserr = asyncio.run(detector.probe_port("127.0.0.1", 8081))
        assert res_oserr.state == PortState.FILTERED_OR_AMBIGUOUS
        assert res_oserr.evidence_confirmed is False

    def test_scan_ports_detects_edge_or_cdn_anomaly_on_mass_no_banner_opens(self) -> None:
        async def _open_no_banner(host: str, port: int):
            return _DummyReader(b""), _DummyWriter()

        detector = HardenedPortDetector(
            per_probe_delay=0.0,
            anomaly_open_threshold=3,
            enable_active_probe=False,
        )
        with patch("asyncio.open_connection", side_effect=_open_no_banner):
            summary = asyncio.run(
                detector.scan_ports("edge.target.local", [9001, 9001, 9002, 9003])
            )

        assert [r.port for r in summary.confirmed_open] == [9001, 9002, 9003]
        assert len(summary.confirmed_open) == 3
        assert summary.closed_count == 0
        assert summary.filtered_or_ambiguous_count == 0
        assert summary.edge_anomaly_detected is True
        assert isinstance(summary.anomaly_reason, str)
        assert "3" in summary.anomaly_reason

    def test_attach_cbom_metadata_populates_extra_cbom(self) -> None:
        detector = HardenedPortDetector(per_probe_delay=0.0)
        meta: dict[str, object] = {
            "tls_version": "TLSv1.0",
            "cipher_suite": "TLS_RSA_WITH_3DES_EDE_CBC_SHA",
        }
        detector._attach_cbom_metadata("198.51.100.20", 443, meta)

        assert "cbom" in meta
        cbom_payload = meta["cbom"]
        assert isinstance(cbom_payload, dict)
        assert cbom_payload["asset_id"] == "198.51.100.20:443"
        assert cbom_payload["pqc_readiness"] == "quantum_vulnerable_or_legacy"
        flags = cbom_payload.get("posture_flags", [])
        assert any(flag.startswith("WEAK_TLS_VERSION:") for flag in flags)
        assert any(flag.startswith("DEPRECATED_CIPHER_TOKEN:") for flag in flags)

        empty_meta: dict[str, object] = {}
        detector._attach_cbom_metadata("198.51.100.20", 80, empty_meta)
        assert "cbom" not in empty_meta

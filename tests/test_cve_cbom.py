from __future__ import annotations

import json
from pathlib import Path

import pytest

from security.cve_cbom import CBOMAnalyzer, CBOMAsset, CPEMatch, OfflineCPERepository


def _sample_cpe_entries() -> list[dict]:
    return [
        {
            "vendor": "nginx",
            "product": "nginx",
            "version": "1.24.0",
            "cpe": "cpe:2.3:a:nginx:nginx:1.24.0:*:*:*:*:*:*:*",
            "aliases": ["nginx"],
            "cves": ["CVE-2023-44487"],
            "max_cvss": 7.5,
        },
        {
            "vendor": "openbsd",
            "product": "openssh",
            "version": "8.2p1",
            "cpe": "cpe:2.3:a:openbsd:openssh:8.2p1:*:*:*:*:*:*:*",
            "aliases": ["ssh"],
            "cves": ["CVE-2023-38408"],
            "max_cvss": 9.8,
        },
        {
            "vendor": "apache",
            "product": "http_server",
            "version": "2.4.58",
            "cpe": "cpe:2.3:a:apache:http_server:2.4.58:*:*:*:*:*:*:*",
            "aliases": ["apache", "httpd"],
            "cves": ["CVE-2023-45802"],
            "max_cvss": 7.1,
        },
    ]


class TestOfflineCPERepositoryAndTokenExtraction:
    def test_extract_service_tokens_from_banners(self):
        repo = OfflineCPERepository(_sample_cpe_entries())

        tokens_nginx = repo.extract_service_tokens("Server: nginx/1.24.0 (Ubuntu)")
        tokens_ssh = repo.extract_service_tokens("SSH-2.0-OpenSSH_8.2p1 Ubuntu-4ubuntu0.11")

        assert "nginx:1.24.0" in tokens_nginx
        assert "nginx" in tokens_nginx
        assert "openssh:8.2p1" in tokens_ssh
        assert "openssh" in tokens_ssh

    def test_correlate_banner_prioritizes_highest_cvss_and_tracks_match_type(self):
        repo = OfflineCPERepository(_sample_cpe_entries())

        matches = repo.correlate_banner("SSH-2.0-OpenSSH_8.2p1 Ubuntu-4ubuntu0.11")

        assert len(matches) >= 1
        assert isinstance(matches[0], CPEMatch)
        assert matches[0].product == "openssh"
        assert matches[0].matched_by == "product_and_version"
        assert "CVE-2023-38408" in matches[0].cves
        assert matches[0].max_cvss == 9.8

    def test_from_json_file_supports_list_and_dict_formats(self, tmp_path: Path):
        list_file = tmp_path / "cpe_list.json"
        list_file.write_text(json.dumps(_sample_cpe_entries()), encoding="utf-8")

        dict_file = tmp_path / "cpe_dict.json"
        dict_file.write_text(
            json.dumps({"schema": "1.0", "entries": _sample_cpe_entries()}),
            encoding="utf-8",
        )

        repo_from_list = OfflineCPERepository.from_json_file(list_file)
        repo_from_dict = OfflineCPERepository.from_json_file(dict_file)

        assert len(repo_from_list.entries) == 3
        assert len(repo_from_dict.entries) == 3

    def test_from_json_file_raises_on_missing_path(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            OfflineCPERepository.from_json_file(tmp_path / "no_existe.json")


class TestCBOMAnalyzer:
    def test_detects_weak_tls_cipher_signature_and_rsa_key_size(self):
        analyzer = CBOMAnalyzer()

        asset = analyzer.inspect_crypto_observation(
            target="198.51.100.10",
            port=443,
            protocol="https",
            observed_crypto={
                "tls_version": "TLSv1.1",
                "cipher_suite": "ECDHE-RSA-RC4-SHA",
                "key_algorithm": "RSA",
                "key_bits": 1024,
                "signature_algorithm": "SHA1withRSA",
            },
        )

        assert isinstance(asset, CBOMAsset)
        assert asset.asset_id == "198.51.100.10:443"
        assert asset.pqc_readiness == "quantum_vulnerable_or_legacy"
        assert "WEAK_TLS_VERSION:TLSv1.1" in asset.posture_flags
        assert "DEPRECATED_CIPHER_TOKEN:RC4" in asset.posture_flags
        assert "WEAK_SIGNATURE_ALGORITHM:SHA1withRSA" in asset.posture_flags
        assert "WEAK_RSA_KEY_SIZE:1024b" in asset.posture_flags

    def test_modern_crypto_observation_has_no_legacy_flags(self):
        analyzer = CBOMAnalyzer()

        asset = analyzer.inspect_crypto_observation(
            target="198.51.100.20",
            port=443,
            protocol="https",
            observed_crypto={
                "tls_version": "TLSv1.3",
                "cipher_suite": "TLS_AES_256_GCM_SHA384",
                "key_algorithm": "EC",
                "key_bits": 256,
                "signature_algorithm": "ECDSA-SHA256",
            },
        )

        assert asset.posture_flags == []
        assert asset.pqc_readiness == "hybrid_or_modern_tls_review"

    def test_missing_crypto_telemetry_marks_no_observation(self):
        analyzer = CBOMAnalyzer()

        asset = analyzer.inspect_crypto_observation(
            target="198.51.100.30",
            port=80,
            protocol="http",
            observed_crypto={},
        )

        assert asset.pqc_readiness == "no_crypto_telemetry_observed"
        assert asset.posture_flags == []

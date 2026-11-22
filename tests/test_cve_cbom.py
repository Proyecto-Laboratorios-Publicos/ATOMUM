from __future__ import annotations

import json
from pathlib import Path

import pytest

from security.cve_cbom import (
    CBOMAnalyzer,
    CBOMAsset,
    CPEMatch,
    OfflineCPERepository,
    enrich_service_finding,
)


def _sample_entries() -> list[dict]:
    return [
        {
            "cpe": "cpe:2.3:a:f5:nginx:1.24.0:*:*:*:*:*:*:*",
            "vendor": "f5",
            "product": "nginx",
            "version": "1.24.0",
            "aliases": ["nginx"],
            "cves": ["CVE-2023-44487", "CVE-2022-41741"],
            "max_cvss": 7.5,
        },
        {
            "cpe": "cpe:2.3:a:f5:nginx:*:*:*:*:*:*:*:*",
            "vendor": "f5",
            "product": "nginx",
            "version": None,
            "aliases": ["nginx"],
            "cves": ["CVE-2022-41741", "CVE-2021-23017"],
            "max_cvss": 9.8,
        },
        {
            "cpe": "cpe:2.3:a:openbsd:openssh:8.9p1:*:*:*:*:*:*:*",
            "vendor": "openbsd",
            "product": "openssh",
            "version": "8.9p1",
            "aliases": ["ssh"],
            "cves": ["CVE-2023-38408"],
            "max_cvss": 9.8,
        },
    ]


def test_repository_from_json_file_list_and_entries_dict(tmp_path: Path) -> None:
    list_file = tmp_path / "cpe_list.json"
    list_file.write_text(json.dumps(_sample_entries()), encoding="utf-8")
    repo_from_list = OfflineCPERepository.from_json_file(list_file)
    assert len(repo_from_list.entries) == 3

    dict_file = tmp_path / "cpe_dict.json"
    dict_file.write_text(json.dumps({"entries": _sample_entries()[:2]}), encoding="utf-8")
    repo_from_dict = OfflineCPERepository.from_json_file(dict_file)
    assert len(repo_from_dict.entries) == 2


def test_repository_from_json_file_errors(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        OfflineCPERepository.from_json_file(tmp_path / "missing.json")

    invalid_file = tmp_path / "invalid.json"
    invalid_file.write_text(json.dumps({"unexpected": True}), encoding="utf-8")
    with pytest.raises(ValueError):
        OfflineCPERepository.from_json_file(invalid_file)


def test_correlate_banner_prioritizes_exact_version_and_cvss() -> None:
    repo = OfflineCPERepository(_sample_entries())
    matches = repo.correlate_banner("nginx/1.24.0")

    assert len(matches) >= 2
    assert isinstance(matches[0], CPEMatch)
    assert matches[0].matched_by == "product_and_version"
    assert matches[0].version == "1.24.0"
    assert "CVE-2023-44487" in matches[0].cves


def test_correlate_banner_empty_or_unmatched() -> None:
    repo = OfflineCPERepository(_sample_entries())
    assert repo.correlate_banner("") == []
    assert repo.correlate_banner("unknown-custom-daemon v0.0.1") == []


def test_cbom_analyzer_flags_and_pqc_readiness() -> None:
    analyzer = CBOMAnalyzer()

    no_crypto = analyzer.inspect_crypto_observation("example.com", {}, port=80, protocol="tcp")
    assert isinstance(no_crypto, CBOMAsset)
    assert no_crypto.asset_id == "example.com:80"
    assert no_crypto.pqc_readiness == "no_crypto_telemetry_observed"
    assert no_crypto.posture_flags == []

    weak_asset = analyzer.inspect_crypto_observation(
        "legacy.internal",
        {
            "tls_version": "TLSv1.0",
            "cipher_suite": "TLS_RSA_WITH_3DES_EDE_CBC_SHA",
            "key_algorithm": "RSA",
            "key_bits": 1024,
            "signature_algorithm": "SHA1withRSA",
        },
        port=443,
        protocol="tls",
    )
    assert weak_asset.pqc_readiness == "quantum_vulnerable_or_legacy"
    assert any(flag.startswith("WEAK_TLS_VERSION:") for flag in weak_asset.posture_flags)
    assert any(flag.startswith("DEPRECATED_CIPHER_TOKEN:") for flag in weak_asset.posture_flags)
    assert any(flag.startswith("WEAK_RSA_KEY_SIZE:") for flag in weak_asset.posture_flags)
    assert any(flag.startswith("WEAK_SIGNATURE_ALGORITHM:") for flag in weak_asset.posture_flags)

    modern_asset = analyzer.inspect_crypto_observation(
        "modern.example.org",
        {
            "tls_version": "TLSv1.3",
            "cipher_suite": "TLS_AES_256_GCM_SHA384",
            "key_algorithm": "ECDSA",
            "key_bits": 256,
            "signature_algorithm": "ECDSA-SHA256",
        },
        port=443,
        protocol="tls",
    )
    assert modern_asset.pqc_readiness == "hybrid_or_modern_tls_review"
    assert modern_asset.posture_flags == []


def test_enrich_service_finding_deduplicates_cves_and_builds_cbom() -> None:
    repo = OfflineCPERepository(_sample_entries())
    analyzer = CBOMAnalyzer()

    result = enrich_service_finding(
        target="198.51.100.10",
        port=443,
        banner="nginx/1.24.0",
        repository=repo,
        crypto_analyzer=analyzer,
        observed_crypto={
            "tls_version": "TLSv1.2",
            "cipher_suite": "ECDHE-RSA-AES128-GCM-SHA256",
            "key_algorithm": "RSA",
            "key_bits": 2048,
        },
    )

    assert result["cves"] == ["CVE-2023-44487", "CVE-2022-41741", "CVE-2021-23017"]
    assert isinstance(result["cbom_asset"], CBOMAsset)
    assert result["cbom_asset"].asset_id == "198.51.100.10:443"
    assert result["cbom_asset"].pqc_readiness == "hybrid_or_modern_tls_review"

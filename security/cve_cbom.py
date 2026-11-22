from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CPEMatch(BaseModel):
    cpe_uri: str
    vendor: str
    product: str
    version: Optional[str] = None
    cves: List[str] = Field(default_factory=list)
    max_cvss: Optional[float] = None
    matched_by: str = "banner_token"


class CBOMAsset(BaseModel):
    """Registro de inventario criptográfico (CBOM) derivado de evidencia observada."""

    asset_id: str
    target: str
    port: Optional[int] = None
    protocol: Optional[str] = None
    tls_version: Optional[str] = None
    cipher_suite: Optional[str] = None
    key_algorithm: Optional[str] = None
    key_bits: Optional[int] = None
    signature_algorithm: Optional[str] = None
    pqc_readiness: str = "needs_assessment"
    posture_flags: List[str] = Field(default_factory=list)
    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


def _parse_cvss(raw_value: Any) -> Optional[float]:
    if raw_value is None or isinstance(raw_value, bool):
        return None
    try:
        val = float(str(raw_value).strip())
        if 0.0 <= val <= 10.0:
            return round(val, 1)
    except (TypeError, ValueError):
        return None
    return None


def _parse_int_safe(raw_value: Any) -> Optional[int]:
    if raw_value is None or isinstance(raw_value, bool):
        return None
    try:
        return int(str(raw_value).strip())
    except (TypeError, ValueError):
        return None


class OfflineCPERepository:
    """Consulta determinista y offline sobre cpe_database.json."""

    def __init__(self, entries: List[Dict[str, Any]]) -> None:
        self.entries = entries

    @classmethod
    def from_json_file(cls, db_path: str | Path) -> "OfflineCPERepository":
        path = Path(db_path)
        if not path.exists():
            raise FileNotFoundError(f"No se encontró la base CPE local en: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return cls(payload)
        if isinstance(payload, dict) and isinstance(payload.get("entries"), list):
            return cls(payload["entries"])
        raise ValueError(
            "Formato inválido en cpe_database.json: se esperaba lista o dict con 'entries'."
        )

    @staticmethod
    def extract_service_tokens(banner_or_text: str) -> List[str]:
        """Extrae tokens de producto/versión desde un banner de red o cabecera."""
        if not banner_or_text:
            return []
        cleaned = banner_or_text.strip().lower()
        tokens: List[str] = []

        # Patrones típicos tipo producto/versión (ej: nginx/1.24.0, openssh_8.9p1, apache/2.4.58)
        slash_matches = re.findall(
            r"([a-z0-9._-]{2,})[/\s_-]+v?(\d+(?:\.\d+){0,3}[a-z0-9]*)",
            cleaned,
        )
        for product, ver in slash_matches:
            ver_clean = ver.lower()
            tokens.append(f"{product}:{ver_clean}")
            base_ver = re.match(r"^(\d+(?:\.\d+){0,2})", ver_clean)
            if base_ver and base_ver.group(1) != ver_clean:
                tokens.append(f"{product}:{base_ver.group(1)}")
            if product not in tokens:
                tokens.append(product)

        # Palabras clave alfanuméricas de respaldo
        for word in re.findall(r"[a-z0-9][a-z0-9._-]{1,28}", cleaned):
            if word not in tokens:
                tokens.append(word)
        return tokens

    def correlate_banner(self, banner_or_text: str) -> List[CPEMatch]:
        """Correlaciona un banner o descripción de servicio contra la base CPE local."""
        tokens = self.extract_service_tokens(banner_or_text)
        if not tokens:
            return []
        token_set = set(tokens)
        matches: List[CPEMatch] = []

        for item in self.entries:
            if not isinstance(item, dict):
                continue
            vendor = str(item.get("vendor", "")).lower().strip()
            product = str(item.get("product", "")).lower().strip()
            version = str(item.get("version", "")).strip() or None
            cpe_uri = str(item.get("cpe", item.get("cpe_uri", ""))).strip()
            aliases = [
                str(a).lower().strip()
                for a in item.get("aliases", [])
                if str(a).strip()
            ]
            cves_raw = item.get("cves", [])
            cves = (
                [str(c).strip() for c in cves_raw if str(c).strip()]
                if isinstance(cves_raw, list)
                else []
            )
            max_cvss = _parse_cvss(item.get("max_cvss"))

            candidates = {c for c in [product, vendor, *aliases] if c}
            versioned_keys = (
                {f"{c}:{version.lower()}" for c in candidates} if version else set()
            )

            matched_by: Optional[str] = None
            if versioned_keys & token_set:
                matched_by = "product_and_version"
            elif candidates & token_set:
                matched_by = "product_or_alias"

            if matched_by:
                matches.append(
                    CPEMatch(
                        cpe_uri=cpe_uri
                        or f"cpe:2.3:a:{vendor or '*'}:{product or '*'}:{version or '*'}",
                        vendor=vendor or "unknown",
                        product=product or "unknown",
                        version=version,
                        cves=cves,
                        max_cvss=max_cvss,
                        matched_by=matched_by,
                    )
                )

        matches.sort(
            key=lambda m: (
                m.matched_by == "product_and_version",
                m.max_cvss is not None,
                m.max_cvss or 0.0,
            ),
            reverse=True,
        )
        return matches


class CBOMAnalyzer:
    """Evalúa postura criptográfica observada para construir entradas de CBOM."""

    _WEAK_TLS = {"SSLV2", "SSLV3", "TLSV1", "TLSV1.0", "TLSV1.1", "TLS 1.0", "TLS 1.1"}
    _DEPRECATED_CIPHERS = ("RC4", "3DES", "DES", "NULL", "EXPORT", "ANON", "MD5")
    _WEAK_SIGS = ("MD2", "MD5", "SHA1", "SHA-1")

    def inspect_crypto_observation(
        self,
        target: str,
        observed_crypto: Dict[str, Any],
        port: Optional[int] = None,
        protocol: Optional[str] = None,
    ) -> CBOMAsset:
        tls_ver_raw = observed_crypto.get("tls_version")
        cipher_raw = observed_crypto.get("cipher_suite")
        key_alg_raw = observed_crypto.get("key_algorithm")
        key_bits = _parse_int_safe(observed_crypto.get("key_bits"))
        sig_alg_raw = observed_crypto.get("signature_algorithm")

        tls_ver = str(tls_ver_raw).strip() if tls_ver_raw else None
        cipher = str(cipher_raw).strip() if cipher_raw else None
        key_alg = str(key_alg_raw).strip() if key_alg_raw else None
        sig_alg = str(sig_alg_raw).strip() if sig_alg_raw else None

        flags: List[str] = []

        if tls_ver and tls_ver.upper() in self._WEAK_TLS:
            flags.append(f"WEAK_TLS_VERSION:{tls_ver}")

        if cipher:
            cipher_upper = cipher.upper()
            for bad in self._DEPRECATED_CIPHERS:
                if bad in cipher_upper:
                    flags.append(f"DEPRECATED_CIPHER_TOKEN:{bad}")

        if sig_alg:
            sig_upper = sig_alg.upper()
            for weak_sig in self._WEAK_SIGS:
                if weak_sig in sig_upper:
                    flags.append(f"WEAK_SIGNATURE_ALGORITHM:{sig_alg}")

        if key_alg and key_bits is not None:
            alg_upper = key_alg.upper()
            if "RSA" in alg_upper and key_bits < 2048:
                flags.append(f"WEAK_RSA_KEY_SIZE:{key_bits}b")
            elif ("EC" in alg_upper or "ECDSA" in alg_upper) and key_bits < 256:
                flags.append(f"WEAK_ECC_KEY_SIZE:{key_bits}b")

        if not tls_ver and not cipher and not key_alg and not sig_alg:
            pqc_readiness = "no_crypto_telemetry_observed"
        elif flags:
            pqc_readiness = "quantum_vulnerable_or_legacy"
        else:
            pqc_readiness = "hybrid_or_modern_tls_review"

        asset_id = f"{target}:{port}" if (port is not None and port > 0) else target
        return CBOMAsset(
            asset_id=asset_id,
            target=target,
            port=port,
            protocol=protocol or "tls",
            tls_version=tls_ver,
            cipher_suite=cipher,
            key_algorithm=key_alg,
            key_bits=key_bits,
            signature_algorithm=sig_alg,
            pqc_readiness=pqc_readiness,
            posture_flags=flags,
        )


def enrich_service_finding(
    target: str,
    port: int,
    banner: str,
    repository: Optional[OfflineCPERepository] = None,
    crypto_analyzer: Optional[CBOMAnalyzer] = None,
    observed_crypto: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Correlaciona un banner con CPE/CVEs y construye un CBOMAsset si hay telemetría."""
    cpe_matches: List[CPEMatch] = repository.correlate_banner(banner) if repository else []
    cves: List[str] = []
    for match in cpe_matches:
        for cve in match.cves:
            if cve not in cves:
                cves.append(cve)

    cbom_asset: Optional[CBOMAsset] = None
    if crypto_analyzer and observed_crypto:
        cbom_asset = crypto_analyzer.inspect_crypto_observation(
            target=target,
            observed_crypto=observed_crypto,
            port=port,
            protocol="tls",
        )

    return {
        "cpe_matches": cpe_matches,
        "cves": cves,
        "cbom_asset": cbom_asset,
    }

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
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
        raise ValueError("Formato inválido en cpe_database.json: se esperaba lista o dict con 'entries'.")

    @staticmethod
    def extract_service_tokens(banner_or_text: str) -> List[str]:
        """Extrae tokens de producto/versión desde un banner de red o cabecera."""
        if not banner_or_text:
            return []
        cleaned = banner_or_text.strip().lower()
        tokens: List[str] = []

        # Patrones típicos tipo producto/versión (ej: nginx/1.24.0, openssh_8.9p1, apache/2.4.58)
        slash_matches = re.findall(r"([a-z0-9._-]{2,})[/\s_-]+v?(\d+(?:\.\d+){0,3}[a-z0-9]*)", cleaned)
        for product, ver in slash_matches:
            tokens.append(f"{product}:{ver}")
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
            vendor = str(item.get("vendor", "")).lower().strip()
            product = str(item.get("product", "")).lower().strip()
            version = str(item.get("version", "")).strip() or None
            cpe_uri = str(item.get("cpe", item.get("cpe_uri", ""))).strip()
            aliases = [str(a).lower().strip() for a in item.get("aliases", [])]
            cves = [str(c) for c in item.get("cves", [])]
            max_cvss = item.get("max_cvss")

            candidates = {c for c in [product, vendor, *aliases] if c}
            versioned_keys = {f"{c}:{version.lower()}" for c in candidates if version}

            matched_by: Optional[str] = None
            if versioned_keys & token_set:
                matched_by = "product_and_version"
            elif candidates & token_set:
                matched_by = "product_or_alias"

            if matched_by:
                matches.append(
                    CPEMatch(
                        cpe_uri=cpe_uri or f"cpe:2.3:a:{vendor or '*'}:{product or '*'}:{version or '*'}",
                        vendor=vendor or "unknown",
                        product=product or "unknown",
                        version=version,
                        cves=cves,
                        max_cvss=float(max_cvss) if max_cvss is not None else None,
                        matched_by=matched_by,
                    )
                )

        matches.sort(key=lambda m: (m.max_cvss is not None, m.max_cvss or 0.0), reverse=True)
        return matches


class CBOMAnalyzer:
    """Evalúa postura criptográfica observada para construir entradas de CBOM."""

    _WEAK_TLS = {"SSLv2", "SSLv3", "TLSv1", "TLSv1.0", "TLSv1.1", "TLS 1.0", "TLS 1.1"}
    _DEPRECATED_CIPHERS = ("RC4", "3DES", "DES", "NULL", "EXPORT", "ANON", "MD5")
    _WEAK_SIGS = ("MD2", "MD5", "SHA1", "SHA-1")

    def inspect_crypto_observation(
        self,
        target: str,
        observed_crypto: Dict[str, Any],
        port: Optional[int] = None,
        protocol: Optional[str] = None,
    ) -> CBOMAsset:
        tls_ver = observed_crypto.get("tls_version")
        cipher = observed_crypto.get("cipher_suite")
        key_alg = observed_crypto.get("key_algorithm")
        key_bits_raw = observed_crypto.get("key_bits")
        key_bits = int(key_bits_raw) if key_bits_raw is not None else None
        sig_alg = observed_crypto.get("signature_algorithm")

        flags: List[str] = []

        if tls_ver and str(tls_ver).strip() in self._WEAK_TLS:
            flags.append(f"WEAK_TLS_VERSION:{tls_ver}")

        if cipher:
            cipher_upper = str(cipher).upper()
            for bad in self._DEPRECATED_CIPHERS:
                if bad in cipher_upper:
                    flags.append(f"DEPRECATED_CIPHER_TOKEN:{bad}")

        if sig_alg:
            sig_upper = str(sig_alg).upper()
            for weak_sig in self._WEAK_SIGS:
                if weak_sig in sig_upper:
                    flags.append(f"WEAK_SIGNATURE_ALGORITHM:{sig_alg}")

        if key_alg and key_bits is not None:
            alg_upper = str(key_alg).upper()
            if "RSA" in alg_upper and key_bits < 2048:
                flags.append(f"WEAK_RSA_KEY_SIZE:{key_bits}b")
            elif "EC" in alg_upper and key_bits < 256:
                flags.append(f"WEAK_ECC_KEY_SIZE:{key_bits}b")

        pqc_readiness = "quantum_vulnerable_or_legacy" if flags else "hybrid_or_modern_tls_review"
        if not tls_ver and not cipher and not key_alg:
            pqc_readiness = "no_crypto_telemetry_observed"

        asset_id = f"{target}:{port}" if port is not None else target
        return CBOMAsset(
            asset_id=asset_id,
            target=target,
            port=port,
            protocol=protocol or "tls",
            tls_version=str(tls_ver) if tls_ver else None,
            cipher_suite=str(cipher) if cipher else None,
            key_algorithm=str(key_alg) if key_alg else None,
            key_bits=key_bits,
            signature_algorithm=str(sig_alg) if sig_alg else None,
            pqc_readiness=pqc_readiness,
            posture_flags=flags,
        )

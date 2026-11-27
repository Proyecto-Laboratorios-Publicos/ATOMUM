from datetime import datetime, timezone
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class IndicatorOfCompromise(BaseModel):
    """Representa un Indicador de Compromiso (IoC)."""

    type: str # ej., IP, dominio, hash
    value: str
    description: Optional[str] = None
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class VulnerabilityReference(BaseModel):
    """Representa una referencia a una vulnerabilidad (CVE, CWE, etc.)."""

    id: str # ej., CVE-2023-12345
    source: str # ej., NVD, MITRE
    severity: Optional[str] = None
    description: Optional[str] = None


class ThreatIntelligence(BaseModel):
    """Representa una inteligencia de amenazas consolidada."""

    threat_id: str
    name: str
    description: Optional[str] = None
    actors: List[str] = Field(default_factory=list)
    malware_families: List[str] = Field(default_factory=list)
    indicators: List[IndicatorOfCompromise] = Field(default_factory=list)
    vulnerabilities: List[VulnerabilityReference] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

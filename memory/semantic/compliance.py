from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class ComplianceStandard(BaseModel):
    """Representa un estándar o marco de cumplimiento (ej., ISO 27001, PCI-DSS)."""

    name: str  # Nombre del estándar
    version: Optional[str] = None  # Versión del estándar
    description: Optional[str] = None  # Descripción breve


class SecurityPolicy(BaseModel):
    """Representa una política de seguridad interna o estándar de cumplimiento."""

    policy_id: str  # Identificador único (ej., POL-SEC-001)
    title: str  # Título de la política
    description: str  # Detalle de la norma a cumplir
    category: str  # Categoría (ej., Acceso, Red, Cifrado)
    relevant_standards: List[ComplianceStandard] = Field(
        default_factory=list
    )  # Estándares asociados
    is_active: bool = True  # Estado de la política
    last_updated: datetime = Field(default_factory=datetime.utcnow)

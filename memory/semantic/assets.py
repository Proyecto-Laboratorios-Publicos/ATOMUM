from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class Asset(BaseModel):
    """Representa un activo dentro de la infraestructura analizada."""

    asset_id: str  # ID único del activo
    name: str  # Nombre o hostname del activo
    type: str  # Tipo de activo (ej., Servidor, Base de Datos, Endpoint)
    criticality: int = Field(
        default=1, ge=1, le=5
    )  # Nivel de criticidad (1 al 5)
    ip_address: Optional[str] = None  # Dirección IP asociada
    os: Optional[str] = None  # Sistema operativo
    services: List[str] = Field(
        default_factory=list
    )  # Servicios o puertos abiertos
    associated_vulnerabilities: List[str] = Field(
        default_factory=list
    )  # CVEs asociados
    tags: List[str] = Field(default_factory=list)  # Etiquetas adicionales
    last_scanned: datetime = Field(default_factory=datetime.utcnow)

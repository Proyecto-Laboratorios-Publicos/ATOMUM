from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field

class EpisodicEvent(BaseModel):
    """Representa un evento o acción individual registrado en la memoria episódica."""
    
    event_id: UUID = Field(
        default_factory=uuid4, 
        description="Identificador único universal del evento"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), 
        description="Fecha y hora en que ocurrió el evento"
    )
    agent_role: str = Field(
        ..., 
        description="Rol o nombre del agente que ejecutó la acción"
    )
    action: str = Field(
        ..., 
        description="Nombre o descripción de la acción realizada"
    )
    inputs: Dict[str, Any] = Field(
        default_factory=dict, 
        description="Datos o argumentos de entrada para la acción"
    )
    outputs: Dict[str, Any] = Field(
        default_factory=dict, 
        description="Datos o resultados obtenidos de la acción"
    )
    result_status: str = Field(
        ..., 
        description="Estado del resultado, ej. 'success', 'failed'"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, 
        description="Información de contexto adicional o métricas"
    )

    class Config:
        json_encoders = {
            UUID: lambda v: str(v),
            datetime: lambda v: v.isoformat()
        }

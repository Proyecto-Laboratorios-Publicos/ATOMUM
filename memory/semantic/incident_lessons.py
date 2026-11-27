from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class LessonLearned(BaseModel):
    """Representa una lección aprendida de un incidente de seguridad."""

    lesson_id: str  # ID único
    incident_id: Optional[str] = None  # ID del incidente relacionado
    category: str  # Categoría (ej., Detección, Respuesta, Configuración)
    finding: str  # hallazgo o problema detectado
    recommendation: str  # Acción recomendada o correctiva
    preventive_measure: str  # Medida preventiva implementada
    severity_addressed: Optional[int] = Field(
        default=1, ge=1, le=5
    )  # Severidad del problema solucionado
    tags: List[str] = Field(default_factory=list)  # Etiquetas
    created_at: datetime = Field(default_factory=datetime.utcnow)

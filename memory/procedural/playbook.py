from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class PlaybookStep(BaseModel):
    """Representa un paso individual dentro de un playbook de ejecución."""

    step_id: str
    action: str
    description: Optional[str] = None
    parameters: Dict[str, str] = Field(default_factory=dict)
    expected_outcome: Optional[str] = None
    fallback_action: Optional[str] = None


class Playbook(BaseModel):
    """Representa un playbook operativo para manejar un escenario o incidente."""

    playbook_id: str
    title: str
    description: str
    category: str  # Ej., Contención, Erradicación, Recuperación
    steps: List[PlaybookStep] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SuccessfulTechnique(BaseModel):
    """Documenta una técnica o flujo de acción que demostró ser exitoso."""

    technique_id: str
    name: str
    context: str  # Escenario en el que fue exitoso
    steps_executed: List[str]  # Pasos que llevaron al éxito
    effectiveness_score: float = Field(default=1.0, ge=0.0, le=1.0)
    learned_at: datetime = Field(default_factory=datetime.utcnow)

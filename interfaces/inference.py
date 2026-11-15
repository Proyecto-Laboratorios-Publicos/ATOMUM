from abc import ABC, abstractmethod
from typing import Any, Dict

class InferenceEngine(ABC):
    @abstractmethod
    async def run(self, model_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Ejecuta el modelo y devuelve el resultado crudo."""
        pass

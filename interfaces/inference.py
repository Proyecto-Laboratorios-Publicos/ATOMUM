# atomum/interfaces/inference.py
from abc import ABC, abstractmethod
from typing import Any, Dict

class InferenceEngine(ABC):
    @abstractmethod
    async def run(self, model_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Ejecuta el modelo en la API de Groq y devuelve el resultado crudo."""
        pass

# atomum/interfaces/context.py
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

class ContextStore(ABC):
    @abstractmethod
    async def get(self, key: str) -> Any:
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        pass

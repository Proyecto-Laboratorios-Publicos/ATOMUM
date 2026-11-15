from abc import ABC, abstractmethod
from typing import Any, Dict, List


class ContextStore(ABC):
    @abstractmethod
    async def get(self, key: str) -> Any:
        """Recupera un valor del contexto por clave."""
        ...

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Guarda un valor en el contexto con TTL opcional."""
        ...

    @abstractmethod
    async def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Busca registros relevantes en el contexto."""
        ...

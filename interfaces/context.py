from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

class ContextStore(ABC):
    @abstractmethod
    async def get(self, key: str) -> Any:
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        pass

    @abstractmethod
    async def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        pass

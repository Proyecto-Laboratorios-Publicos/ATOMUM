from typing import Any, Dict, List, Optional
from atomum.interfaces.context import ContextStore

class StubContextStore(ContextStore):
    """Simulador de almacenamiento de memoria volátil y determinista para pruebas."""

    def __init__(self, initial_data: Optional[Dict[str, Any]] = None):
        self._mock_db: Dict[str, Any] = initial_data.copy() if initial_data else {}

    async def get(self, key: str) -> Any:
        return self._mock_db.get(key, None)

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        self._mock_db[key] = value

    async def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        return [
            {"key": k, "value": v}
            for k, v in list(self._mock_db.items())[:top_k]
            if query.lower() in str(k).lower() or query.lower() in str(v).lower()
        ]

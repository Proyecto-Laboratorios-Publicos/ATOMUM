from typing import Any, Dict, List, Optional
from atomum.interfaces.context import ContextStore


class ContextService(ContextStore):
    def __init__(self) -> None:
        # Almacenamiento en memoria volátil (puede extenderse luego a JSON, Redis o DB)
        self._store: Dict[str, Any] = {}

    async def get(self, key: str) -> Any:
        """Recupera un valor del almacén de contexto según su clave."""
        return self._store.get(key)

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Establece un valor en el almacén de contexto."""
        # TTL queda disponible para futura integración con bases de datos o caché en memoria
        self._store[key] = value

    async def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Realiza una búsqueda básica por coincidencia de texto dentro del contexto."""
        results = []
        for key, value in self._store.items():
            if query.lower() in str(key).lower() or query.lower() in str(value).lower():
                results.append({"key": key, "value": value})
                if len(results) >= top_k:
                    break
        return results

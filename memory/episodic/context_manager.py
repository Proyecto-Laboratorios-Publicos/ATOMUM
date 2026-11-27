from __future__ import annotations
from typing import Any, Dict, List, Optional
from autonomous_loop.memory.episodic.models import EpisodicEvent
from autonomous_loop.memory.episodic.store import EpisodicMemoryStore

class EpisodicMemoryContextManager:
    """Gestiona el contexto y la interacción de alto nivel con la memoria episódica."""
    
    def __init__(self, store: EpisodicMemoryStore):
        """Inicializa el manager con una instancia de EpisodicMemoryStore."""
        self.store = store

    def log_action(
        self,
        agent_role: str,
        action: str,
        inputs: Dict[str, Any],
        outputs: Dict[str, Any],
        result_status: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Registra una nueva acción como un evento en la memoria episódica."""
        event = EpisodicEvent(
            agent_role=agent_role,
            action=action,
            inputs=inputs,
            outputs=outputs,
            result_status=result_status,
            metadata=metadata or {}
        )
        return self.store.save_event(event)

    def get_recent_context(self, limit: int = 5) -> List[EpisodicEvent]:
        """Obtiene los eventos más recientes registrados en la memoria."""
        return self.store.query_events(limit=limit)

    def get_agent_history(self, agent_role: str, limit: int = 10) -> List[EpisodicEvent]:
        """Recupera el historial de acciones de un agente específico."""
        return self.store.query_events(agent_role=agent_role, limit=limit)

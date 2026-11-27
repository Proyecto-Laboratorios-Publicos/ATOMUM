from __future__ import annotations
import json
from typing import Any, Dict, List, Optional
from uuid import UUID
from redis import Redis
from datetime import datetime
from autonomous_loop.memory.episodic.models import EpisodicEvent

class EpisodicMemoryStore:
    """Implementación de almacenamiento para la memoria episódica usando Redis."""

    def __init__(self, redis_client: Redis, namespace: str = "episodic_memory"):
        self.redis = redis_client
        self.namespace = namespace

    def _get_key(self, event_id: UUID | str) -> str:
        return f"{self.namespace}:event:{event_id}"

    def _get_index_key(self) -> str:
        return f"{self.namespace}:index"

    def save_event(self, event: EpisodicEvent) -> bool:
        """Guarda un evento en la memoria episódica."""
        try:
            key = self._get_key(event.event_id)
            self.redis.set(key, event.model_dump_json())
            
            # Indexamos el ID del evento (por ejemplo, en un Set) para facilitar las consultas
            index_key = self._get_index_key()
            self.redis.sadd(index_key, str(event.event_id))
            
            return True
        except Exception as e:
            print(f"Error al guardar evento en memoria episódica: {e}")
            return False

    def get_event(self, event_id: UUID | str) -> Optional[EpisodicEvent]:
        """Obtiene un evento específico por su ID."""
        try:
            key = self._get_key(event_id)
            data = self.redis.get(key)
            if data:
                return EpisodicEvent.model_validate_json(data)
            return None
        except Exception as e:
            print(f"Error al obtener evento de memoria episódica: {e}")
            return None

    def query_events(
        self, 
        agent_role: Optional[str] = None, 
        result_status: Optional[str] = None,
        limit: int = 10
    ) -> List[EpisodicEvent]:
        """Consulta eventos filtrando por rol de agente o estado, con un límite."""
        try:
            index_key = self._get_index_key()
            event_ids = self.redis.smembers(index_key)
            
            events = []
            for event_id in event_ids:
                event = self.get_event(event_id.decode("utf-8"))
                if event:
                    if agent_role and event.agent_role != agent_role:
                        continue
                    if result_status and event.result_status != result_status:
                        continue
                    events.append(event)
                    
                    if len(events) >= limit:
                        break
            
            # Ordenamos por timestamp de manera descendente
            events.sort(key=lambda x: x.timestamp, reverse=True)
            return events
        except Exception as e:
            print(f"Error al consultar la memoria episódica: {e}")
            return []

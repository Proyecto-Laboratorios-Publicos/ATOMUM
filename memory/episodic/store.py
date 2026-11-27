from __future__ import annotations
import json
import os
import psycopg2
from psycopg2.extras import Json
from typing import Any, Dict, List, Optional
from uuid import UUID
from redis import Redis
from datetime import datetime
from memory.episodic.models import EpisodicEvent

class EpisodicMemoryStore:
    """Implementación de almacenamiento para la memoria episódica usando Redis y PostgreSQL."""
    def __init__(self, redis_client: Optional[Redis] = None, namespace: str = "episodic_memory"):
        self.redis = redis_client or Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            db=0,
            decode_responses=True,
        )
        self.namespace = namespace
        self.db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/atomum_db")

    def _get_db_connection(self) -> Any:
        return psycopg2.connect(self.db_url)

    def _get_key(self, event_id: UUID | str) -> str:
        return f"{self.namespace}:event:{event_id}"

    def _get_index_key(self) -> str:
        return f"{self.namespace}:index"

    def save_event(self, event: EpisodicEvent) -> bool:
        """Guarda un evento en la memoria episódica en Redis y PostgreSQL."""
        try:
            # 1. Guardar en Redis (Caché)
            key = self._get_key(event.event_id)
            self.redis.set(key, event.model_dump_json())
            
            # Indexamos el ID del evento para facilitar las consultas
            index_key = self._get_index_key()
            self.redis.sadd(index_key, str(event.event_id))

            # 2. Guardar en PostgreSQL (Largo Plazo)
            conn = self._get_db_connection()
            cur = conn.cursor()
            try:
                cur.execute(
                    """
                    INSERT INTO episodic_events (event_id, agent_role, inputs, outputs, result_status, timestamp)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (event_id) DO UPDATE 
                    SET agent_role = EXCLUDED.agent_role,
                        inputs = EXCLUDED.inputs,
                        outputs = EXCLUDED.outputs,
                        result_status = EXCLUDED.result_status;
                    """,
                    (
                        str(event.event_id),
                        event.agent_role,
                        Json(event.inputs),
                        Json(event.outputs),
                        event.result_status,
                        event.timestamp
                    )
                )
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise e
            finally:
                cur.close()
                conn.close()

            return True
        except Exception as e:
            print(f"Error al guardar evento en memoria episódica: {e}")
            return False

    def get_event(self, event_id: UUID | str) -> Optional[EpisodicEvent]:
        """Obtiene un evento específico por su ID desde Redis o PostgreSQL."""
        try:
            key = self._get_key(event_id)
            data = self.redis.get(key)
            if data:
                return EpisodicEvent.model_validate_json(data)
            
            # Si no está en Redis, buscar en PostgreSQL
            conn = self._get_db_connection()
            cur = conn.cursor()
            try:
                cur.execute(
                    """
                    SELECT event_id, agent_role, inputs, outputs, result_status, timestamp
                    FROM episodic_events WHERE event_id = %s;
                    """,
                    (str(event_id),)
                )
                row = cur.fetchone()
                if row:
                    event = EpisodicEvent(
                        event_id=row[0],
                        agent_role=row[1],
                        inputs=row[2],
                        outputs=row[3],
                        result_status=row[4],
                        timestamp=row[5]
                    )
                    # Sincronizar en Redis para futuras consultas
                    self.redis.set(key, event.model_dump_json())
                    return event
                return None
            finally:
                cur.close()
                conn.close()
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
                event_id_str = event_id.decode("utf-8") if isinstance(event_id, bytes) else event_id
                event = self.get_event(event_id_str)
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

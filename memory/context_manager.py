from datetime import datetime, timezone
import json
import logging
import os
from typing import Any, Dict, List, Optional
import redis
import psycopg2

logger = logging.getLogger(__name__)

class ContextManager:
    def __init__(self) -> None:
        # Configuración de Redis
        self.redis_client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            db=0,
            decode_responses=True,
        )
        # Configuración de PostgreSQL
        self.db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/atomum_db")
        self._init_db()

    def _get_db_connection(self) -> Any:
        return psycopg2.connect(self.db_url)

    def _init_db(self) -> None:
        """Inicializa la tabla para el historial de eventos en PostgreSQL."""
        conn = self._get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS system_events (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    event_type TEXT,
                    details TEXT
                );
            """)
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cur.close()
            conn.close()

    def log_event(self, event_type: str, details: str) -> bool:
        """Registra un evento del sistema en Redis y PostgreSQL."""
        try:
            timestamp = datetime.now(timezone.utc)
            
            # 1. Guardar en Redis como caché
            redis_key = "system_events:recent"
            event_entry = {
                "timestamp": timestamp.isoformat(),
                "type": event_type,
                "details": details
            }
            self.redis_client.lpush(redis_key, json.dumps(event_entry))
            self.redis_client.ltrim(redis_key, 0, 99) # Mantener los últimos 100 eventos
            
            # 2. Guardar en PostgreSQL
            conn = self._get_db_connection()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO system_events (timestamp, event_type, details)
                VALUES (%s, %s, %s);
            """, (timestamp, event_type, details))
            conn.commit()
            cur.close()
            conn.close()
            
            logger.info("[Event Log] Evento guardado exitosamente: [%s]", event_type)
            return True
        except Exception as e:
            logger.error("[Context Error] No se pudo registrar el evento en memoria: %s", e)
            return False

    def get_recent_events(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Devuelve los últimos N eventos almacenados en PostgreSQL."""
        try:
            conn = self._get_db_connection()
            cur = conn.cursor()
            cur.execute("""
                SELECT timestamp, event_type, details
                FROM system_events
                ORDER BY id DESC LIMIT %s;
            """, (limit,))
            rows = cur.fetchall()
            
            events = []
            for row in rows:
                events.append({
                    "timestamp": row[0].isoformat() if row[0] else None,
                    "type": row[1],
                    "details": row[2]
                })
            cur.close()
            conn.close()
            return events[::-1] # Invertir el orden para que sea cronológico
        except Exception as e:
            logger.error("[Context Error] No se pudo leer el historial de memoria: %s", e)
            return []

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cm = ContextManager()
    cm.log_event("SYSTEM_TEST", "Verificando persistencia y robustez del administrador de contexto.")

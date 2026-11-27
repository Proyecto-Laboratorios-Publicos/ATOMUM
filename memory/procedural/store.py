import os
import json
from typing import Any, Dict, List, Optional
import redis
import psycopg2
from psycopg2.extras import Json
from memory.procedural.playbook import Playbook

class ProceduralMemoryStore:
    """
    Gestiona el almacenamiento de la memoria procedimental.
    Utiliza Redis para almacenamiento rápido de recuperación reciente
    y PostgreSQL con soporte pgvector para almacenamiento y búsqueda a largo plazo.
    """
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

    def _get_db_connection(self) -> Any:
        return psycopg2.connect(self.db_url)

    def save_playbook(self, playbook: Playbook) -> None:
        """Guarda un playbook en Redis y PostgreSQL."""
        # 1. Guardar en Redis (Corto Plazo / Caché)
        redis_key = f"playbook:{playbook.playbook_id}"
        self.redis_client.set(redis_key, json.dumps(playbook.to_dict()))
        
        # 2. Guardar en PostgreSQL (Largo Plazo)
        conn = self._get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO playbooks (playbook_id, title, description, category, steps, tags, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (playbook_id) DO UPDATE 
                SET title = EXCLUDED.title, 
                    description = EXCLUDED.description, 
                    category = EXCLUDED.category,
                    steps = EXCLUDED.steps, 
                    tags = EXCLUDED.tags;
                """,
                (
                    playbook.playbook_id, 
                    playbook.title, 
                    playbook.description, 
                    playbook.category, 
                    Json([step.to_dict() for step in playbook.steps]), 
                    playbook.tags,
                    playbook.created_at
                )
            )
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cur.close()
            conn.close()

    def get_playbook(self, playbook_id: str) -> Optional[Playbook]:
        """Recupera un playbook desde Redis o PostgreSQL."""
        # Intento de lectura en Redis (Cache Hit)
        redis_key = f"playbook:{playbook_id}"
        cached_data = self.redis_client.get(redis_key)
        if cached_data:
            return Playbook.from_dict(json.loads(cached_data))
        
        # Si no está en Redis, buscar en PostgreSQL
        conn = self._get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT playbook_id, title, description, category, steps, tags, created_at
                FROM playbooks WHERE playbook_id = %s;
                """,
                (playbook_id,)
            )
            row = cur.fetchone()
            if row:
                # El campo created_at (row[6]) ya es un objeto datetime al usar psicopg2
                playbook = Playbook(
                    playbook_id=row[0],
                    title=row[1],
                    description=row[2],
                    category=row[3],
                    steps=[PlaybookStep.from_dict(step) for step in row[4]],
                    tags=row[5],
                    created_at=row[6]
                )
                
                # Sincronizar en Redis para futuras consultas
                self.redis_client.set(redis_key, json.dumps(playbook.to_dict()))
                return playbook
            return None
        finally:
            cur.close()
            conn.close()

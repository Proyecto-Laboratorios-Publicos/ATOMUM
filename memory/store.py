import os
import json
import logging
from typing import Any, Dict, List, Optional
import redis
import psycopg2
from psycopg2.extras import Json

logger = logging.getLogger(__name__)

class PersistentStore:
    """
    Gestor de persistencia transaccional para ATOMUM.
    Almacena el estado de los objetivos, parches propuestos y métricas de ejecución.
    Utiliza Redis para caché y PostgreSQL para almacenamiento a largo plazo.
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
        self._init_db()

    def _get_db_connection(self) -> Any:
        return psycopg2.connect(self.db_url)

    def _init_db(self) -> None:
        """Inicializa las tablas base en PostgreSQL para el registro de memoria y automejora."""
        conn = self._get_db_connection()
        cur = conn.cursor()
        try:
            # Tabla de registros generales de ejecución
            cur.execute("""
                CREATE TABLE IF NOT EXISTS autonomous_logs (
                    id SERIAL PRIMARY KEY,
                    goal_id TEXT,
                    proposal_id TEXT,
                    status TEXT,
                    metrics JSONB,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_autonomous_logs_goal_id ON autonomous_logs (goal_id);
            """)
            
            # Tabla para Inteligencia de Amenazas
            cur.execute("""
                CREATE TABLE IF NOT EXISTS threat_intelligence (
                    id SERIAL PRIMARY KEY,
                    threat_id TEXT UNIQUE,
                    description TEXT,
                    severity TEXT,
                    ioc_data JSONB,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Tabla para Políticas de Cumplimiento
            cur.execute("""
                CREATE TABLE IF NOT EXISTS compliance_policies (
                    id SERIAL PRIMARY KEY,
                    policy_id TEXT UNIQUE,
                    standards JSONB,
                    last_updated TIMESTAMP
                );
            """)

            # Tabla para Activos
            cur.execute("""
                CREATE TABLE IF NOT EXISTS assets (
                    id SERIAL PRIMARY KEY,
                    asset_id TEXT UNIQUE,
                    classification TEXT,
                    last_scanned TIMESTAMP
                );
            """)

            # Tabla para Lecciones Aprendidas
            cur.execute("""
                CREATE TABLE IF NOT EXISTS incident_lessons (
                    id SERIAL PRIMARY KEY,
                    lesson_id TEXT UNIQUE,
                    category TEXT,
                    details TEXT,
                    mitigated BOOLEAN,
                    created_at TIMESTAMP
                );
            """)

            conn.commit()
            logger.info("Tablas de memoria semántica inicializadas correctamente.")
        except Exception as e:
            conn.rollback()
            logger.error("Error al inicializar la base de datos: %s", e)
            raise e
        finally:
            cur.close()
            conn.close()

    def record_execution(self, goal_id: str, proposal_id: str, status: str, metrics: dict[str, Any]) -> None:
        """Registra el resultado de una iteración del bucle autónomo en Redis y PostgreSQL."""
        # 1. Guardar en Redis como caché
        redis_key = f"execution:last:{goal_id}"
        self.redis_client.set(redis_key, json.dumps({
            "goal_id": goal_id,
            "proposal_id": proposal_id,
            "status": status,
            "metrics": metrics
        }))
        
        # 2. Guardar en PostgreSQL
        conn = self._get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO autonomous_logs (goal_id, proposal_id, status, metrics)
                VALUES (%s, %s, %s, %s);
            """, (goal_id, proposal_id, status, Json(metrics)))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cur.close()
            conn.close()

    def get_recent_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Recupera el historial reciente de ejecuciones del bucle desde PostgreSQL."""
        safe_limit = max(0, int(limit))
        if safe_limit == 0:
            return []
            
        conn = self._get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT goal_id, proposal_id, status, metrics, timestamp
                FROM autonomous_logs
                ORDER BY id DESC LIMIT %s;
            """, (safe_limit,))
            rows = cur.fetchall()
            
            results = []
            for row in rows:
                results.append({
                    "goal_id": row[0],
                    "proposal_id": row[1],
                    "status": row[2],
                    "metrics": row[3], # Ya es un dict gracias a Json de psycopg2
                    "timestamp": row[4].isoformat() if row[4] else None
                })
            return results
        finally:
            cur.close()
            conn.close()

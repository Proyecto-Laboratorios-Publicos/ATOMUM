"""
store.py
--------
Gestor de persistencia transaccional para ATOMUM.
Almacena el estado de los objetivos, parches propuestos y métricas de ejecución.
"""

import sqlite3
import pathlib
import json
from typing import Dict, Any, List, Optional

class PersistentStore:
    def __init__(self, db_path: str = "memory/atomum_memory.db"):
        self.db_path = pathlib.Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Inicializa las tablas base para el registro de memoria y automejora."""
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS autonomous_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    goal_id TEXT,
                    proposal_id TEXT,
                    status TEXT,
                    metrics TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def record_execution(self, goal_id: str, proposal_id: str, status: str, metrics: Dict[str, Any]) -> None:
        """Registra el resultado de una iteración del bucle autónomo."""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO autonomous_logs (goal_id, proposal_id, status, metrics)
                VALUES (?, ?, ?, ?)
                """,
                (goal_id, proposal_id, status, json.dumps(metrics))
            )
            conn.commit()

    def get_recent_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Recupera el historial reciente de ejecuciones del bucle."""
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT goal_id, proposal_id, status, metrics, timestamp FROM autonomous_logs ORDER BY id DESC LIMIT ?",
                (limit,)
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

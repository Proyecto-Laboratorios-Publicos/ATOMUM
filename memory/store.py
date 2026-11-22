"""
store.py
--------
Gestor de persistencia transaccional para ATOMUM.
Almacena el estado de los objetivos, parches propuestos y métricas de ejecución.
"""

from contextlib import closing
import json
import logging
import pathlib
import sqlite3
from typing import Any

logger = logging.getLogger(__name__)


class PersistentStore:
    def __init__(self, db_path: str | pathlib.Path = "memory/atomum_memory.db") -> None:
        self.db_path = pathlib.Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_db(self) -> None:
        """Inicializa las tablas base para el registro de memoria y automejora."""
        with closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS autonomous_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        goal_id TEXT,
                        proposal_id TEXT,
                        status TEXT,
                        metrics TEXT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_autonomous_logs_goal_id
                    ON autonomous_logs (goal_id)
                    """
                )

    def record_execution(
        self,
        goal_id: str,
        proposal_id: str,
        status: str,
        metrics: dict[str, Any],
    ) -> None:
        """Registra el resultado de una iteración del bucle autónomo."""
        serialized_metrics = json.dumps(metrics, ensure_ascii=False)
        with closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    """
                    INSERT INTO autonomous_logs (goal_id, proposal_id, status, metrics)
                    VALUES (?, ?, ?, ?)
                    """,
                    (goal_id, proposal_id, status, serialized_metrics),
                )

    def get_recent_history(self, limit: int = 10) -> list[dict[str, Any]]:
        """Recupera el historial reciente de ejecuciones del bucle."""
        safe_limit = max(0, int(limit))
        if safe_limit == 0:
            return []

        with closing(self._connect()) as conn:
            cursor = conn.execute(
                """
                SELECT goal_id, proposal_id, status, metrics, timestamp
                FROM autonomous_logs
                ORDER BY id DESC
                LIMIT ?
                """,
                (safe_limit,),
            )
            rows = cursor.fetchall()

        results: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            raw_metrics = item.get("metrics")
            if isinstance(raw_metrics, str):
                try:
                    item["metrics"] = json.loads(raw_metrics)
                except json.JSONDecodeError:
                    logger.warning("Métricas no JSON en registro de goal_id=%s", item.get("goal_id"))
            results.append(item)
        return results

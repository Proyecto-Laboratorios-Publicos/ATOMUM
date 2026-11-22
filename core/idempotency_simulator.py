"""
idempotency_simulator.py
------------------------
Simula y valida la idempotencia de los parches ejecutando pruebas de
consistencia de estado (hash SHA-256) antes de aplicarlos.
"""

from collections.abc import Callable
import hashlib
import logging
import pathlib
import json
from typing import Any

logger = logging.getLogger(__name__)

StateRunner = Callable[[pathlib.Path], dict[str, Any]]


class IdempotencySimulator:
    """Evalúa si la ejecución repetida de un objetivo produce un estado determinista."""

    def __init__(
        self,
        script_path: str | pathlib.Path,
        runner: StateRunner | None = None,
    ) -> None:
        self.script_path = pathlib.Path(script_path)
        self.runner = runner or self._default_runner

    def _default_runner(self, target: pathlib.Path) -> dict[str, Any]:
        """Simulación controlada determinista basada en el estado del archivo objetivo."""
        if not target.exists():
            return {"target": str(target), "exists": False, "status": "missing"}
        content_hash = hashlib.sha256(target.read_bytes()).hexdigest()
        return {
            "target": str(target),
            "exists": True,
            "content_sha256": content_hash,
            "status": "validated",
        }

    def hash_state(self, state: dict[str, Any]) -> str:
        """Genera un hash SHA-256 normalizado y determinista del estado devuelto."""
        serialized = json.dumps(
            state,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def evaluate(self, runs: int = 3) -> dict[str, Any]:
        """Ejecuta múltiples corridas y devuelve un diagnóstico detallado."""
        if runs < 2:
            raise ValueError("Se requieren al menos 2 ejecuciones (runs >= 2) para validar idempotencia.")

        hashes: list[str] = []
        for _ in range(runs):
            state = self.runner(self.script_path)
            hashes.append(self.hash_state(state))

        unique_hashes = set(hashes)
        is_idempotent = len(unique_hashes) == 1
        return {
            "idempotent": is_idempotent,
            "runs": runs,
            "unique_states": len(unique_hashes),
            "hashes": hashes,
        }

    def simulate(self, runs: int = 3) -> bool:
        """Ejecuta múltiples pruebas y devuelve True solo si todas producen el mismo hash."""
        result = self.evaluate(runs=runs)
        if not result["idempotent"]:
            logger.warning(
                "Inconsistencia de idempotencia detectada en %s (estados únicos: %d)",
                self.script_path,
                result["unique_states"],
            )
        return bool(result["idempotent"])

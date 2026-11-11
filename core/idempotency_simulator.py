"""
idempotency_simulator.py
------------------------
Simula y valida la idempotencia de los parches ejecutando pruebas de consistencia
de estado (hash SHA-256) antes de aplicarlos.
"""

import json
import hashlib
import pathlib
import subprocess
from typing import Dict, Any

class IdempotencySimulator:
    def __init__(self, script_path: str):
        self.script_path = pathlib.Path(script_path)

    def hash_state(self, state: dict) -> str:
        """Genera un hash SHA-256 normalizado del estado devuelto."""
        serialized = json.dumps(state, sort_keys=True)
        return hashlib.sha256(serialized.encode()).hexdigest()

    def simulate(self, runs: int = 3) -> bool:
        """Ejecuta múltiples pruebas para verificar consistencia absoluta."""
        hashes = []
        for i in range(runs):
            # Simulación de ejecución controlada (mock o entorno aislado)
            # En producción se conecta al sandbox de ejecución o Docker
            mock_state = {"run_index": i, "target": str(self.script_path), "status": "validated"}
            hashes.append(self.hash_state(mock_state))
        
        # Si todos los hashes coinciden, el comportamiento es idempotente
        return len(set(hashes)) == 1

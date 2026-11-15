from typing import Any, Dict, List
from atomum.interfaces.planning import Planner

class StubPlanner(Planner):
    """Simulador de planificador cognitivo con pasos predefinidos para pruebas."""

    async def create_plan(self, goal: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not goal:
            return [{"error": "Objetivo vacío en stub"}]

        return [
            {"step": 1, "action": "stub_analyze", "details": f"Analizando objetivo: {goal}"},
            {"step": 2, "action": "stub_execute", "details": "Ejecutando acción simulada en entorno aislado"}
        ]

from typing import Any, Dict, List
from atomum.interfaces.planning import Planner
from atomum.planning.planner import CognitivePlanner

class PlanningService(Planner):
    def __init__(self, planner: Planner | None = None, inference_engine: Any = None):
        self.planner = planner or CognitivePlanner(inference_engine)

    async def create_plan(self, goal: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Orquesta la validación y ejecución de la planificación.
        """
        if not goal:
            return [{"error": "El objetivo (goal) no puede estar vacío."}]
            
        return await self.planner.create_plan(goal, context)

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class Planner(ABC):
    @abstractmethod
    async def create_plan(self, objective: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Crea un plan de ejecución basado en un objetivo y contexto."""
        ...


PlanningService = Planner

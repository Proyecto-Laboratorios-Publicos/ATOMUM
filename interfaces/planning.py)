from abc import ABC, abstractmethod
from typing import Any, Dict, List

class Planner(ABC):
    @abstractmethod
    async def create_plan(self, goal: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Genera un plan de pasos estructurado para alcanzar un objetivo."""
        pass

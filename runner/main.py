# runner/main.py
import asyncio
from typing import Any, Dict
from atomum.inference.service import InferenceService
from atomum.context.service import ContextService
from atomum.planning.service import PlanningService

class AtomumRunner:
    def __init__(self):
        self.context_service = ContextService()
        self.inference_service = InferenceService()
        self.planning_service = PlanningService(inference_engine=self.inference_service)

    async def execute_mission(self, goal: str) -> Dict[str, Any]:
        """
        Ejecuta el ciclo completo: guarda el objetivo en contexto, genera el plan y procesa la inferencia.
        """
        print(f"[*] Iniciando misión en Atomum: '{goal}'")
        
        # 1. Registrar objetivo en el contexto
        await self.context_service.set("current_goal", goal)
        
        # 2. Generar plan de acción
        plan = await self.planning_service.create_plan(goal, {"status": "active"})
        await self.context_service.set("current_plan", plan)
        
        return {
            "goal": goal,
            "status": "planned",
            "plan": plan
        }

if __name__ == "__main__":
    runner = AtomumRunner()
    result = asyncio.run(runner.execute_mission("Optimizar la arquitectura del agente autónomo"))
    print(result)

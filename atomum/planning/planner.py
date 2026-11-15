from typing import Any, Dict, List
from atomum.interfaces.planning import Planner
from atomum.interfaces.inference import InferenceEngine

class CognitivePlanner(Planner):
    def __init__(self, inference_engine: InferenceEngine):
        self.inference_engine = inference_engine

    async def create_plan(self, goal: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Genera un plan estructurado basado en el objetivo y el contexto actual.
        """
        # Aquí estructuramos la directiva para que el LLM devuelva los pasos atómicos
        prompt = f"Dado el objetivo: '{goal}', desglosa un plan de pasos secuenciales en formato JSON."
        
        payload = {
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3
        }
        
        # Ejecuta la inferencia usando el motor desacoplado
        response = await self.inference_engine.run("llama3-70b-8192", payload)
        
        if response.get("status") == "success":
            return [{"step": 1, "action": "parse_goal", "details": response.get("content")}]
        
        return [{"step": 1, "action": "error", "details": "No se pudo generar el plan."}]

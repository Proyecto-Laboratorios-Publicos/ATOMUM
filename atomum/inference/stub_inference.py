from typing import Any, Dict
from atomum.interfaces.inference import InferenceEngine

class StubInferenceClient(InferenceEngine):
    """Simulador de motor de inferencia para pruebas unitarias y de integración sin consumo de API."""

    async def run(self, model_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        messages = payload.get("messages", [])
        last_prompt = messages[-1]["content"] if messages else "sin_contenido"

        return {
            "status": "success",
            "model": f"stub-{model_id}",
            "content": f"[STUB RESPONSE] Procesado correctamente: {last_prompt}",
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 15,
                "total_tokens": 25
            }
        }

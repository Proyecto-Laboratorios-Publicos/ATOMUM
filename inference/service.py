from typing import Any, Dict
from atomum.interfaces.inference import InferenceEngine
from atomum.inference.groq_client import GroqInferenceClient

class InferenceService(InferenceEngine):
    def __init__(self, client: InferenceEngine | None = None):
        # Permite inyectar el cliente (ideal para pruebas con stubs) o usa Groq por defecto
        self.client = client or GroqInferenceClient()

    async def run(self, model_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Orquesta y valida la ejecución de la inferencia a través del motor configurado.
        """
        # Validaciones previas de negocio o sanitización del payload si fuera necesario
        if not model_id:
            return {"status": "error", "error_message": "El parámetro 'model_id' es obligatorio."}
        
        messages = payload.get("messages", [])
        if not messages:
            return {"status": "error", "error_message": "El payload no contiene mensajes para procesar."}

        # Ejecución delegada al cliente subyacente
        result = await self.client.run(model_id, payload)
        return result

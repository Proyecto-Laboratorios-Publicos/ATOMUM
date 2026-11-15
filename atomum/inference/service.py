from typing import Any, Dict
from atomum.interfaces.inference import InferenceEngine
from atomum.inference.groq_client import GroqInferenceClient

class InferenceService(InferenceEngine):
    """
    Servicio de inferencia que orquesta la validación del payload y delega la
    ejecución al cliente subyacente (por defecto GroqInferenceClient). 
    Se garantiza que el payload incluya un límite de tokens suficientemente
    alto (8192) para evitar que las respuestas largas se trunquen.
    """

    def __init__(self, client: InferenceEngine | None = None):
        # Permite inyectar el cliente (ideal para pruebas con stubs) o usa Groq por defecto
        self.client = client or GroqInferenceClient()

    async def run(self, model_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Orquesta y valida la ejecución de la inferencia a través del motor configurado.
        Si el payload no especifica `max_output_tokens` o `max_tokens`, se añaden
        valores por defecto de 8192 para asegurar respuestas completas.
        """
        # Validaciones previas de negocio o sanitización del payload si fuera necesario
        if not model_id:
            return {"status": "error", "error_message": "El parámetro 'model_id' es obligatorio."}
        
        messages = payload.get("messages", [])
        if not messages:
            return {"status": "error", "error_message": "El payload no contiene mensajes para procesar."}

        # --- Ajuste de límite de tokens -------------------------------------------------
        # Groq (y la mayoría de APIs de LLM) aceptan `max_output_tokens` o `max_tokens`.
        # Se prioriza `max_output_tokens` (más explícito). Si el usuario ya lo definió,
        # respetamos su valor; de lo contrario, establecemos un valor por defecto alto.
        DEFAULT_MAX_TOKENS = 8192

        # Caso 1: el payload tiene una clave explícita `max_output_tokens`
        if "max_output_tokens" not in payload:
            # Caso 2: el payload usa la variante `max_tokens`
            if "max_tokens" not in payload:
                # Ninguna de las dos está presente → asignamos la predeterminada
                payload["max_output_tokens"] = DEFAULT_MAX_TOKENS
            else:
                # El usuario ya definió `max_tokens`; nos aseguramos de que sea suficientemente alto
                try:
                    if int(payload["max_tokens"]) < DEFAULT_MAX_TOKENS:
                        payload["max_tokens"] = DEFAULT_MAX_TOKENS
                except (ValueError, TypeError):
                    # Si el valor no es numérico, lo sobrescribimos por seguridad
                    payload["max_tokens"] = DEFAULT_MAX_TOKENS
        # Si `max_output_tokens` está presente pero es menor que el default, lo elevamos.
        else:
            try:
                if int(payload["max_output_tokens"]) < DEFAULT_MAX_TOKENS:
                    payload["max_output_tokens"] = DEFAULT_MAX_TOKENS
            except (ValueError, TypeError):
                payload["max_output_tokens"] = DEFAULT_MAX_TOKENS
        # -------------------------------------------------------------------------------

        # Ejecución delegada al cliente subyacente
        result = await self.client.run(model_id, payload)
        return result

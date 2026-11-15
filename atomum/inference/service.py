import logging
from typing import Any, Dict

from atomum.interfaces.inference import InferenceEngine
from atomum.inference.groq_client import GroqInferenceClient

# Configuración básica del logger del módulo; la aplicación puede reconfigurarlo.
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class InferenceService(InferenceEngine):
    """
    Servicio de inferencia que delega la ejecución al cliente subyacente
    (por defecto GroqInferenceClient). Se ha ampliado el manejo de
    excepciones para capturar fallos de red, límites de cuota y cualquier
    otro error inesperado, registrando información útil para depuración.
    """

    def __init__(self, client: InferenceEngine | None = None):
        # Permite inyectar el cliente (ideal para pruebas con stubs) o usa Groq por defecto
        self.client = client or GroqInferenceClient()

    async def run(self, model_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Orquesta y valida la ejecución de la inferencia a través del motor configurado.
        Fuerza globalmente el uso del modelo activo para evitar llamadas a modelos deprecados.
        """
        from config.settings import settings
        # Forzamos el modelo activo configurado en settings
        active_model = settings.MODEL_Name if hasattr(settings, "MODEL_Name") else settings.MODEL_NAME

        # Validaciones previas de negocio o sanitización del payload si fuera necesario
        if not payload:
            error_msg = "El payload está vacío."
            logger.error(error_msg)
            return {"status": "error", "error_message": error_msg}

        messages = payload.get("messages", [])
        if not messages:
            error_msg = "El payload no contiene mensajes para procesar."
            logger.error(error_msg)
            return {"status": "error", "error_message": error_msg}

        try:
            # Ejecución delegada al cliente subyacente usando el modelo forzado
            result = await self.client.run(active_model, payload)
            return result
        except ConnectionError as exc:
            logger.exception("Error de conexión al intentar ejecutar la inferencia.")
            return {
                "status": "error",
                "error_type": "connection_error",
                "error_message": str(exc) or "Error de conexión al servicio de inferencia.",
            }
        except TimeoutError as exc:
            logger.exception("Timeout al ejecutar la inferencia.")
            return {
                "status": "error",
                "error_type": "timeout",
                "error_message": str(exc) or "La solicitud de inferencia excedió el tiempo máximo permitido.",
            }
        except RuntimeError as exc:
            logger.exception("Error de runtime al ejecutar la inferencia.")
            return {
                "status": "error",
                "error_type": "runtime_error",
                "error_message": str(exc) or "Error interno del motor de inferencia.",
            }
        except Exception as exc:
            logger.exception("Error inesperado durante la inferencia.")
            return {
                "status": "error",
                "error_type": "unknown_error",
                "error_message": str(exc) or "Error desconocido al procesar la inferencia.",
            }

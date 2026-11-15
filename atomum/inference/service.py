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
        Devuelve un diccionario con el resultado o con información estructurada de error.
        """
        # Validaciones previas de negocio o sanitización del payload si fuera necesario
        if not model_id:
            error_msg = "El parámetro 'model_id' es obligatorio."
            logger.error(error_msg)
            return {"status": "error", "error_message": error_msg}

        messages = payload.get("messages", [])
        if not messages:
            error_msg = "El payload no contiene mensajes para procesar."
            logger.error(error_msg)
            return {"status": "error", "error_message": error_msg}

        try:
            # Ejecución delegada al cliente subyacente
            result = await self.client.run(model_id, payload)
            return result
        except ConnectionError as exc:
            # Fallos de red o de conexión al endpoint de Groq
            logger.exception("Error de conexión al intentar ejecutar la inferencia.")
            return {
                "status": "error",
                "error_type": "connection_error",
                "error_message": str(exc) or "Error de conexión al servicio de inferencia.",
            }
        except TimeoutError as exc:
            # Tiempo de espera excedido
            logger.exception("Timeout al ejecutar la inferencia.")
            return {
                "status": "error",
                "error_type": "timeout",
                "error_message": str(exc) or "La solicitud de inferencia excedió el tiempo máximo permitido.",
            }
        except RuntimeError as exc:
            # Posibles errores específicos de la API de Groq (p.ej., límite de cuota)
            logger.exception("Error de runtime al ejecutar la inferencia.")
            return {
                "status": "error",
                "error_type": "runtime_error",
                "error_message": str(exc) or "Error interno del motor de inferencia.",
            }
        except Exception as exc:
            # Captura genérica para cualquier otro problema inesperado
            logger.exception("Error inesperado durante la inferencia.")
            return {
                "status": "error",
                "error_type": "unknown_error",
                "error_message": str(exc) or "Error desconocido al procesar la inferencia.",
            }

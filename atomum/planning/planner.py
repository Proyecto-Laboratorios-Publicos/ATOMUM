from __future__ import annotations

from typing import Any, Dict, List, TypedDict

from atomum.interfaces.planner import Planner
from atomum.interfaces.inference import InferenceEngine


class Step(TypedDict, total=False):
    """Representa un paso individual del plan generado."""

    step: int
    action: str
    details: Any


class PlanGenerationError(Exception):
    """Excepción lanzada cuando no se puede generar un plan válido."""

    def __init__(self, message: str, *, cause: Exception | None = None) -> None:
        super().__init__(message)
        self.__cause__ = cause


class CognitivePlanner(Planner):
    """
    Implementación de :class:`atomum.interfaces.planning.Planner` que delega
    la generación de planes a un motor de inferencia LLM.

    Parameters
    ----------
    inference_engine: InferenceEngine
        Instancia del motor de inferencia desacoplado que ejecuta peticiones
        contra el modelo LLM.

    Notes
    -----
    La clase es completamente asíncrona; el método :meth:`create_plan` debe
    invocarse dentro de un bucle de eventos ``asyncio``.
    """

    def __init__(self, inference_engine: InferenceEngine) -> None:
        self.inference_engine = inference_engine

    async def create_plan(self, goal: str, context: Dict[str, Any]) -> List[Step]:
        """
        Genera un plan estructurado basado en el objetivo y el contexto actual.

        Parameters
        ----------
        goal: str
            Descripción del objetivo que se desea alcanzar.
        context: Dict[str, Any]
            Información adicional que puede influir en la generación del plan.

        Returns
        -------
        List[Step]
            Lista de pasos del plan. Cada paso es un diccionario con las claves
            ``step``, ``action`` y ``details``.

        Raises
        ------
        PlanGenerationError
            Si la llamada al motor de inferencia falla o la respuesta no contiene
            los datos esperados.
        """
        # Construcción del prompt para el LLM
        prompt: str = (
            f"Dado el objetivo: '{goal}', desglosa un plan de pasos secuenciales "
            "en formato JSON."
        )
        payload: Dict[str, Any] = {
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
        }

        try:
            response: Dict[str, Any] = await self.inference_engine.run(
                "openai/gpt-oss-120b", payload
            )
        except Exception as exc:  # pylint: disable=broad-except
            raise PlanGenerationError(
                "Error al ejecutar la inferencia del motor LLM.", cause=exc
            ) from exc

        # Validación de la respuesta del motor
        if not isinstance(response, dict):
            raise PlanGenerationError("Respuesta del motor LLM no es un diccionario.")

        status: str | None = response.get("status")
        content: Any = response.get("content")

        if status == "success" and content is not None:
            return [
                Step(step=1, action="parse_goal", details=content)  # type: ignore[arg-type]
            ]

        error_detail: str = (
            f"Respuesta inesperada del motor LLM: {response!r}"
            if response
            else "Respuesta vacía del motor LLM."
        )
        raise PlanGenerationError(error_detail)

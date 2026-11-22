import os
from typing import Any, Dict

from groq import Groq

from atomum.interfaces.inference import InferenceEngine
from config.settings import settings


class GroqInferenceClient(InferenceEngine):
    def __init__(self, api_key: str | None = None):
        # Utiliza la API key pasada por parámetro o la toma del entorno de forma segura
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("La variable de entorno GROQ_API_KEY no está configurada.")
        self.client = Groq(api_key=self.api_key)

    async def run(self, model_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Ejecuta la inferencia contra el modelo de Groq utilizando los parámetros del payload.
        Fuerza la mitigación de modelos deprecados reemplazándolos por el activo en settings.
        """
        try:
            # Blindaje absoluto: si entra un modelo viejo o vacío, forzamos el de settings
            active_model = settings.MODEL_NAME
            if not model_id or "llama3-70b" in model_id or "mixtral" in model_id:
                model_id = active_model

            messages = payload.get("messages", [])
            temperature = float(payload.get("temperature", 0.1))
            max_tokens = int(payload.get("max_tokens", 16384))

            # Llamada al SDK oficial de Groq con el modelo blindado
            chat_completion = self.client.chat.completions.create(
                model=model_id,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            choice = chat_completion.choices[0] if chat_completion.choices else None
            content = (choice.message.content or "") if choice and choice.message else ""
            finish_reason = getattr(choice, "finish_reason", None)

            usage_obj = getattr(chat_completion, "usage", None)
            usage = {
                "prompt_tokens": getattr(usage_obj, "prompt_tokens", None),
                "completion_tokens": getattr(usage_obj, "completion_tokens", None),
                "total_tokens": getattr(usage_obj, "total_tokens", None),
            }

            return {
                "status": "success",
                "model": model_id,
                "content": content,
                "finish_reason": finish_reason,
                "usage": usage,
            }
        except Exception as e:
            return {"status": "error", "error_message": str(e)}

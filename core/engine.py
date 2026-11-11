"""
Motor Cognitivo Principal de ATOMUM (AtomumEngine).
Orquesta la seguridad, las llamadas al modelo cognitivo de Groq y la ejecución concurrente.
"""

import os
import sys
import asyncio
import logging
from typing import List, Dict, Any, Optional

# Asegurar rutas absolutas exactas antes de cualquier importación interna
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from config.settings import settings
from core.guardrails import Guardrails
from core.http_client import AsyncHttpClient
from groq import Groq

# Configurar logging centralizado
log = logging.getLogger(__name__)

class AtomumEngine:
    def __init__(self, concurrency_limit: int = 20):
        self.guardrails = Guardrails()
        self.is_active = True
        
        # Obtener claves y configuraciones de forma segura desde Pydantic (settings)
        self.api_key = settings.GROQ_API_KEY.get_secret_value() if settings.GROQ_API_KEY else None
        self.model_name = settings.MODEL_NAME

        # Instanciar el cliente HTTP asíncrono optimizado
        self.http_client = AsyncHttpClient(
            max_connections=100,
            max_concurrency=concurrency_limit,
            timeout=30.0,
            retry_attempts=3
        )
        
        # Semáforo para control estricto de concurrencia en tareas masivas
        self.semaphore = asyncio.Semaphore(concurrency_limit)

        # Inicializar el cliente oficial de Groq de manera segura
        if self.api_key:
            try:
                self.client = Groq(api_key=self.api_key)
                log.info("🧠 [Engine] Cliente oficial de Groq inicializado con éxito mediante configuración segura.")
            except Exception as e:
                self.client = None
                log.error(f"❌ [Engine Error] No se pudo inicializar el cliente de Groq: {e}")
        else:
            self.client = None
            log.warning("⚠️ [Engine] Advertencia: No se encontró API Key de Groq configurada en Settings.")

    def process_instruction(self, instruction: str) -> str:
        """Procesa una instrucción de manera síncrona asegurando validaciones estrictas."""
        if not instruction or not isinstance(instruction, str):
            return "⚠️ [Engine] Directiva vacía o inválida recibida."
            
        cleaned_instruction = instruction.strip()
        log.info(f"⚙️ [Engine] Procesando directiva: '{cleaned_instruction}'")

        # 1. Validación estricta con los guardarraíses constitucionales (AST)
        if not self.guardrails.validate_action(cleaned_instruction):
            return "🚫 [Engine] Ejecución denegada por los guardarraíses de seguridad suprema."

        # 2. Conexión con la API Cognitiva mediante el SDK oficial
        if self.client:
            try:
                completion = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {
                            "role": "system",
                            "content": "Actúas como el núcleo cognitivo autónomo de ATOMUM. Responde de forma directa, técnica y analítica estructurando código y soluciones robustas."
                        },
                        {
                            "role": "user",
                            "content": cleaned_instruction
                        }
                    ],
                    temperature=0.2,
                    max_tokens=settings.MAX_TOKENS
                )
                ai_response = completion.choices[0].message.content
                return ai_response
            except Exception as e:
                log.error(f"❌ [Engine] Fallo en la llamada al SDK de Groq: {e}")
                return f"❌ [Engine] Fallo en la llamada al SDK de Groq: {e}"
        else:
            return "🧠 [Engine] Modo Autónomo Local: Falta configurar la API Key de Groq en las variables de entorno o secretos."

    async def _worker(self, task_id: str, payload_func: Any) -> Any:
        """Worker individual controlado por semáforo para ejecución concurrente."""
        async with self.semaphore:
            try:
                log.info(f"🔄 [AsyncWorker] Iniciando tarea {task_id}")
                result = await payload_func()
                log.info(f"✅ [AsyncWorker] Tarea {task_id} completada con éxito.")
                return result
            except Exception as e:
                log.error(f"❌ [AsyncWorker] Error en tarea {task_id}: {e}")
                raise

    async def run_concurrent_tasks(self, tasks_data: List[Dict[str, Any]], coro_callback: Any) -> List[Any]:
        """Orquesta la ejecución concurrente masiva de múltiples tareas usando asyncio.gather."""
        tasks = [
            asyncio.create_task(self._worker(item.get("id", str(i)), lambda item=item: coro_callback(item)))
            for i, item in enumerate(tasks_data)
        ]
        return await asyncio.gather(*tasks, return_exceptions=True)

    async def close(self):
        await self.http_client.close()

if __name__ == "__main__":
    engine = AtomumEngine()
    print(engine.process_instruction("estado del sistema"))

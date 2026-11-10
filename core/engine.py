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

from core.guardrails import Guardrails
from core.http_client import AsyncHttpClient
from groq import Groq

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger(__name__)

class AtomumEngine:
    def __init__(self, concurrency_limit: int = 20):
        self.guardrails = Guardrails()
        self.is_active = True
        self.api_key = os.getenv("ATOMUM_LLM_API_KEY") or os.getenv("GROQ_API_KEY")
        self.model_name = os.getenv("ATOMUM_LLM_MODEL", "openai/gpt-oss-120b")
        
        # Instanciar el cliente HTTP asíncrono optimizado
        self.http_client = AsyncHttpClient(
            max_connections=100,
            max_concurrency=concurrency_limit,
            timeout=30.0,
            retry_attempts=3
        )
        
        # Semáforo para control estricto de concurrencia en tareas masivas
        self.semaphore = asyncio.Semaphore(concurrency_limit)
        
        # Inicializar el cliente oficial de Groq
        if self.api_key:
            try:
                self.client = Groq(api_key=self.api_key)
                log.info("🧠 [Engine] Cliente oficial de Groq inicializado con éxito.")
            except Exception as e:
                self.client = None
                log.error(f"❌ [Engine Error] No se pudo inicializar el cliente de Groq: {e}")
        else:
            self.client = None
            log.warning("⚠️ [Engine] Advertencia: No se encontró API Key de Groq configurada.")

    def process_instruction(self, instruction: str) -> str:
        """Procesa una instrucción de manera síncrona (para compatibilidad con Streamlit)."""
        if not instruction or not isinstance(instruction, str):
            return "⚠️ [Engine] Directiva vacía o inválida recibida."
            
        cleaned_instruction = instruction.strip()
        log.info(f"⚙️ [Engine] Procesando directiva: '{cleaned_instruction}'")
        
        # 1. Validación estricta con los guardarraíses
        if not self.guardrails.validate_action(cleaned_instruction):
            return "🚫 [Engine] Ejecución denegada por los guardarraíses de seguridad suprema."
            
        # 2. Control de patrones destructivos
        dangerous_patterns = ["rm -rf", "sudo", "shutdown", "mkfs", "dd if="]
        if any(pattern in cleaned_instruction.lower() for pattern in dangerous_patterns):
            return "🛡️ [Engine] Alerta de seguridad: Patrón destructivo bloqueado por el motor."
            
        # 3. Conexión con la API Cognitiva mediante el SDK oficial
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
                    max_tokens=8192
                )
                ai_response = completion.choices[0].message.content
                return ai_response
            except Exception as e:
                return f"❌ [Engine] Fallo en la llamada al SDK de Groq: {e}"
        else:
            return "🧠 [Engine] Modo Autónomo Local: Falta configurar la API Key de Groq en los secretos de Streamlit."

    async def _worker(self, task_id: str, payload_func: Any) -> Any:
        """Worker individual controlado por semáforo para ejecución concurrente."""
        async with self.semaphore:
            try:
                log.info(f"🔄 [AsyncWorker] Iniciando tarea {task_id}")
                # Ejecución de la tarea asíncrona inyectada
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
        # Ejecutar en paralelo esperando resultados o propagando excepciones controladas
        return await asyncio.gather(*tasks, return_exceptions=True)

    async def close(self):
        await self.http_client.close()

if __name__ == "__main__":
    engine = AtomumEngine()
    print(engine.process_instruction("estado del sistema"))

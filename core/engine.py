"""
Motor Cognitivo Principal de ATOMUM (AtomumEngine).
Orquesta la seguridad, las llamadas al modelo cognitivo de Groq y la ejecución aislada.
"""

import os
import sys
import asyncio
import logging
import multiprocessing
from typing import List, Dict, Any, Optional

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from config.settings import settings
from core.logger import get_logger
from core.guardrails import Guardrails, validate_user_code, GuardrailViolation
from core.http_client import AsyncHttpClient
from groq import Groq

log = get_logger("atomum.engine")

def _isolated_execution_worker(source_code: str, conn):
    """Función que se ejecuta en un proceso hijo aislado para evitar riesgos en el proceso principal."""
    try:
        # Validación estricta con AST antes de ejecutar
        validate_user_code(source_code)
        
        # Diccionario local de ejecución controlado
        local_scope = {}
        exec(source_code, {"__builtins__": {}}, local_scope)
        conn.send(("SUCCESS", local_scope.get("result", "Ejecución completada sin retorno explícito")))
    except Exception as e:
        conn.send(("ERROR", str(e)))
    finally:
        conn.close()

class AtomumEngine:
    def __init__(self, concurrency_limit: int = 20):
        self.guardrails = Guardrails()
        self.is_active = True
        
        self.api_key = settings.GROQ_API_KEY.get_secret_value() if settings.GROQ_API_KEY else None
        self.model_name = settings.MODEL_NAME

        self.http_client = AsyncHttpClient(
            max_connections=100,
            max_concurrency=concurrency_limit,
            timeout=30.0,
            retry_attempts=3
        )
        self.semaphore = asyncio.Semaphore(concurrency_limit)

        if self.api_key:
            try:
                self.client = Groq(api_key=self.api_key)
                log.info("Cliente oficial de Groq inicializado con éxito.")
            except Exception as e:
                self.client = None
                log.error(f"No se pudo inicializar el cliente de Groq: {e}")
        else:
            self.client = None
            log.warning("No se encontró API Key de Groq configurada en Settings (Modo Local).")

    def execute_code_safely(self, source_code: str, timeout: float = 5.0) -> Any:
        """Ejecuta código de manera aislada utilizando un proceso hijo con control de tiempo límite."""
        parent_conn, child_conn = multiprocessing.Pipe()
        
        # Forzar método 'spawn' para compatibilidad total y aislamiento limpio
        ctx = multiprocessing.get_context('spawn')
        p = ctx.Process(target=_isolated_execution_worker, args=(source_code, child_conn))
        p.start()
        
        # Esperar respuesta con timeout estricto para evitar bloqueos / DoS
        if parent_conn.poll(timeout):
            status, result = parent_conn.recv()
            p.join()
            if status == "ERROR":
                raise RuntimeError(f"Error en ejecución aislada: {result}")
            return result
        else:
            p.terminate()
            p.join()
            raise TimeoutError("La ejecución excedió el tiempo límite permitido.")

    def process_instruction(self, instruction: str) -> str:
        if not instruction or not isinstance(instruction, str):
            return "Directiva vacía o inválida recibida."
            
        cleaned_instruction = instruction.strip()
        log.info(f"Procesando directiva: '{cleaned_instruction}'")

        if not self.guardrails.validate_action(cleaned_instruction):
            return "Ejecución denegada por los guardarraíses de seguridad."

        if self.client:
            try:
                completion = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {
                            "role": "system",
                            "content": "Actúas como el núcleo cognitivo autónomo de ATOMUM. Responde de forma directa, técnica y analítica."
                        },
                        {
                            "role": "user",
                            "content": cleaned_instruction
                        }
                    ],
                    temperature=0.2,
                    max_tokens=settings.MAX_TOKENS
                )
                return completion.choices[0].message.content
            except Exception as e:
                log.error(f"Fallo en la llamada al SDK de Groq: {e}")
                return f"Fallo en la llamada al SDK de Groq: {e}"
        else:
            return "Modo Autónomo Local: Falta configurar la API Key de Groq."

    async def close(self):
        await self.http_client.close()

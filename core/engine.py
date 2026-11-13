"""
Motor Cognitivo Principal de ATOMUM (AtomumEngine).
Orquesta la seguridad, las llamadas al modelo cognitivo de Groq y la ejecución aislada.
"""

import os
import sys
import asyncio
import logging
import multiprocessing
import logging
from typing import List, Dict, Any, Optional
from typing import List, Dict, Any

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




log = logging.getLogger(__name__)

# Umbrales de severidad que disparan alerta
ALERT_SEVERITIES = {"CRITICAL", "HIGH"}

def _flatten_findings(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Convierte la estructura anidada del JSON (p.ej. por archivo) en una lista plana.
    Se asume que el formato del analyzer sigue la convención:
    {
        "results": [
            {
                "file": "src/module.py",
                "issues": [
                    {"id": "S001", "title": "...", "severity": "CRITICAL", ...},
                    ...
                ]
            },
            ...
        ]
    }
    """
    flat = []
    for entry in report.get("results", []):
        file_path = entry.get("file", "")
        for issue in entry.get("issues", []):
            issue_copy = issue.copy()
            issue_copy["file"] = file_path
            flat.append(issue_copy)
    return flat


def process_security_report(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Analiza el JSON del escáner y devuelve una lista de hallazgos que superan
    los umbrales definidos (CRITICAL / HIGH). Además, envía los datos al motor
    cognitivo de Groq (si está configurado) para enriquecer la información.

    Returns
    -------
    alerts : list[dict]
        Cada dict contiene al menos: id, title, severity, file, line (si disponible)
    """
    flat_findings = _flatten_findings(report)

    alerts = [f for f in flat_findings if f.get("severity") in ALERT_SEVERITIES]

    # ------------------------------------------------------------------
    # Integración opcional con Groq (cognitivo) – se ejecuta solo si la
    # variable de entorno GROQ_API_KEY está presente.
    # ------------------------------------------------------------------
    import os
    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key and alerts:
        try:
            from groq import Groq  # pip install groq
            client = Groq(api_key=groq_key)

            # Construir prompt que describa los hallazgos críticos
            prompt = "You are a security analyst. For each of the following findings, provide a concise remediation recommendation (max 2 sentences).\n\n"
            for i, a in enumerate(alerts, 1):
                prompt += f"{i}. [{a['severity']}] {a['id']} in {a['file']}: {a['title']}\n"

            response = client.chat.completions.create(
                model="mixtral-8x7b-32768",  # ejemplo de modelo Groq
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=1024,
            )
            # Parsear la respuesta (asumimos una lista numerada)
            recommendations = response.choices[0].message.content.strip().splitlines()
            for rec, alert in zip(recommendations, alerts):
                alert["remediation"] = rec.partition(".")[2].strip()
        except Exception as e:
            log.warning(f"Integración con Groq falló: {e}")

    # ------------------------------------------------------------------
    # Registro de alertas en el motor interno (p.ej. base de datos, eventos)
    # ------------------------------------------------------------------
    # Aquí se podría insertar en una tabla `security_events` o publicar en un
    # bus de eventos (Kafka, RabbitMQ). Se deja como placeholder.
    # ------------------------------------------------------------------

    return alerts

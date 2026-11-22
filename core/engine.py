"""
Motor Cognitivo Principal de ATOMUM (AtomumEngine).
Orquesta la seguridad, las llamadas al modelo cognitivo de Groq, la ejecución aislada,
la gobernanza de alcance/parada de emergencia y los sobres de evidencia auditable.
"""

import asyncio
import logging
import multiprocessing
import os
import sys
from typing import Any, Callable, Dict, List, Optional

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from groq import Groq

from config.settings import settings
from core.guardrails import Guardrails, GuardrailViolation, validate_user_code
from core.http_client import AsyncHttpClient
from core.logger import get_logger

try:
    from core.governance import (
        ActionImpact,
        AuditFindingEnvelope,
        GovernanceController,
        GovernanceDecision,
        LLMTriage,
        ScopePolicy,
        ValidatedEvidence,
    )

    _HAS_GOVERNANCE = True
except ImportError:
    _HAS_GOVERNANCE = False

log = get_logger("atomum.engine")


def _isolated_execution_worker(source_code: str, conn) -> None:
    """Función que se ejecuta en un proceso hijo aislado para evitar riesgos en el proceso principal."""
    try:
        # Validación estricta con AST antes de ejecutar
        validate_user_code(source_code)
        # Diccionario local de ejecución controlado
        local_scope: Dict[str, Any] = {}
        exec(source_code, {"__builtins__": {}}, local_scope)
        conn.send(
            (
                "SUCCESS",
                local_scope.get("result", "Ejecución completada sin retorno explícito"),
            )
        )
    except Exception as e:
        conn.send(("ERROR", str(e)))
    finally:
        conn.close()


class AtomumEngine:
    """Núcleo cognitivo y de ejecución segura de ATOMUM."""

    def __init__(
        self,
        concurrency_limit: int = 20,
        scope_policy: Optional[Any] = None,
        approval_callback: Optional[Callable[[Any], bool]] = None,
    ) -> None:
        self.guardrails = Guardrails()
        self.is_active = True
        self.api_key = (
            settings.GROQ_API_KEY.get_secret_value()
            if getattr(settings, "GROQ_API_KEY", None)
            else None
        )
        # Blindaje del modelo activo
        self.model_name = settings.MODEL_NAME
        self.http_client = AsyncHttpClient(
            max_connections=100,
            max_concurrency=concurrency_limit,
            timeout=30.0,
            retry_attempts=3,
        )
        self.semaphore = asyncio.Semaphore(concurrency_limit)
        self.approval_callback = approval_callback

        if _HAS_GOVERNANCE:
            policy = scope_policy if scope_policy is not None else ScopePolicy()
            self.governance: Optional[GovernanceController] = GovernanceController(policy)
        else:
            self.governance = None

        if self.api_key:
            try:
                self.client: Optional[Groq] = Groq(api_key=self.api_key)
                log.info("Cliente oficial de Groq inicializado con éxito.")
            except Exception as e:
                self.client = None
                log.error(f"No se pudo inicializar el cliente de Groq: {e}")
        else:
            self.client = None
            log.warning("No se encontró API Key de Groq configurada en Settings (Modo Local).")

    def execute_code_safely(self, source_code: str, timeout: float = 5.0) -> Any:
        """Ejecuta código de manera aislada utilizando un proceso hijo con control de tiempo límite."""
        if self.governance and self.governance.emergency_stop.is_triggered:
            raise RuntimeError(
                f"Ejecución bloqueada por EmergencyStop: {self.governance.emergency_stop.status.get('reason')}"
            )

        parent_conn, child_conn = multiprocessing.Pipe()
        # Forzar método 'spawn' para compatibilidad total y aislamiento limpio
        ctx = multiprocessing.get_context("spawn")
        p = ctx.Process(
            target=_isolated_execution_worker, args=(source_code, child_conn)
        )
        p.start()

        # Esperar respuesta con timeout estricto para evitar bloqueos / DoS
        if parent_conn.poll(timeout):
            status, result = parent_conn.recv()
            p.join()
            if self.governance:
                self.governance.emergency_stop.record_error(is_error=(status == "ERROR"))
            if status == "ERROR":
                raise RuntimeError(f"Error en ejecución aislada: {result}")
            return result

        p.terminate()
        p.join()
        if self.governance:
            self.governance.emergency_stop.record_error(is_error=True)
        raise TimeoutError("La ejecución excedió el tiempo límite permitido.")

    def process_instruction(self, instruction: str) -> str:
        """Procesa una directiva técnica aplicando guardarraíses, control de parada y modelo activo."""
        if not instruction or not isinstance(instruction, str):
            return "Directiva vacía o inválida recibida."

        cleaned_instruction = instruction.strip()
        log.info(f"Procesando directiva: '{cleaned_instruction}'")

        if self.governance and self.governance.emergency_stop.is_triggered:
            reason = self.governance.emergency_stop.status.get("reason") or "Parada activa"
            return f"Ejecución detenida por EmergencyStop: {reason}"

        if self.governance:
            injection_hit = self.governance.emergency_stop.inspect_text_for_injection(
                cleaned_instruction
            )
            if injection_hit:
                return f"Ejecución detenida por señal de inyección/override: {injection_hit}"

            self.governance.emergency_stop.record_step()
            if self.governance.emergency_stop.is_triggered:
                reason = self.governance.emergency_stop.status.get("reason") or "Límite excedido"
                return f"Ejecución detenida por EmergencyStop: {reason}"

        if not self.guardrails.validate_action(cleaned_instruction):
            return "Ejecución denegada por los guardarraíses de seguridad."

        if self.client:
            try:
                active_model = settings.MODEL_NAME
                completion = self.client.chat.completions.create(
                    model=active_model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "Actúas como el núcleo cognitivo autónomo de ATOMUM. "
                                "Responde de forma directa, técnica y analítica."
                            ),
                        },
                        {"role": "user", "content": cleaned_instruction},
                    ],
                    temperature=0.2,
                    max_tokens=settings.MAX_TOKENS,
                )
                if self.governance:
                    self.governance.emergency_stop.record_error(is_error=False)
                return completion.choices[0].message.content
            except Exception as e:
                if self.governance:
                    self.governance.emergency_stop.record_error(is_error=True)
                log.error(f"Fallo en la llamada al SDK de Groq: {e}")
                return f"Fallo en la llamada al SDK de Groq: {e}"

        return "Modo Autónomo Local: Falta configurar la API Key de Groq."

    def build_finding_envelope(
        self,
        source_tool: str,
        target: str,
        observed_data: Dict[str, Any],
        raw_excerpt: Optional[str] = None,
        port: Optional[int] = None,
        protocol: Optional[str] = None,
        scope_verified: bool = True,
        triage_summary: Optional[str] = None,
        risk_priority: str = "info",
    ) -> Optional[Any]:
        """Construye un sobre auditable separando evidencia técnica observada de triaje LLM."""
        if not _HAS_GOVERNANCE:
            return {
                "scope_verified": scope_verified,
                "validated_evidence": {
                    "source_tool": source_tool,
                    "target": target,
                    "port": port,
                    "protocol": protocol,
                    "observed_data": observed_data,
                    "raw_excerpt": raw_excerpt,
                },
                "llm_triage": None,
            }

        if raw_excerpt:
            self.governance.emergency_stop.inspect_text_for_injection(raw_excerpt) if self.governance else None

        evidence = ValidatedEvidence(
            source_tool=source_tool,
            target=target,
            port=port,
            protocol=protocol,
            observed_data=observed_data,
            raw_excerpt=raw_excerpt,
        )

        triage: Optional[LLMTriage] = None
        if triage_summary:
            valid_priorities = {"info", "low", "medium", "high", "critical"}
            norm_prio = risk_priority.lower() if risk_priority.lower() in valid_priorities else "info"
            triage = LLMTriage(
                model_name=self.model_name,
                summary=triage_summary,
                rationale="Hipótesis generada a partir de evidencia observada; verificar en contexto.",
                recommended_next_step="Validar hallazgo y correlacionar con base CPE/CBOM.",
            )
            triage.risk_priority = norm_prio  # type: ignore[assignment]

        return AuditFindingEnvelope(
            scope_verified=scope_verified,
            validated_evidence=evidence,
            llm_triage=triage,
        )

    async def close(self) -> None:
        """Cierra recursos asíncronos abiertos por el motor."""
        await self.http_client.close()


# Umbrales de severidad que disparan alerta
ALERT_SEVERITIES = {"CRITICAL", "HIGH"}


def _flatten_findings(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Convierte la estructura anidada del JSON (p.ej. por archivo) en una lista plana."""
    flat: List[Dict[str, Any]] = []
    for entry in report.get("results", []):
        file_path = entry.get("file", "")
        for issue in entry.get("issues", []):
            issue_copy = issue.copy()
            issue_copy["file"] = file_path
            flat.append(issue_copy)
    return flat


def process_security_report(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Analiza el JSON del escáner y devuelve una lista de hallazgos que superan los umbrales
    definidos (CRITICAL / HIGH). Además, envía los datos al motor cognitivo de Groq
    utilizando siempre el modelo activo en settings.
    """
    flat_findings = _flatten_findings(report)
    alerts = [f for f in flat_findings if f.get("severity") in ALERT_SEVERITIES]

    # Integración opcional con Groq (cognitivo)
    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key and alerts:
        try:
            client = Groq(api_key=groq_key)
            prompt = (
                "You are a security analyst. For each of the following findings, "
                "provide a concise remediation recommendation (max 2 sentences).\n\n"
            )
            for i, a in enumerate(alerts, 1):
                prompt += (
                    f"{i}. [{a['severity']}] {a['id']} in {a['file']}: {a['title']}\n"
                )

            # Blindaje absoluto del modelo en el análisis de seguridad
            active_security_model = settings.MODEL_NAME
            response = client.chat.completions.create(
                model=active_security_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=1024,
            )
            content = response.choices[0].message.content or ""
            recommendations = content.strip().splitlines()
            for rec, alert in zip(recommendations, alerts):
                alert["remediation"] = rec.partition(".")[2].strip() or rec.strip()
        except Exception as e:
            log.warning(f"Integración con Groq falló: {e}")

    return alerts

"""
runner.py
---------
Orquestador principal del ciclo de auto-mejora autónoma de ATOMUM.
"""

import ast
import asyncio
from datetime import datetime, timezone
import json
import logging
import os
import re
import sys
from typing import Any, Callable, Dict, Optional

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from atomum.context.service import ContextService
from atomum.inference.service import InferenceService
from atomum.inference.stub_inference import StubInferenceClient
from core.governance import ActionImpact, GovernanceController, ScopePolicy
from skills.file_tools import FileTools
from skills.git_ops import GitOperations
from skills.system_tools import SystemTools

try:
    from core.guardrails import validate_user_code
except Exception:
    validate_user_code = None

logger = logging.getLogger("atomum.runner")
logging.basicConfig(level=logging.INFO)


class AutonomousRunner:
    """Orquestador encargado de ejecutar ciclos autónomos de mejora y apertura de PRs."""

    def __init__(
        self,
        repo_slug: str = "Proyecto-Laboratorios-Publicos/ATOMUM",
        governance: Optional[GovernanceController] = None,
        pr_approval_callback: Optional[Callable[[Any], bool]] = None,
    ) -> None:
        self.repo_slug = repo_slug
        self.context = ContextService()
        self.files = FileTools(base_dir=".")
        self.system = SystemTools()
        self.git_ops = GitOperations(repo_path=".")
        self.governance = governance or GovernanceController(
            ScopePolicy(allowed_domains=["github.com", repo_slug])
        )
        self.pr_approval_callback = pr_approval_callback

        api_key = os.getenv("GROQ_API_KEY", "")
        if api_key and api_key != "test_stub_key":
            self.inference = InferenceService()
        else:
            self.inference = InferenceService(client=StubInferenceClient())

        # Blindaje preventivo: Forzar modelo moderno
        raw_model = os.getenv("ATOMUM_LLM_MODEL", "openai/gpt-oss-120b")
        if "llama3-70b-8192" in raw_model:
            logger.warning(
                "⚠️ [Runner] Detectado modelo deprecado en entorno. Forzando a 'openai/gpt-oss-120b'."
            )
            raw_model = "openai/gpt-oss-120b"
        self.model_id = raw_model

    @staticmethod
    def _parse_proposal_response(raw_text: str, target_file: str, default_goal: str) -> dict:
        title_match = re.search(r"^TITLE:\s*(.+)$", raw_text, re.MULTILINE)
        summary_match = re.search(r"^SUMMARY:\s*(.+)$", raw_text, re.MULTILINE)
        code_match = re.search(
            r"```(?:python)?\s*\n(.*?)(?:\n\s*```|$)",
            raw_text,
            re.DOTALL,
        )
        if not code_match or not code_match.group(1).strip():
            raise ValueError("No se encontró código Python válido en la respuesta del modelo.")

        title = (
            title_match.group(1).strip()
            if title_match
            else f"chore(atomum): mejora autónoma en {target_file}"
        )
        summary = summary_match.group(1).strip() if summary_match else default_goal
        updated_code = code_match.group(1).strip() + "\n"
        return {
            "title": title,
            "summary": summary,
            "updated_code": updated_code,
        }

    @staticmethod
    def _validate_candidate_code(code: str) -> tuple[bool, Optional[str]]:
        if validate_user_code is not None:
            try:
                validate_user_code(code)
            except Exception as exc:
                return False, f"Guardrail/AST rechazó el código: {exc}"
        try:
            ast.parse(code)
            return True, None
        except SyntaxError as syn_err:
            return False, f"Validación AST fallida: {syn_err}"

    @staticmethod
    def _pytest_failed(test_output: str) -> bool:
        lowered = (test_output or "").lower()
        return bool(
            re.search(r"\b\d+\s+failed\b", lowered)
            or re.search(r"\b\d+\s+error\b", lowered)
            or "traceback (most recent call last)" in lowered
            or "no module named pytest" in lowered
            or "timed out" in lowered
        )

    async def _request_code_proposal(
        self,
        target_file: str,
        goal: str,
        original_code: str,
        tasks_data: dict,
        repair_hint: Optional[str] = None,
    ) -> dict:
        system_prompt = (
            "Eres el núcleo de ingeniería autónoma de ATOMUM. "
            "Aplica cambios mínimos, limpios y quirúrgicos al archivo Python para cumplir el objetivo "
            "sin reescribir innecesariamente bloques intactos ni agregar texto de relleno. "
            "Responde ESTRICTAMENTE con este formato:\n"
            "TITLE: <título corto>\n"
            "SUMMARY: <resumen técnico en una línea>\n"
            "```python\n"
            "<código Python completo y sintácticamente válido>\n"
            "```\n"
            "Mantén 100% de retrocompatibilidad y asegúrate de cerrar todas las estructuras y bloques."
        )
        compact_tasks = json.dumps(tasks_data, ensure_ascii=False)[:800]
        user_prompt = (
            f"Objetivo: {goal}\n"
            f"Tareas: {compact_tasks}\n"
            f"Archivo: {target_file}\n\n"
            f"Código actual:\n```python\n{original_code}\n```"
        )
        if repair_hint:
            user_prompt += (
                f"\n\nCorrección obligatoria del intento anterior:\n{repair_hint}\n"
                "Devuelve el bloque ```python completo y válido sin truncar."
            )

        llm_res = await self.inference.run(
            model_id=self.model_id,
            payload={
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]
            },
        )
        if llm_res.get("status") == "error":
            return {
                "ok": False,
                "error": llm_res.get("error_message", "Fallo en inferencia"),
                "raw_content": "",
            }

        raw_content = (
            llm_res.get("output")
            or llm_res.get("response")
            or llm_res.get("text")
            or llm_res.get("content")
            or ""
        )
        try:
            proposal = self._parse_proposal_response(raw_content, target_file, goal)
        except Exception as exc:
            return {
                "ok": False,
                "error": f"No se pudo extraer la propuesta: {exc}",
                "raw_content": raw_content,
            }

        valid, validation_err = self._validate_candidate_code(proposal["updated_code"])
        if not valid:
            return {
                "ok": False,
                "error": validation_err or "Validación de código fallida",
                "raw_content": raw_content,
            }

        return {"ok": True, "proposal": proposal, "raw_content": raw_content}

    def _authorize_pr_creation(self, target_file: str) -> tuple[bool, str]:
        if self.governance.emergency_stop.is_triggered:
            reason = self.governance.emergency_stop.status.get("reason") or "EmergencyStop activo"
            return False, f"Creación de PR bloqueada por EmergencyStop: {reason}"

        decision = self.governance.authorize_action(
            actor="autonomous_runner",
            action_name="create_pull_request",
            impact=ActionImpact.PR_CREATION,
            host=target_file,
        )

        if decision.requires_human_approval and decision.approval_request_id:
            approved = (
                bool(self.pr_approval_callback(decision))
                if self.pr_approval_callback is not None
                else False
            )
            if approved:
                if self.governance.approval_gate.approve(
                    decision.approval_request_id,
                    approver="autonomous_runner_reviewer",
                ):
                    decision = self.governance.authorize_action(
                        actor="autonomous_runner",
                        action_name="create_pull_request",
                        impact=ActionImpact.PR_CREATION,
                        host=target_file,
                        approval_request_id=decision.approval_request_id,
                    )

        if not decision.allowed:
            return False, f"Creación de PR no autorizada ({decision.code}): {decision.reason}"

        return True, "Autorizado"

    async def propose_improvement(
        self,
        target_file: str = "skills/data_tools.py",
        goal: str = "Optimizar manejo de errores, tipado estático y docstrings sin romper compatibilidad.",
        open_pr: bool = True,
    ) -> dict:
        logger.info(f"🚀 [Runner] Iniciando ciclo de auto-mejora sobre '{target_file}'...")
        await self.context.set(
            "last_runner_cycle",
            {
                "target_file": target_file,
                "goal": goal,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

        original_code = self.files.read_text_file(target_file)
        if original_code is None:
            return {"status": "error", "message": f"No se pudo leer '{target_file}'."}

        tasks_data = self.files.read_json_file("tasks.json") or {}

        # Primer intento + 1 reintento acotado si falla parseo o validación AST
        attempt = await self._request_code_proposal(
            target_file=target_file,
            goal=goal,
            original_code=original_code,
            tasks_data=tasks_data,
        )
        if not attempt["ok"]:
            logger.warning(
                f"⚠️ [Runner] Reintentando propuesta para '{target_file}' tras error: {attempt['error']}"
            )
            attempt = await self._request_code_proposal(
                target_file=target_file,
                goal=goal,
                original_code=original_code,
                tasks_data=tasks_data,
                repair_hint=attempt["error"],
            )

        if not attempt["ok"]:
            return {
                "status": "error",
                "message": attempt["error"],
                "raw_preview": (attempt.get("raw_content") or "")[:500],
            }

        proposal = attempt["proposal"]
        updated_code = proposal["updated_code"]
        pr_title = proposal["title"]
        pr_summary = proposal["summary"]

        if updated_code.strip() == original_code.strip():
            return {"status": "noop", "message": "El núcleo determinó que no se requieren cambios."}

        if not self.files.write_text_file(target_file, updated_code):
            return {"status": "blocked", "message": f"Escritura bloqueada en '{target_file}'."}

        test_output = self.system.execute_safe_command("pytest tests/unit -q", timeout_sec=30)
        if self._pytest_failed(test_output):
            self.files.write_text_file(target_file, original_code)
            return {
                "status": "reverted",
                "message": "Los tests unitarios fallaron. Cambios revertidos.",
                "test_output": test_output,
            }

        if not open_pr:
            return {
                "status": "staged_local",
                "title": pr_title,
                "summary": pr_summary,
                "test_output": test_output,
            }

        allowed_pr, auth_reason = self._authorize_pr_creation(target_file)
        if not allowed_pr:
            self.files.write_text_file(target_file, original_code)
            return {
                "status": "blocked",
                "message": auth_reason,
                "title": pr_title,
                "summary": pr_summary,
            }

        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        branch_name = f"atomum/proposal-{stamp}"
        if not self.git_ops.create_proposal_branch(branch_name):
            self.files.write_text_file(target_file, original_code)
            return {"status": "error", "message": "No se pudo crear la rama de propuesta en Git."}

        if not self.git_ops.commit_changes(f"feat(atomum): {pr_title}"):
            return {"status": "error", "message": "No se pudo realizar el commit en la rama de propuesta."}

        if not self.git_ops.push_branch(branch_name):
            return {
                "status": "committed_local",
                "branch": branch_name,
                "message": "Commit creado en rama local, pero falló el push (verifica GITHUB_TOKEN).",
            }

        pr_body = (
            f"### Propuesta Autónoma de ATOMUM\n\n"
            f"- **Archivo modificado:** `{target_file}`\n"
            f"- **Objetivo:** {goal}\n"
            f"- **Resumen técnico:** {pr_summary}\n"
            f"- **Validación AST & Pytest:** `{test_output}`\n"
        )
        pr_res = self.git_ops.create_pull_request(
            title=f"[ATOMUM] {pr_title}",
            body=pr_body,
            head_branch=branch_name,
            repo_slug=self.repo_slug,
        )
        return {
            "status": "pr_opened" if pr_res.get("status") == "ok" else "error",
            "branch": branch_name,
            "title": pr_title,
            "summary": pr_summary,
            "pr": pr_res,
        }

    def run_cycle(self):
        result = asyncio.run(self.propose_improvement())
        logger.info(f"✨ [Runner] Resultado del ciclo: {result}")
        return result


if __name__ == "__main__":
    runner = AutonomousRunner()
    runner.run_cycle()

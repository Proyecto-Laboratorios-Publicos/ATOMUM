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
    def _clean_code_block(raw_code: str) -> str:
        code = raw_code.strip()
        if code.startswith("```"):
            lines = code.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            code = "\n".join(lines).strip()
        return code + "\n" if code else ""

    @classmethod
    def _try_repair_unterminated_tail(cls, code: str) -> Optional[str]:
        """Intenta cerrar un f-string o string simple truncado al final del bloque."""
        lines = code.splitlines()
        if not lines:
            return None
        last = lines[-1]
        for quote in ('"""', "'''", '"', "'"):
            if last.count(quote) % 2 == 1:
                lines[-1] = last + quote
                candidate = "\n".join(lines) + "\n"
                try:
                    ast.parse(candidate)
                    return candidate
                except SyntaxError:
                    continue
        return None

    @classmethod
    def _merge_or_validate_code(cls, original_code: str, candidate_code: str) -> str:
        """Si candidate_code define una sola función/clase presente en original_code, la reemplaza."""
        try:
            tree = ast.parse(candidate_code)
        except SyntaxError:
            return candidate_code

        if len(tree.body) == 1 and isinstance(
            tree.body[0], (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            target_name = tree.body[0].name
            orig_lines = original_code.splitlines()
            cand_lines = candidate_code.splitlines()
            pattern = re.compile(
                rf"^(\s*)(?:async\s+def|def|class)\s+{re.escape(target_name)}\b"
            )
            start_idx = None
            base_indent = ""
            for idx, line in enumerate(orig_lines):
                m = pattern.match(line)
                if m:
                    start_idx = idx
                    base_indent = m.group(1)
                    break

            if start_idx is not None:
                end_idx = len(orig_lines)
                for idx in range(start_idx + 1, len(orig_lines)):
                    stripped = orig_lines[idx].strip()
                    if not stripped:
                        continue
                    curr_indent = len(orig_lines[idx]) - len(orig_lines[idx].lstrip(" "))
                    if curr_indent <= len(base_indent) and not stripped.startswith(
                        ("@", "#", ")", "]", "}")
                    ):
                        end_idx = idx
                        break

                rebuilt = orig_lines[:start_idx] + cand_lines + orig_lines[end_idx:]
                merged = "\n".join(rebuilt).strip() + "\n"
                try:
                    ast.parse(merged)
                    return merged
                except SyntaxError:
                    pass

        return candidate_code

    @classmethod
    def _validate_candidate_code(cls, code: str) -> tuple[bool, Optional[str], str]:
        normalized = cls._clean_code_block(code)
        if not normalized:
            return False, "Código candidato vacío.", normalized

        if validate_user_code is not None:
            try:
                validate_user_code(normalized)
            except Exception as exc:
                return False, f"Guardrail/AST rechazó el código: {exc}", normalized

        try:
            ast.parse(normalized)
            return True, None, normalized
        except SyntaxError as syn_err:
            repaired = cls._try_repair_unterminated_tail(normalized)
            if repaired:
                if validate_user_code is not None:
                    try:
                        validate_user_code(repaired)
                    except Exception as exc:
                        return False, f"Guardrail rechazó el código reparado: {exc}", repaired
                return True, None, repaired
            return False, f"Validación AST fallida: {syn_err}", normalized

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
            "<código Python completo o función/clase puntual válida>\n"
            "```\n"
            "Mantén 100% de retrocompatibilidad y asegúrate de cerrar todas las estructuras, strings y bloques."
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

        merged_code = self._merge_or_validate_code(original_code, proposal["updated_code"])
        valid, validation_err, final_code = self._validate_candidate_code(merged_code)
        if not valid:
            return {
                "ok": False,
                "error": validation_err or "Validación de código fallida",
                "raw_content": raw_content,
            }

        proposal["updated_code"] = final_code
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

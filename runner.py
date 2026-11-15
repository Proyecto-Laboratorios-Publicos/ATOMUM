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

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from atomum.context.service import ContextService
from atomum.inference.service import InferenceService
from atomum.inference.stub_inference import StubInferenceClient
from skills.file_tools import FileTools
from skills.git_ops import GitOperations
from skills.system_tools import SystemTools

logger = logging.getLogger("atomum.runner")
logging.basicConfig(level=logging.INFO)


class AutonomousRunner:
    def __init__(self, repo_slug: str = "Proyecto-Laboratorios-Publicos/ATOMUM"):
        self.repo_slug = repo_slug
        self.context = ContextService()
        self.files = FileTools(base_dir=".")
        self.system = SystemTools()
        self.git_ops = GitOperations(repo_path=".")

        api_key = os.getenv("GROQ_API_KEY", "")
        if api_key and api_key != "test_stub_key":
            self.inference = InferenceService()
        else:
            self.inference = InferenceService(client=StubInferenceClient())

        self.model_id = os.getenv("ATOMUM_LLM_MODEL", "openai/gpt-oss-120b")

    @staticmethod
    def _parse_proposal_response(raw_text: str, target_file: str, default_goal: str) -> dict:
        title_match = re.search(r"^TITLE:\s*(.+)$", raw_text, re.MULTILINE)
        summary_match = re.search(r"^SUMMARY:\s*(.+)$", raw_text, re.MULTILINE)
        
        # Búsqueda flexible de bloques de código (admite saltos de línea previos)
        code_match = re.search(r"```python\s*\n(.*?)\n\s*```", raw_text, re.DOTALL)
        if not code_match:
            code_match = re.search(r"```\s*\n(.*?)\n\s*```", raw_text, re.DOTALL)

        if not code_match:
            raise ValueError("No se encontró un bloque ```python ... ``` en la respuesta del modelo.")

        title = (
            title_match.group(1).strip()
            if title_match
            else f"chore(atomum): mejora autónoma en {target_file}"
        )
        summary = summary_match.group(1).strip() if summary_match else default_goal
        updated_code = code_match.group(1).strip() + "\n"

        return {"title": title, "summary": summary, "updated_code": updated_code}

    async def propose_improvement(
        self,
        target_file: str = "skills/data_tools.py",
        goal: str = "Optimizar manejo de errores, tipado estático y docstrings sin romper compatibilidad.",
        open_pr: bool = True,
    ) -> dict:
        logger.info(f"🚀 [Runner] Iniciando ciclo de auto-mejora sobre '{target_file}'...")
        await self.context.set(
            "last_runner_cycle",
            {"target_file": target_file, "goal": goal, "timestamp": datetime.now(timezone.utc).isoformat()},
        )

        original_code = self.files.read_text_file(target_file)
        if original_code is None:
            return {"status": "error", "message": f"No se pudo leer '{target_file}'."}

        tasks_data = self.files.read_json_file("tasks.json") or {}

        system_prompt = (
            "Eres el núcleo de ingeniería autónoma de ATOMUM. "
            "Analiza el archivo Python y responde ESTRICTAMENTE con este formato:\n"
            "TITLE: <título corto>\n"
            "SUMMARY: <resumen técnico en una línea>\n"
            "```python\n"
            "<código Python completo>\n"
            "```\n"
            "Mantén 100% de retrocompatibilidad y entrega el archivo completo."
        )
        user_prompt = (
            f"Objetivo: {goal}\n"
            f"Tareas: {json.dumps(tasks_data, ensure_ascii=False)[:1500]}\n"
            f"Archivo: {target_file}\n\n"
            f"Código actual:\n```python\n{original_code}\n```"
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
            return {"status": "error", "message": llm_res.get("error_message", "Fallo en inferencia")}

        raw_content = (
            llm_res.get("output")
            or llm_res.get("response")
            or llm_res.get("text")
            or llm_res.get("content")
            or ""
        )

        try:
            proposal = self._parse_proposal_response(raw_content, target_file, goal)
            updated_code = proposal["updated_code"]
            pr_title = proposal["title"]
            pr_summary = proposal["summary"]
        except Exception as exc:
            return {
                "status": "error",
                "message": f"No se pudo extraer la propuesta: {exc}",
                "raw_preview": raw_content[:500],
            }

        try:
            ast.parse(updated_code)
        except SyntaxError as syn_err:
            return {"status": "error", "message": f"Validación AST fallida: {syn_err}"}

        if updated_code.strip() == original_code.strip():
            return {"status": "noop", "message": "El núcleo determinó que no se requieren cambios."}

        if not self.files.write_text_file(target_file, updated_code):
            return {"status": "blocked", "message": f"Escritura bloqueada en '{target_file}'."}

        test_output = self.system.execute_safe_command("pytest tests/unit -q", timeout_sec=30)
        if "failed" in test_output.lower() or "error" in test_output.lower():
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

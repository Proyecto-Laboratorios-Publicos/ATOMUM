"""
runner.py
---------
Orquestador principal del ciclo de auto-mejora autónoma de ATOMUM.
Integra el núcleo modular (InferenceService, ContextService), validación AST,
pruebas unitarias y apertura segura de Pull Requests en GitHub.
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
    def _extract_json_block(raw_text: str) -> dict:
        """Extrae y parsea el bloque JSON de la respuesta del LLM."""
        cleaned = raw_text.strip()
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
        if match:
            cleaned = match.group(1)
        return json.loads(cleaned)

    async def propose_improvement(
        self,
        target_file: str = "skills/data_tools.py",
        goal: str = "Optimizar manejo de errores, tipado estático y docstrings sin romper compatibilidad.",
        open_pr: bool = True,
    ) -> dict:
        """Ejecuta un ciclo completo de análisis, validación AST/pytest y Pull Request."""
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
            "Debes analizar el archivo Python proporcionado y devolver EXCLUSIVAMENTE un objeto JSON válido "
            "con las claves exactas: "
            '{"title": "título corto del PR", "summary": "explicación técnica", "updated_code": "código completo actualizado"}. '
            "Reglas estrictas: mantén total retrocompatibilidad, no inventes dependencias externas y asegúrate de que el código compile."
        )
        user_prompt = (
            f"Objetivo de mejora: {goal}\n"
            f"Contexto de tareas (tasks.json): {json.dumps(tasks_data, ensure_ascii=False)[:1500]}\n"
            f"Archivo objetivo: {target_file}\n\n"
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
            proposal = self._extract_json_block(raw_content)
            updated_code = proposal["updated_code"]
            pr_title = proposal.get("title", f"chore(atomum): mejora autónoma en {target_file}")
            pr_summary = proposal.get("summary", goal)
        except Exception as exc:
            return {
                "status": "error",
                "message": f"La respuesta del modelo no tuvo un JSON estructural válido: {exc}",
                "raw_preview": raw_content[:400],
            }

        # 1. Validación estricta de sintaxis AST antes de escribir
        try:
            ast.parse(updated_code)
        except SyntaxError as syn_err:
            return {"status": "error", "message": f"Validación AST fallida: {syn_err}"}

        if updated_code.strip() == original_code.strip():
            return {"status": "noop", "message": "El núcleo determinó que no se requieren cambios."}

        # 2. Aplicar cambio temporalmente y ejecutar suite de tests unitarios
        if not self.files.write_text_file(target_file, updated_code):
            return {"status": "blocked", "message": f"Escritura bloqueada por guardarraíles en '{target_file}'."}

        test_output = self.system.execute_safe_command("pytest tests/unit -q", timeout_sec=30)
        if "failed" in test_output.lower() or "error" in test_output.lower():
            # Rollback inmediato si falla algún test
            self.files.write_text_file(target_file, original_code)
            return {
                "status": "reverted",
                "message": "Los tests unitarios fallaron tras aplicar el parche. Cambios revertidos.",
                "test_output": test_output,
            }

        if not open_pr:
            return {
                "status": "staged_local",
                "title": pr_title,
                "summary": pr_summary,
                "test_output": test_output,
            }

        # 3. Crear rama de propuesta, commitear, pushear y abrir PR en GitHub
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
        """Punto de entrada síncrono compatible con CLI y cron jobs."""
        result = asyncio.run(self.propose_improvement())
        logger.info(f"✨ [Runner] Resultado del ciclo: {result}")
        return result


if __name__ == "__main__":
    runner = AutonomousRunner()
    runner.run_cycle()

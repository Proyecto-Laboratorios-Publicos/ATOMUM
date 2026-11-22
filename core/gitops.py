"""
core/gitops.py
--------------
Helper ligero para operaciones locales de Git (creación de ramas y commits)
utilizado por flujos auxiliares de ATOMUM.
"""

from __future__ import annotations

import logging
from pathlib import Path
import re
import subprocess
import uuid

logger = logging.getLogger(__name__)

_REF_SANITIZER: re.Pattern[str] = re.compile(r"[^a-zA-Z0-9._/-]+")


class GitHubSyncOps:
    """Encapsula operaciones locales de creación de ramas y commits en Git."""

    def __init__(self, repo_path: str | Path = ".", base_branch: str = "main") -> None:
        self.repo_path: Path = Path(repo_path).resolve()
        self.base_branch: str = base_branch.strip() or "main"

    def _run_git(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        """Ejecuta un comando git en repo_path y propaga detalles claros en caso de error."""
        if not self.repo_path.exists():
            raise FileNotFoundError(f"La ruta del repositorio no existe: {self.repo_path}")

        try:
            return subprocess.run(
                ["git", *args],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "").strip()
            stdout = (exc.stdout or "").strip()
            detail = stderr or stdout or str(exc)
            raise RuntimeError(f"Comando 'git {' '.join(args)}' falló: {detail}") from exc

    def _has_changes(self) -> bool:
        """Indica si existen cambios staged o sin seguimiento en el repositorio."""
        status = self._run_git(["status", "--porcelain"])
        return bool(status.stdout.strip())

    @staticmethod
    def _sanitize_prefix(prefix: str) -> str:
        cleaned = _REF_SANITIZER.sub("-", prefix.strip()).strip("/.-")
        return cleaned or "auto-opt-"

    def create_branch(self, prefix: str = "auto-opt-", from_branch: str | None = None) -> str:
        """Crea una rama única a partir de la rama base configurada."""
        target_base = (from_branch or self.base_branch).strip() or "main"
        safe_prefix = self._sanitize_prefix(prefix)
        suffix = "" if safe_prefix.endswith("-") else "-"
        branch_name = f"{safe_prefix}{suffix}{uuid.uuid4().hex[:8]}"

        try:
            self._run_git(["checkout", target_base])
            self._run_git(["checkout", "-b", branch_name])
            logger.info("Rama creada para PR automático: %s (base: %s)", branch_name, target_base)
            return branch_name
        except Exception as exc:
            logger.error("Error creando rama de Git '%s': %s", branch_name, exc)
            raise

    def commit_changes(self, message: str) -> bool:
        """Agrega cambios y realiza commit si hay modificaciones pendientes."""
        clean_message = message.strip()
        if not clean_message:
            raise ValueError("El mensaje de commit no puede estar vacío.")

        try:
            if not self._has_changes():
                logger.info("Sin cambios pendientes para commit en %s", self.repo_path)
                return False

            self._run_git(["add", "."])
            if not self._has_changes():
                logger.info("No quedaron cambios staged para commit en %s", self.repo_path)
                return False

            self._run_git(["commit", "-m", clean_message])
            logger.info("Commit realizado con éxito: %s", clean_message)
            return True
        except Exception as exc:
            logger.error("Error al realizar commit: %s", exc)
            raise

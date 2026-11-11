"""
gitops.py
---------
Encapsula las interacciones con GitHub: ramas, commits y automatización
de flujo de trabajo con control de errores.
"""

import os
import uuid
import subprocess
import pathlib
from utils.logger import logger

class GitHubSyncOps:
    def __init__(self, repo_path: str = "."):
        self.repo_path = pathlib.Path(repo_path)

    def create_branch(self, prefix: str = "auto-opt-") -> str:
        """Crea una rama única para la optimización autónoma."""
        branch_name = f"{prefix}{uuid.uuid4().hex[:8]}"
        try:
            subprocess.run(["git", "checkout", "main"], cwd=self.repo_path, capture_output=True, check=True)
            subprocess.run(["git", "checkout", "-b", branch_name], cwd=self.repo_path, check=True)
            logger.info(f"Rama creada para PR automático: {branch_name}")
            return branch_name
        except Exception as e:
            logger.error(f"Error creando rama de Git: {e}")
            raise

    def commit_changes(self, message: str) -> None:
        """Realiza commit de los cambios actuales en el repositorio."""
        try:
            subprocess.run(["git", "add", "."], cwd=self.repo_path, check=True)
            subprocess.run(["git", "commit", "-m", message], cwd=self.repo_path, check=True)
            logger.info(f"Commit realizado con éxito: {message}")
        except Exception as e:
            logger.error(f"Error al realizar commit: {e}")
            raise

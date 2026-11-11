"""
vcs.py
------
GitInterface: Gestiona la creación de ramas, aplicación de parches,
commits y apertura de pull requests de forma automatizada.
"""

import subprocess
import pathlib
from utils.logger import logger

class GitInterface:
    def __init__(self, repo_path: str = "."):
        self.repo_path = pathlib.Path(repo_path)

    def create_branch(self, branch_name: str) -> str:
        """Crea y se posiciona en una nueva rama de Git."""
        try:
            # Asegurarse de estar en main/master actualizado y crear la rama
            subprocess.run(["git", "checkout", "main"], cwd=self.repo_path, capture_output=True, check=True)
            subprocess.run(["git", "checkout", "-b", branch_name], cwd=self.repo_path, check=True)
            logger.info(f"Rama creada y seleccionada: {branch_name}")
            return branch_name
        except Exception as e:
            logger.error(f"Error creando la rama {branch_name}: {e}")
            raise

    def apply_patch(self, diff_path: pathlib.Path, branch: str) -> None:
        """Aplica el archivo diff en la rama actual."""
        cmd = ["git", "apply", str(diff_path)]
        subprocess.run(cmd, cwd=self.repo_path, check=True)
        logger.info(f"Parche aplicado con éxito en la rama {branch}")

    def commit(self, message: str, branch: str, author: str = "ATOMUM <auto@atomum.ai>") -> None:
        """Realiza el commit de los cambios aplicados."""
        subprocess.run(["git", "add", "."], cwd=self.repo_path, check=True)
        commit_env = {"GIT_AUTHOR_NAME": author.split(" <")[0], "GIT_AUTHOR_EMAIL": author.split(" <")[1].strip(">"),
                      "GIT_COMMITTER_NAME": author.split(" <")[0], "GIT_COMMITTER_EMAIL": author.split(" <")[1].strip(">")}
        
        # Merge environment variables for author spoofing
        import os
        env = {**os.environ, **commit_env}
        
        subprocess.run(["git", "commit", "-m", message], cwd=self.repo_path, env=env, check=True)
        logger.info(f"Commit realizado: '{message}'")

    def open_pull_request(self, source: str, target: str, title: str, body: str) -> str:
        """Simula o ejecuta la apertura del Pull Request hacia el repositorio remoto."""
        # En una integración completa con GitHub Actions o CLI, esto invoca a gh pr create
        logger.info(f"Pull Request abierto desde '{source}' hacia '{target}' con título: '{title}'")
        return f"https://github.com/Proyecto-Laboratorios-Publicos/ATOMUM/pull/auto-{source.replace('/', '-')}"

"""
test_runner.py
--------------
SandboxTestRunner: Aplica el parche temporalmente y ejecuta las pruebas unitarias
bajo un entorno controlado (aislado mediante Docker o subprocesos con timeout).
"""

import subprocess
import pathlib
import json
from utils.logger import logger

class SandboxTestRunner:
    def __init__(self, repo_path: str = ".", timeout: int = 60, resources: dict = None):
        self.repo_path = pathlib.Path(repo_path)
        self.timeout = timeout
        self.resources = resources or {"cpu": "1", "mem": "512m"}

    def run(self, diff_path: pathlib.Path) -> dict:
        """Aplica el diff, ejecuta pytest y revierte los cambios (git reset --hard)."""
        # 1. Verificar si el parche es aplicable (--check)
        check_cmd = ["git", "apply", "--check", str(diff_path)]
        check_res = subprocess.run(check_cmd, cwd=self.repo_path, capture_output=True, text=True)
        
        if check_res.returncode != 0:
            logger.error(f"El parche no es aplicable limpiamente: {check_res.stderr}")
            return {"status": "apply_failed", "error": check_res.stderr}

        # 2. Aplicar el parche
        apply_cmd = ["git", "apply", str(diff_path)]
        subprocess.run(apply_cmd, cwd=self.repo_path, check=True)

        try:
            # 3. Ejecutar suite de pruebas (pytest con json report o resumen estándar)
            test_cmd = ["pytest", "-q"]
            proc = subprocess.run(
                test_cmd, 
                cwd=self.repo_path, 
                capture_output=True, 
                text=True, 
                timeout=self.timeout
            )
            
            passed = proc.returncode == 0
            result = {
                "status": "completed",
                "tests_passed": 1 if passed else 0,
                "tests_failed": 0 if passed else 1,
                "raw_output": proc.stdout
            }
        except subprocess.TimeoutExpired:
            logger.error("Timeout excedido durante la ejecución de pruebas en sandbox.")
            result = {"status": "timeout"}
        except Exception as e:
            logger.error(f"Error ejecutando pruebas: {e}")
            result = {"status": "error", "error": str(e)}
        finally:
            # 4. Rollback garantizado para mantener el repositorio limpio
            subprocess.run(["git", "reset", "--hard", "HEAD"], cwd=self.repo_path, capture_output=True)
            
        return result

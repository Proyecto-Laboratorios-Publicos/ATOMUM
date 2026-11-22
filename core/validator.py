"""
validator.py
------------
Validador de AST para inspeccionar código Python antes de aplicar parches,
detectando llamadas peligrosas y errores de sintaxis de forma controlada.
"""

import ast
import logging
import sys

logger = logging.getLogger(__name__)


class ASTValidator:
    """Comprueba que el código fuente sea sintácticamente válido y libre de llamadas prohibidas."""

    PROHIBITED_CALLS: set[str] = {
        "eval",
        "exec",
        "compile",
        "__import__",
        "os.system",
        "os.popen",
        "subprocess.Popen",
        "subprocess.run",
        "subprocess.call",
        "subprocess.check_call",
        "subprocess.check_output",
    }

    def __init__(self, source: str) -> None:
        if not isinstance(source, str):
            raise TypeError("El código fuente debe ser una cadena de texto (str).")
        self.source = source
        self.tree: ast.AST | None = None
        self.syntax_error: SyntaxError | None = None
        self.violations: list[str] = []

        try:
            self.tree = ast.parse(source)
            self.violations = self._find_forbidden_calls()
        except SyntaxError as exc:
            self.syntax_error = exc
            self.violations = [f"SyntaxError en línea {exc.lineno}: {exc.msg}"]

    @staticmethod
    def _resolve_call_name(func: ast.expr) -> str:
        """Resuelve nombres simples o cadenas de atributos (ej. os.system, a.b.c)."""
        if isinstance(func, ast.Name):
            return func.id
        if isinstance(func, ast.Attribute):
            parts: list[str] = [func.attr]
            current: ast.expr = func.value
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
                return ".".join(reversed(parts))
        return ""

    def _find_forbidden_calls(self) -> list[str]:
        if self.tree is None:
            return []
        found: list[str] = []
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call):
                call_name = self._resolve_call_name(node.func)
                if call_name in self.PROHIBITED_CALLS:
                    found.append(call_name)
        return found

    def is_valid(self) -> bool:
        """Devuelve True solo si el código parsea sin errores y no tiene llamadas prohibidas."""
        return self.syntax_error is None and not self.violations


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger.info("ASTValidator listo (verificación estática de sintaxis y llamadas prohibidas).")
    sys.exit(0)

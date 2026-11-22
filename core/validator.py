"""
validator.py
------------
Validador de AST para inspeccionar código Python antes de aplicar parches,
detectando errores de sintaxis, imports sensibles y llamadas prohibidas de forma controlada.
"""

from __future__ import annotations

import ast
import logging
import sys
from typing import Any

logger = logging.getLogger(__name__)


class ASTValidator:
    """Validador estático basado en AST para código Python propuesto en parches."""

    PROHIBITED_CALLS: frozenset[str] = frozenset(
        {
            "eval",
            "exec",
            "compile",
            "__import__",
            "getattr",
            "importlib.import_module",
            "os.system",
            "os.popen",
            "os.spawnl",
            "os.spawnle",
            "os.spawnlp",
            "os.spawnlpe",
            "os.spawnv",
            "os.spawnve",
            "os.spawnvp",
            "os.spawnvpe",
            "subprocess.Popen",
            "subprocess.run",
            "subprocess.call",
            "subprocess.check_call",
            "subprocess.check_output",
            "shutil.rmtree",
        }
    )

    PROHIBITED_MODULES: frozenset[str] = frozenset(
        {
            "ctypes",
            "pickle",
            "marshal",
            "shelve",
        }
    )

    def __init__(
        self,
        source: str,
        *,
        extra_prohibited_calls: set[str] | frozenset[str] | None = None,
        strict_imports: bool = True,
    ) -> None:
        if not isinstance(source, str):
            raise TypeError("El código fuente debe ser una cadena de texto (str).")

        self.source: str = source
        self.strict_imports: bool = strict_imports
        self.prohibited_calls: frozenset[str] = (
            self.PROHIBITED_CALLS | frozenset(extra_prohibited_calls)
            if extra_prohibited_calls
            else self.PROHIBITED_CALLS
        )
        self.tree: ast.Module | None = None
        self.syntax_error: SyntaxError | None = None
        self.violations: list[str] = []

        self._analyze()

    def _analyze(self) -> None:
        """Ejecuta el parseo AST y recolecta infracciones estáticas."""
        try:
            self.tree = ast.parse(self.source)
        except SyntaxError as exc:
            self.syntax_error = exc
            line = exc.lineno if exc.lineno is not None else "?"
            self.violations = [f"SyntaxError en línea {line}: {exc.msg}"]
            return

        violations: list[str] = []
        violations.extend(self._find_forbidden_calls(self.tree))
        if self.strict_imports:
            violations.extend(self._find_prohibited_imports(self.tree))
        self.violations = violations

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

    def _find_forbidden_calls(self, tree: ast.AST) -> list[str]:
        """Busca llamadas a funciones o métodos prohibidos en el árbol AST."""
        found: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                call_name = self._resolve_call_name(node.func)
                if call_name in self.prohibited_calls:
                    line = getattr(node, "lineno", "?")
                    found.append(f"Llamada prohibida '{call_name}' en línea {line}")
        return found

    def _find_prohibited_imports(self, tree: ast.AST) -> list[str]:
        """Detecta imports de módulos sensibles o de deserialización insegura."""
        found: list[str] = []
        for node in ast.walk(tree):
            line = getattr(node, "lineno", "?")
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_pkg = alias.name.split(".")[0]
                    if alias.name in self.PROHIBITED_MODULES or root_pkg in self.PROHIBITED_MODULES:
                        found.append(f"Import sensible '{alias.name}' en línea {line}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                root_pkg = node.module.split(".")[0]
                if node.module in self.PROHIBITED_MODULES or root_pkg in self.PROHIBITED_MODULES:
                    found.append(f"Import desde módulo sensible '{node.module}' en línea {line}")
        return found

    def is_valid(self) -> bool:
        """Devuelve True solo si el código parsea sin errores y no tiene infracciones."""
        return self.syntax_error is None and not self.violations

    def summary(self) -> dict[str, Any]:
        """Devuelve un resumen estructurado del resultado de validación."""
        return {
            "valid": self.is_valid(),
            "has_syntax_error": self.syntax_error is not None,
            "violation_count": len(self.violations),
            "violations": list(self.violations),
        }


def main() -> int:
    """Punto de entrada CLI para verificaciones de entorno o pruebas rápidas."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    sample = "x = 1 + 2\n"
    result = ASTValidator(sample).summary()
    logger.info("ASTValidator operativo | resumen de prueba: %s", result)
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())

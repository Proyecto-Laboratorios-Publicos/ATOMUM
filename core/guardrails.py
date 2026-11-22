"""
core/guardrails.py
------------------
Guardrails constitucionales y de sandbox estático para ATOMUM.
Evalúa tanto acciones operativas propuestas como fragmentos de código no confiable
antes de permitir su ejecución o aplicación en el repositorio.
"""

from __future__ import annotations

import ast
import logging
import re
from typing import Final

logger = logging.getLogger(__name__)


class GuardrailViolation(Exception):
    """Excepción lanzada cuando un código o acción viola las políticas de seguridad."""


class SafeASTVisitor(ast.NodeVisitor):
    """
    Visitante AST estricto para inspeccionar código no confiable o de sandbox.
    A diferencia de ASTValidator (orientado a revisión de parches del repo),
    este visitante restringe imports sensibles, primitivas de introspección
    y complejidad excesiva del árbol sintáctico.
    """

    FORBIDDEN_MODULES: Final[frozenset[str]] = frozenset(
        {
            "os",
            "sys",
            "subprocess",
            "shutil",
            "socket",
            "ctypes",
            "pickle",
            "marshal",
            "shelve",
            "importlib",
            "builtins",
            "pathlib",
            "tempfile",
            "pty",
            "commands",
        }
    )

    FORBIDDEN_BUILTINS: Final[frozenset[str]] = frozenset(
        {
            "eval",
            "exec",
            "compile",
            "__import__",
            "open",
            "input",
            "getattr",
            "setattr",
            "delattr",
            "hasattr",
            "globals",
            "locals",
            "vars",
            "dir",
            "type",
            "super",
            "memoryview",
            "breakpoint",
        }
    )

    FORBIDDEN_DUNDERS: Final[frozenset[str]] = frozenset(
        {
            "__subclasses__",
            "__globals__",
            "__builtins__",
            "__code__",
            "__closure__",
            "__mro__",
            "__bases__",
            "__base__",
            "__class__",
            "__dict__",
            "__loader__",
            "__spec__",
            "__import__",
        }
    )

    FORBIDDEN_CALL_PATHS: Final[frozenset[str]] = frozenset(
        {
            "importlib.import_module",
            "__builtins__.eval",
            "__builtins__.exec",
            "__builtins__.__import__",
        }
    )

    def __init__(self, max_nodes: int = 1000) -> None:
        if max_nodes < 1:
            raise ValueError("max_nodes debe ser un entero positivo.")
        self.max_nodes: int = max_nodes
        self.node_count: int = 0

    def check(self, tree: ast.AST) -> None:
        """Reinicia el contador y recorre el árbol AST completo."""
        self.node_count = 0
        self.visit(tree)

    def generic_visit(self, node: ast.AST) -> None:
        self.node_count += 1
        if self.node_count > self.max_nodes:
            raise GuardrailViolation(
                f"Código demasiado complejo ({self.node_count} nodos AST; máximo permitido: {self.max_nodes})."
            )
        super().generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            root_pkg = alias.name.split(".")[0]
            if alias.name in self.FORBIDDEN_MODULES or root_pkg in self.FORBIDDEN_MODULES:
                raise GuardrailViolation(
                    f"Importación de módulo restringido '{alias.name}' en línea {node.lineno}."
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.level > 0:
            raise GuardrailViolation(
                f"Importación relativa no permitida en modo sandbox (línea {node.lineno})."
            )
        if node.module:
            root_pkg = node.module.split(".")[0]
            if node.module in self.FORBIDDEN_MODULES or root_pkg in self.FORBIDDEN_MODULES:
                raise GuardrailViolation(
                    f"Importación desde módulo restringido '{node.module}' en línea {node.lineno}."
                )
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr in self.FORBIDDEN_DUNDERS or (
            node.attr.startswith("__") and node.attr.endswith("__") and node.attr != "__name__"
        ):
            raise GuardrailViolation(
                f"Acceso a atributo dunder restringido '{node.attr}' en línea {node.lineno}."
            )
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load) and node.id in self.FORBIDDEN_BUILTINS:
            raise GuardrailViolation(
                f"Referencia a built-in restringido '{node.id}' en línea {node.lineno}."
            )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        call_path = self._resolve_call_name(node.func)
        if call_path in self.FORBIDDEN_BUILTINS or call_path in self.FORBIDDEN_CALL_PATHS:
            raise GuardrailViolation(
                f"Llamada restringida '{call_path}' en línea {node.lineno}."
            )
        self.generic_visit(node)

    @staticmethod
    def _resolve_call_name(func: ast.expr) -> str:
        """Resuelve nombres simples o cadenas de atributos (ej. a.b.c)."""
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


def validate_user_code(source: str, *, max_nodes: int = 1000) -> ast.Module:
    """
    Parsea y valida código Python contra las reglas de SafeASTVisitor.
    Devuelve el árbol ast.Module si supera todas las comprobaciones o lanza GuardrailViolation.
    """
    if not isinstance(source, str) or not source.strip():
        raise GuardrailViolation("El código fuente debe ser una cadena de texto no vacía.")

    try:
        tree = ast.parse(source, mode="exec")
    except SyntaxError as exc:
        line = exc.lineno if exc.lineno is not None else "?"
        raise GuardrailViolation(f"Error de sintaxis en línea {line}: {exc.msg}") from exc

    visitor = SafeASTVisitor(max_nodes=max_nodes)
    visitor.check(tree)
    return tree


class Guardrails:
    """Capa de cumplimiento constitucional y validación operativa de acciones en ATOMUM."""

    FORBIDDEN_ACTION_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
        re.compile(r"(?i)\brm\s+-rf\b"),
        re.compile(r"(?i)\bdrop\s+(?:table|database)\b"),
        re.compile(r"(?i)\btruncate\s+table\b"),
        re.compile(r"(?i)\bdelete\s+from\b"),
        re.compile(r"(?i)\bformat\s+[a-z]:"),
        re.compile(r"(?i)\bmkfs(?:\.[a-z0-9]+)?\b"),
        re.compile(r"(?i)\b(?:shutdown|reboot|poweroff)\b"),
        re.compile(r"(?i)\bchmod\s+777\b"),
        re.compile(r"(?i)\bcurl\b.*\|\s*(?:sh|bash)\b"),
    )

    def __init__(self, constitution_path: str = "CONSTITUTION.md") -> None:
        self.constitution_path: str = constitution_path
        logger.info("Guardrails cargados con Constitución en: %s", self.constitution_path)

    def validate_action(self, action_description: str) -> bool:
        """Verifica que la acción descriptiva no contenga comandos destructivos prohibidos."""
        if not isinstance(action_description, str) or not action_description.strip():
            logger.warning("Guardrail bloqueó acción vacía o inválida.")
            return False

        for pattern in self.FORBIDDEN_ACTION_PATTERNS:
            match = pattern.search(action_description)
            if match:
                logger.warning(
                    "Guardrail bloqueó acción peligrosa (patrón coincidente: '%s')",
                    match.group(0),
                )
                return False

        return True

    def validate_code(self, source: str, *, max_nodes:

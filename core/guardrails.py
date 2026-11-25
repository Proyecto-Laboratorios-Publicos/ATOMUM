import ast
import logging
import re
from typing import Final

logger = logging.getLogger(__name__)


class GuardrailViolation(Exception):
    """Excepción lanzada cuando una acción o código viola las reglas de seguridad."""


class SafeASTVisitor(ast.NodeVisitor):
    """Validador de AST para restringir construcciones peligrosas en código Python."""

    BLOCKED_IMPORTS: Final[set[str]] = {
        "os",
        "sys",
        "subprocess",
        "shutil",
        "socket",
        "importlib",
        "ctypes",
        "pickle",
        "marshal",
    }
    BLOCKED_CALLS: Final[set[str]] = {
        "eval",
        "exec",
        "compile",
        "open",
        "__import__",
        "input",
    }

    def __init__(self, max_nodes: int = 1000) -> None:
        self.max_nodes: int = max_nodes
        self.node_count: int = 0

    def check(self, tree: ast.AST) -> None:
        self.node_count = 0
        self.visit(tree)

    def generic_visit(self, node: ast.AST) -> None:
        self.node_count += 1
        if self.node_count > self.max_nodes:
            raise GuardrailViolation(
                f"El código supera el límite máximo de nodos AST ({self.max_nodes})."
            )
        super().generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            root_module = alias.name.split(".")[0]
            if root_module in self.BLOCKED_IMPORTS:
                raise GuardrailViolation(f"Importación bloqueada por guardrail: {alias.name}")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            root_module = node.module.split(".")[0]
            if root_module in self.BLOCKED_IMPORTS:
                raise GuardrailViolation(
                    f"Importación desde módulo bloqueado: {node.module}"
                )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        call_name = self._resolve_call_name(node.func)
        base_name = call_name.split(".")[0] if call_name else ""
        if call_name in self.BLOCKED_CALLS or base_name in self.BLOCKED_CALLS:
            raise GuardrailViolation(f"Llamada a función bloqueada: {call_name}")
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

    def validate_code(self, source: str, *, max_nodes: int = 1000) -> ast.Module:
        """Valida código fuente Python delegando en validate_user_code."""
        return validate_user_code(source, max_nodes=max_nodes)

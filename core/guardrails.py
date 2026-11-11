"""
Guardarraíles Constitucionales (Guardrails) para ATOMUM.
Implementa evaluación segura mediante AST y listas negras de módulos y funciones peligrosas.
"""

import ast
from typing import Set, List

# Módulos prohibidos a nivel de sistema para evitar inyecciones graves
FORBIDDEN_MODULES: Set[str] = {
    "os", "sys", "subprocess", "socket", "shutil", "pathlib", "tempfile", "builtins", "__import__", "importlib"
}

# Funciones integradas peligrosas que no deben invocarse directamente
FORBIDDEN_BUILTINS: Set[str] = {
    "eval", "exec", "open", "compile", "globals", "locals", "vars", "dir", "type", "super", "getattr", "setattr", "delattr", "repr", "print"
}

MAX_NODES: int = 200  # Límite de complejidad del árbol AST para prevenir DoS

class GuardrailViolation(Exception):
    """Excepción lanzada cuando el código viola alguna regla de seguridad."""
    pass

class SafeASTVisitor(ast.NodeVisitor):
    """Recorre el árbol AST y lanza GuardrailViolation si detecta elementos prohibidos."""
    def __init__(self):
        super().__init__()
        self.node_count = 0

    def generic_visit(self, node):
        self.node_count += 1
        if self.node_count > MAX_NODES:
            raise GuardrailViolation(f"AST demasiado grande ({self.node_count} nodos). Posible bucle o complejidad excesiva.")
        super().generic_visit(node)

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            if alias.name.split('.')[0] in FORBIDDEN_MODULES:
                raise GuardrailViolation(f"Importación prohibida detectada: {alias.name}")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module and node.module.split('.')[0] in FORBIDDEN_MODULES:
            raise GuardrailViolation(f"ImportFrom prohibido detectado: {node.module}")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        if isinstance(node.func, ast.Name):
            if node.func.id in FORBIDDEN_BUILTINS:
                raise GuardrailViolation(f"Llamada a función built-in prohibida: {node.func.id}")
        if isinstance(node.func, ast.Attribute):
            if (isinstance(node.func.value, ast.Name) and 
                node.func.value.id in {"importlib", "__builtins__"} and 
                node.func.attr == "import_module"):
                raise GuardrailViolation("Uso de importlib.import_module está prohibido")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute):
        if node.attr.startswith("__"):
            raise GuardrailViolation(f"Acceso a atributo dunder prohibido: {node.attr}")
        self.generic_visit(node)

def validate_user_code(source: str) -> None:
    """
    Analiza `source` con AST y lanza GuardrailViolation si se detecta alguna regla prohibida.
    """
    try:
        tree = ast.parse(source, mode='exec')
    except SyntaxError as exc:
        raise GuardrailViolation(f"Error de sintaxis en el código: {exc}") from exc
    
    visitor = SafeASTVisitor()
    visitor.visit(tree)

class Guardrails:
    def __init__(self):
        print("🛡️ [Guardrails] Subsistema de seguridad constitucional inicializado con AST Avanzado.")

    def validate_action(self, action: str) -> bool:
        """Valida directivas de texto plano y asegura que no contengan comandos destructivos."""
        if not action or not isinstance(action, str):
            return False
            
        action_lower = action.lower()
        forbidden_keywords = ["rm -rf /", "mkfs", "dd if=", ":(){ :|:& };:", "shutdown", "reboot"]
        for keyword in forbidden_keywords:
            if keyword in action_lower:
                print(f"🚫 [Guardrails] Comando destructivo detectado ('{keyword}'). Bloqueado.")
                return False
                
        return True

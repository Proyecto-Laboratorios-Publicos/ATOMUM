"""
guardrails.py (Autonomous Loop)
-------------------------------
Valida estáticamente mediante AST que las propuestas de parches no contengan
instrucciones peligrosas, llamadas prohibidas (eval, exec, os.system, etc.).
"""

import ast
from utils.logger import logger

class SecurityPolicy:
    """Conjunto de reglas estrictas que el AST del parche debe cumplir."""
    DISALLOWED_NODES = {
        getattr(ast, 'Exec', None),
        getattr(ast, 'Eval', None),
    }
    DISALLOWED_NODES = {n for n in DISALLOWED_NODES if n is not None}
    
    DISALLOWED_CALLS = {
        "os.system", "subprocess.Popen", "subprocess.run", 
        "eval", "exec", "pickle.load", "open", "__import__", "importlib.import_module"
    }

class ASTValidator:
    def __init__(self, policy: SecurityPolicy = None):
        self.policy = policy or SecurityPolicy()

    def validate(self, tree: ast.AST) -> bool:
        """Recorre el árbol AST y devuelve False si se detecta alguna violación."""
        for node in ast.walk(tree):
            if type(node) in self.policy.DISALLOWED_NODES:
                logger.warning(f"Nodo prohibido detectado en AST: {type(node).__name__}")
                return False
                
            if isinstance(node, ast.Call):
                func_name = self._resolve_name(node.func)
                if func_name in self.policy.DISALLOWED_CALLS:
                    logger.warning(f"Llamada prohibida detectada en AST: {func_name}")
                    return False
        return True

    @staticmethod
    def _resolve_name(node) -> str:
        """Obtiene el nombre calificado de una llamada (ej. os.path.join)."""
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return f"{ASTValidator._resolve_name(node.value)}.{node.attr}"
        return ""

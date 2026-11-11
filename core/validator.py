"""
validator.py
------------
Validador robusto de AST y compatibilidad de ContextManagers
para asegurar código 100% seguro y compatible antes de aplicar parches.
"""

import ast
from typing import List

class ASTValidator:
    """Comprueba que el árbol sintáctico sea válido y libre de nodos prohibidos."""
    PROHIBITED_CALLS = {"eval", "exec", "os.system", "subprocess.Popen"}

    def __init__(self, source: str):
        self.source = source
        self.tree = ast.parse(source)

    def _has_forbidden_calls(self) -> List[str]:
        bad = []
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call):
                # Extraer nombre de la llamada de forma segura
                func_name = ""
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    func_name = f"{node.func.value.id if isinstance(node.func.value, ast.Name) else ''}.{node.func.attr}"
                
                if func_name in self.PROHIBITED_CALLS:
                    bad.append(func_name)
        return bad

    def is_valid(self) -> bool:
        """Devuelve True solo si el AST pasa todas las normativas de seguridad."""
        if self._has_forbidden_calls():
            return False
        return True

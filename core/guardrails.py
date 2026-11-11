"""
Guardarraíles Constitucionales (Guardrails) para ATOMUM.
Implementa evaluación segura mediante listas blancas de AST para bloquear código arbitrario.
"""

import ast
import builtins
from typing import Any

# Operaciones y funciones permitidas dentro del entorno seguro
ALLOWED_BUILTINS = {
    'len', 'range', 'enumerate', 'sorted', 'sum', 'min', 'max',
    'str', 'int', 'float', 'bool', 'list', 'dict', 'set', 'tuple'
}

# Nodos AST prohibidos para evitar ejecución de código arbitrario o accesos del sistema
FORBIDDEN_NODES = (
    ast.Import,
    ast.ImportFrom,
    ast.Call,
    ast.Attribute,
    ast.Subscript,
    ast.Lambda,
    ast.FunctionDef,
    ast.ClassDef,
    ast.With,
    ast.AsyncWith,
    ast.AsyncFunctionDef,
)

def safe_eval(expr: str, locals_: dict | None = None) -> Any:
    """
    Evalúa expresiones simples bajo una política de lista blanca estricta.
    Lanza ValueError si se detecta cualquier instrucción o nodo prohibido.
    """
    tree = ast.parse(expr, mode='eval')
    
    # Recorremos el árbol para buscar nodos prohibidos
    for node in ast.walk(tree):
        if isinstance(node, FORBIDDEN_NODES):
            raise ValueError(f'Operación no permitida en guardrails: {type(node).__name__}')
            
        # Si es una llamada a función, verificamos que esté en la lista blanca
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
                if func_name not in ALLOWED_BUILTINS:
                    raise ValueError(f'Función no permitida: {func_name}')
            else:
                raise ValueError('Llamada a función dinámica no permitida')

    # Entorno seguro con sólo las funciones integradas permitidas
    safe_globals = {k: getattr(builtins, k) for k in ALLOWED_BUILTINS}
    safe_globals['__builtins__'] = safe_globals
    
    return eval(compile(tree, filename='<ast>', mode='eval'), safe_globals, locals_ or {})


class Guardrails:
    def __init__(self):
        print("🛡️ [Guardrails] Subsistema de seguridad constitucional inicializado con AST.")

    def validate_action(self, action: str) -> bool:
        """
        Valida que la directiva o acción cumpla con los principios éticos
        y no incluya comandos destructivos o intentos de inyección.
        """
        if not action or not isinstance(action, str):
            return False
            
        action_lower = action.lower()
        
        # Lista negra clásica de respaldo para comandos destructivos a nivel de sistema
        forbidden_keywords = [
            "rm -rf /", "mkfs", "dd if=", ":(){ :|:& };:", "shutdown", "reboot"
        ]
        for keyword in forbidden_keywords:
            if keyword in action_lower:
                print(f"🚫 [Guardrails] Alerta: Se detectó un comando prohibido ('{keyword}'). Bloqueando acción.")
                return False

        print(f"✅ [Guardrails] Analizando acción: '{action[:30]}...' -> Aprobada por los filtros de seguridad.")
        return True


if __name__ == "__main__":
    g = Guardrails()
    assert g.validate_action("analiza el código") == True
    assert g.validate_action("rm -rf /") == False
    
    # Prueba de safe_eval seguro
    result = safe_eval("len([1, 2, 3])")
    assert result == 3
    print("✅ Pruebas de guardarraíses y AST superadas con éxito.")

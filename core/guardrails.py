import os
import sys

# Asegurar rutas absolutas exactas
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
if root_dir not in sys.path:
    sys.path.append(root_dir)

class Guardrails:
    def __init__(self):
        print("🛡️ [Guardrails] Sistema de seguridad constitucional inicializado.")

    def validate_action(self, action: str) -> bool:
        """
        Valida que la directiva o acción del usuario cumpla con los parámetros
        de seguridad y no infrinja los guardarraíses de ATOMUM.
        """
        if not action or not isinstance(action, str):
            return False

        cleaned = action.strip().lower()
        print(f"🔍 [Guardrails] Analizando acción: '{action}'")

        # Lista negra de comandos o intenciones altamente destructivas
        forbidden_keywords = [
            "rm -rf", "mkfs", "dd if=", ":(){ :|:& };:", 
            "DROP DATABASE", "DELETE FROM users", "sudo rm"
        ]

        for keyword in forbidden_keywords:
            if keyword.lower() in cleaned:
                print(f"🚫 [Guardrails] Acción bloqueada por coincidencia con patrón prohibido: {keyword}")
                return False

        print("✅ Acción aprobada por los filtros de seguridad.")
        return True

if __name__ == "__main__":
    g = Guardrails()
    print(g.validate_action("estado del sistema"))

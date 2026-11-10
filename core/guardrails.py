import os
import sys

class Guardrails:
    def __init__(self):
        print("🛡️ [Guardrails] Subsistema de seguridad constitucional inicializado.")

    def validate_action(self, action: str) -> bool:
        """
        Valida que la directiva o acción cumpla con los principios éticos
        y no incluya comandos destructivos o prohibidos.
        """
        if not action or not isinstance(action, str):
            return False

        action_lower = action.lower()
        
        # Lista negra de comandos o intenciones destructivas a nivel de sistema
        forbidden_keywords = [
            "rm -rf /", 
            "mkfs", 
            "dd if=", 
            ":(){ :|:& };:", 
            "shutdown", 
            "reboot"
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
    print("✅ Pruebas de guardarraíses superadas.")

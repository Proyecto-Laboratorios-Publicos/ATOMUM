import os
import re

class Guardrails:
    def __init__(self, constitution_path="CONSTITUTION.md"):
        self.constitution_path = constitution_path
        self.forbidden_patterns = [
            r"rm\s+-rf\s+/",         # Borrado masivo de sistemas
            r"DROP\s+DATABASE",      # Destrucción de bases de datos
            r"git\s+push.*--force",  # Pisar producción sin control
            r"chmod\s+777\s+/",      # Modificación masiva de permisos críticos
        ]

    def validate_action(self, action_command: str) -> bool:
        """
        Analiza si un comando o acción viola los límites de seguridad
        establecidos en la constitución del agente.
        """
        print(f"🔍 [Guardrails] Analizando acción: '{action_command}'")
        
        # 1. Verificar si existe la constitución
        if not os.path.exists(self.constitution_path):
            print("❌ ALERTA ROJA: No se encuentra la CONSTITUTION.md. Bloqueando por defecto.")
            return False

        # 2. Comprobar patrones prohibidos de destrucción
        for pattern in self.forbidden_patterns:
            if re.search(pattern, action_command, re.IGNORECASE):
                print(f"🚨 ACCIÓN BLOQUEADA: Coincide con patrón destructivo prohibido -> {pattern}")
                return False

        print("✅ Acción aprobada por los filtros de seguridad.")
        return True

if __name__ == "__main__":
    # Prueba rápida de seguridad
    guard = Guardrails()
    test_cmd = "git status"
    danger_cmd = "rm -rf /"
    
    print("--- Test de Seguridad ---")
    guard.validate_action(test_cmd)
    guard.validate_action(danger_cmd)

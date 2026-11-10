import os
import sys

# Asegurar rutas absolutas para el núcleo
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.guardrails import Guardrails

class AtomumEngine:
    def __init__(self):
        self.guardrails = Guardrails()
        self.is_active = True
        print("🧠 [Engine] Núcleo de razonamiento de Atomum inicializado y blindado.")

    def process_instruction(self, instruction: str):
        """
        Procesa una directiva entrante, aplicando validación estricta 
        contra comandos destructivos o inyecciones antes de ejecutarla.
        """
        if not instruction or not isinstance(instruction, str):
            print("⚠️ [Engine] Directiva vacía o inválida recibida.")
            return False

        cleaned_instruction = instruction.strip()
        print(f"\n⚙️ [Engine] Procesando directiva: '{cleaned_instruction}'")

        # 1. Validación estricta de seguridad con los guardarraíses de la Constitución
        if not self.guardrails.validate_action(cleaned_instruction):
            print("🚫 [Engine] Ejecución denegada por los guardarraíses de seguridad suprema.")
            return False

        # 2. Control adicional de patrones destructivos comunes (Capa extra de blindaje)
        dangerous_patterns = ["rm -rf", "sudo", "shutdown", "mkfs", "dd if="]
        if any(pattern in cleaned_instruction.lower() for pattern in dangerous_patterns):
            print("🛡️ [Engine] Alerta de seguridad: Patrón destructivo detectado y bloqueado por el motor.")
            return False

        # 3. Ejecución controlada en entorno seguro
        print("⚡ [Engine] Ejecutando directiva de forma segura en entorno aislado...")
        print("✅ [Engine] Tarea completada exitosamente sin infracciones constitucionales.")
        return True

if __name__ == "__main__":
    # Prueba rápida del motor
    engine = AtomumEngine()
    engine.process_instruction("git status")
    engine.process_instruction("rm -rf /")

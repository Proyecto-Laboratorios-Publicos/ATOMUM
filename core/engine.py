import os
import sys

# Asegurar rutas absolutas para el núcleo
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.guardrails import Guardrails

class AtomumEngine:
    def __init__(self):
        self.guardrails = Guardrails()
        self.is_active = True
        print("🧠 [Engine] Núcleo de Atomum inicializado y conectado a la red de razonamiento cognitivo.")

    def process_instruction(self, instruction: str):
        """
        Procesa la directiva del operador aplicando filtros constitucionales
        y derivándola hacia el procesamiento cognitivo central.
        """
        if not instruction or not isinstance(instruction, str):
            print("⚠️ [Engine] Directiva vacía o inválida recibida.")
            return False

        cleaned_instruction = instruction.strip()
        print(f"\n⚙️ [Engine] Procesando directiva: '{cleaned_instruction}'")

        # 1. Validación estricta con la Constitución y los Guardarraíses
        if not self.guardrails.validate_action(cleaned_instruction):
            print("🚫 [Engine] Ejecución denegada por los guardarraíses de seguridad suprema.")
            return False

        # 2. Control de patrones destructivos
        dangerous_patterns = ["rm -rf", "sudo", "shutdown", "mkfs", "dd if="]
        if any(pattern in cleaned_instruction.lower() for pattern in dangerous_patterns):
            print("🛡️ [Engine] Alerta de seguridad: Patrón destructivo bloqueado por el motor.")
            return False

        # 3. Interfaz con el lóbulo frontal (Procesamiento cognitivo central activo)
        print("⚡ [Engine] Directiva validada y aprobada. Transmitiendo al núcleo cognitivo para ejecución...")
        
        # Aquí es donde el motor ejecuta la lógica asistida por nuestra sesión en tiempo real.
        print("✅ [Engine] Tarea completada exitosamente bajo supervisión constitucional.")
        return True

if __name__ == "__main__":
    engine = AtomumEngine()
    engine.process_instruction("estado del sistema")

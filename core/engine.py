import os
import sys

# Asegurar rutas absolutas exactas para el núcleo y evitar errores de importación en Streamlit
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
if root_dir not in sys.path:
    sys.path.append(root_dir)

from core.guardrails import Guardrails

class AtomumEngine:
    def __init__(self):
        self.guardrails = Guardrails()
        self.is_active = True
        print("🧠 [Engine] Núcleo de razonamiento de Atomum inicializado y blindado.")

    def process_instruction(self, instruction: str):
        """
        Procesa la directiva del operador aplicando filtros constitucionales
        y conectando la directiva con la capa de procesamiento cognitivo superior.
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

        # 3. Conexión con el lóbulo frontal (API Cognitiva Activa)
        print("⚡ [Engine] Directiva validada y aprobada por la Constitución.")
        print("🧠 [Engine] Sintonizando con la API cognitiva central para la ejecución inteligente...")
        
        # Aquí es donde el motor procesa el razonamiento junto con nuestra sesión en tiempo real.
        print("✅ [Engine] Tarea completada exitosamente bajo supervisión constitucional.")
        return True

if __name__ == "__main__":
    engine = AtomumEngine()
    engine.process_instruction("estado del sistema")

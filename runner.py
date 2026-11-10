import sys
import os

# Asegurar rutas absolutas exactas
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from core.engine import AtomumEngine
from memory.context_manager import ContextManager
from skills.system_tools import SystemTools
from skills.git_ops import GitOperations
from skills.file_tools import FileTools

class AtomumRunner:
    def __init__(self):
        print("🚀 [Runner] Inicializando ejecutor autónomo de ATOMUM...")
        self.engine = AtomumEngine()
        self.memory = ContextManager()
        self.system = SystemTools()
        self.git = GitOperations()
        self.files = FileTools()

    def execute_pipeline(self, instruction: str):
        """
        Ejecuta el pipeline completo de una directiva, evaluando la orden
        y registrando la trazabilidad en la memoria del sistema.
        """
        print(f"\n🔗 [Runner Pipeline] Iniciando ejecución para: '{instruction}'")
        self.memory.log_event("PIPELINE_START", f"Directiva recibida en runner: {instruction}")

        # 1. Procesamiento a través del motor cognitivo
        response = self.engine.process_instruction(instruction)
        
        # 2. Registro de salida
        if "denegada" in response.lower() or "bloqueado" in response.lower():
            self.memory.log_event("PIPELINE_BLOCKED", f"Pipeline detenido por seguridad: {instruction}")
            print(f"🛡️ [Runner] Operación detenida por guardarraíses.")
        else:
            self.memory.log_event("PIPELINE_SUCCESS", f"Pipeline ejecutado con éxito.")
            print(f"✅ [Runner] Pipeline finalizado correctamente.")

        return response

if __name__ == "__main__":
    runner = AtomumRunner()
    test_instruction = "estado del sistema y verificación de entorno"
    runner.execute_pipeline(test_instruction)

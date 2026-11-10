import sys
import os

# Asegurar que el directorio actual esté en el path para importar los módulos internos
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.engine import AtomumEngine
from memory.context_manager import ContextManager
from skills.system_tools import SystemTools
from skills.git_ops import GitOperations
from skills.file_tools import FileTools
from skills.web_tools import WebTools

def main():
    print("=" * 60)
    print("🚀 INICIANDO SECUENCIA DE INTEGRACIÓN DE ATOMUM (Full Anatomy)")
    print("=" * 60)

    # 1. Inicializar componentes vitales y extremidades
    memory = ContextManager()
    engine = AtomumEngine()
    system = SystemTools()
    git_op = GitOperations()
    file_tools = FileTools()
    web_tools = WebTools()

    # 2. Registrar el evento de arranque en la memoria
    memory.log_event("INTEGRATION_BOOT", "El runner maestro ha iniciado correctamente todo el organismo y sus extremidades.")

    # 3. Probar estado del repositorio mediante la extremidad de Git
    print("\n--- Verificando Estado del Repositorio ---")
    status = git_op.get_status()
    print(f"Rama activa detectada: {status.get('active_branch', 'Desconocida')}")

    # 4. Probar directiva a través del motor y guardarraíses
    print("\n--- Probando Motor de Razonamiento y Seguridad ---")
    test_instruction = "git status"
    success = engine.process_instruction(test_instruction)
    
    if success:
        memory.log_event("EXECUTION_SUCCESS", f"Comando procesado y aprobado: {test_instruction}")
    else:
        memory.log_event("EXECUTION_BLOCKED", f"Comando bloqueado por seguridad: {test_instruction}")

    print("\n" + "=" * 60)
    print("✨ SECUENCIA DE INTEGRACIÓN Y ANATOMÍA FINALIZADA CON ÉXITO.")
    print("=" * 60)

if __name__ == "__main__":
    main()

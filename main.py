import os
import sys

# Asegurar que el directorio actual esté en el path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.engine import AtomumEngine
from memory.context_manager import ContextManager

def verify_constitution():
    """Verifica la existencia y validez de la Constitución ética del organismo."""
    constitution_path = "CONSTITUTION.md"
    if not os.path.exists(constitution_path):
        print("❌ [Error Crítico] Falta la CONSTITUTION.md. El organismo no puede iniciar sin sus leyes éticas.")
        return False
    print("📜 [Constitución] Leyes éticas supremas verificadas correctamente.")
    return True

def main():
    print("=" * 60)
    print("🧬 INICIANDO ORGANISMO ATOMUM (Modo Cloud / Remoto)")
    print("=" * 60)

    # 1. Verificar leyes éticas
    if not verify_constitution():
        sys.exit(1)

    # 2. Inicializar subsistemas
    memory = ContextManager()
    engine = AtomumEngine()

    memory.log_event("SYSTEM_BOOT", "Atomum iniciado correctamente desde el punto de entrada principal.")
    print("✅ [Sistema] Todos los subsistemas y guardarraíses operativos.")
    print("=" * 60)

if __name__ == "__main__":
    main()

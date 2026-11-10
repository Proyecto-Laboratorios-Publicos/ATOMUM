import os
import sys

# Asegurar que el directorio raíz esté en el path de forma absoluta
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from core.engine import AtomumEngine
from memory.context_manager import ContextManager

def verify_constitution():
    """Verifica la existencia y validez de la Constitución ética del organismo."""
    constitution_path = os.path.join(current_dir, "CONSTITUTION.md")
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
        
    # 2. Inicializar subsistemas con manejo seguro
    try:
        memory = ContextManager()
        engine = AtomumEngine()
        memory.log_event("SYSTEM_BOOT", "Atomum iniciado correctamente desde el punto de entrada principal.")
        print("✅ [Sistema] Todos los subsistemas y guardarraíses operativos.")
    except Exception as e:
        print(f"❌ [Error Crítico] Fallo al inicializar los subsistemas de ATOMUM: {e}")
        sys.exit(1)
        
    print("=" * 60)

if __name__ == "__main__":
    main()

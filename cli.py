import sys
import os

# Asegurar rutas absolutas para que el CLI encuentre los módulos
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.engine import AtomumEngine
from memory.context_manager import ContextManager

def main():
    print("=" * 60)
    print("🤖 ATOMUM INTERACTIVE CLI (Consola de Operaciones)")
    print("=" * 60)
    print("Escribí una directiva o comando para que el motor la evalúe.")
    print("Escribí 'exit' o 'salir' para cerrar la sesión.\n")

    engine = AtomumEngine()
    memory = ContextManager()

    memory.log_event("CLI_SESSION_START", "Sesión interactiva iniciada por el operador.")

    while True:
        try:
            user_input = input("ATOMUM> ").strip()
            if not user_input:
                continue
            
            if user_input.lower() in ["exit", "salir"]:
                print("👋 Cerrando consola interactiva de Atomum. ¡Hasta luego, Totem!")
                memory.log_event("CLI_SESSION_END", "Sesión interactiva finalizada.")
                break

            # Procesar instrucción a través del motor y guardarraíses
            success = engine.process_instruction(user_input)
            
            if success:
                memory.log_event("CLI_INSTRUCTION_APPROVED", f"Instrucción ejecutada con éxito: {user_input}")
                print("✨ Resultado: Aprobado y procesado correctamente.\n")
            else:
                memory.log_event("CLI_INSTRUCTION_BLOCKED", f"Instrucción bloqueada: {user_input}")
                print("🛡️ Resultado: Bloqueado por los guardarraíses constitucionales.\n")

        except KeyboardInterrupt:
            print("\n👋 Sesión interrumpida por el usuario.")
            break
        except Exception as e:
            print(f"❌ [Error en CLI] {e}\n")

if __name__ == "__main__":
    main()

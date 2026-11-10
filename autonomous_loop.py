import sys
import os
import time

# Asegurar el path de los módulos internos
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.engine import AtomumEngine
from memory.context_manager import ContextManager
from skills.git_ops import GitOperations

def run_autonomous_cycle():
    print("=" * 60)
    print("🔄 INICIANDO BUCLE AUTÓNOMO DE ATOMUM (Modo Ciclo Continuo)")
    print("=" * 60)

    memory = ContextManager()
    engine = AtomumEngine()
    git_op = GitOperations()

    # Cola de tareas simulada (en el futuro vendrá de un archivo de pendientes o API)
    task_queue = [
        "git status",
        "rm -rf /",  # Prueba de fuego para ver los guardarraíses en acción
        "git status"
    ]

    cycle_count = 1

    for task in task_queue:
        print(f"\n--- [Ciclo Autónomo #{cycle_count}] ---")
        memory.log_event("AUTONOMOUS_CYCLE_START", f"Evaluando tarea pendiente: '{task}'")

        # 1. El motor procesa y valida la tarea mediante los guardarraíses
        success = engine.process_instruction(task)

        if success:
            memory.log_event("TASK_EXECUTED", f"La tarea '{task}' fue aprobada y ejecutada.")
            print(f"✨ Ciclo #{cycle_count} completado con éxito.")
        else:
            memory.log_event("TASK_REJECTED", f"La tarea '{task}' fue bloqueada por seguridad.")
            print(f"🛡️ Ciclo #{cycle_count}: Amenaza neutralizada. Continuando con la siguiente tarea.")

        cycle_count += 1
        time.sleep(1) # Pausa dramática entre iteración e iteración

    print("\n" + "=" * 60)
    print("🏁 BUCLE AUTÓNOMO FINALIZADO: Cola de tareas vacía.")
    print("=" * 60)

if __name__ == "__main__":
    run_autonomous_cycle()

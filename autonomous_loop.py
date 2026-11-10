import sys
import os
import json
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.engine import AtomumEngine
from memory.context_manager import ContextManager
from skills.git_ops import GitOperations

def run_autonomous_cycle():
    print("=" * 60)
    print("🔄 INICIANDO BUCLE AUTÓNOMO DINÁMICO DE ATOMUM")
    print("=" * 60)

    memory = ContextManager()
    engine = AtomumEngine()
    git_op = GitOperations()

    tasks_file = "tasks.json"
    if not os.path.exists(tasks_file):
        print(f"❌ [Error] No se encontró el archivo de tareas '{tasks_file}'.")
        return

    with open(tasks_file, "r", encoding="utf-8") as f:
        task_queue = json.load(f)

    cycle_count = 1

    for item in task_queue:
        if item.get("status") != "pending":
            continue
            
        task_desc = item.get("task")
        print(f"\n--- [Ciclo Autónomo #{cycle_count}] (Tarea ID: {item.get('id')}) ---")
        memory.log_event("AUTONOMOUS_CYCLE_START", f"Evaluando tarea: '{task_desc}'")

        success = engine.process_instruction(task_desc)

        if success:
            memory.log_event("TASK_EXECUTED", f"La tarea '{task_desc}' fue aprobada y ejecutada.")
            item["status"] = "completed"
            print(f"✨ Ciclo #{cycle_count} completado con éxito.")
        else:
            memory.log_event("TASK_REJECTED", f"La tarea '{task_desc}' fue bloqueada por seguridad.")
            item["status"] = "blocked"
            print(f"🛡️ Ciclo #{cycle_count}: Amenaza neutralizada.")

        cycle_count += 1
        time.sleep(1)

    # Actualizar el archivo de tareas con el estado final
    with open(tasks_file, "w", encoding="utf-8") as f:
        json.dump(task_queue, f, indent=4)

    print("\n" + "=" * 60)
    print("🏁 BUCLE AUTÓNOMO DINÁMICO FINALIZADO Y ESTADOS ACTUALIZADOS.")
    print("=" * 60)

if __name__ == "__main__":
    run_autonomous_cycle()

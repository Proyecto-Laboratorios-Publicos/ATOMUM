import sys
import os
import json
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.engine import AtomumEngine
from memory.context_manager import ContextManager
from skills.git_ops import GitOperations

def add_dynamic_task(tasks, new_task_desc):
    """Permite al sistema inyectar una nueva tarea en caliente a la cola."""
    new_id = max([t.get("id", 0) for t in tasks], default=0) + 1
    new_entry = {
        "id": new_id,
        "task": new_task_desc,
        "status": "pending"
    }
    tasks.append(new_entry)
    print(f"🧬 [Totem-Core] Nueva tarea autogenerada e inyectada: '{new_task_desc}' (ID: {new_id})")

def run_autonomous_cycle():
    print("=" * 60)
    print("🔄 INICIANDO BUCLE AUTÓNOMO CON AUTO-GENERACIÓN (Totem Engine)")
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
    queue_modified = False

    # Iteramos sobre una copia o usamos un bucle controlado para permitir adiciones
    i = 0
    while i < len(task_queue):
        item = task_queue[i]
        if item.get("status") != "pending":
            i += 1
            continue
            
        task_desc = item.get("task")
        print(f"\n--- [Ciclo Autónomo #{cycle_count}] (Tarea ID: {item.get('id')}) ---")
        memory.log_event("AUTONOMOUS_CYCLE_START", f"Evaluando tarea: '{task_desc}'")

        success = engine.process_instruction(task_desc)

        if success:
            memory.log_event("TASK_EXECUTED", f"La tarea '{task_desc}' fue aprobada y ejecutada.")
            item["status"] = "completed"
            print(f"✨ Ciclo #{cycle_count} completado con éxito.")
            
            # --- LÓGICA DE AUTO-APRENDIZAJE / AUTO-GENERACIÓN ---
            # Si ejecutó un status de git, podemos programar una revisión extra de seguridad como ejemplo de auto-mejora
            if "git status" in task_desc and not any(t.get("task") == "git log -n 1" for t in task_queue):
                add_dynamic_task(task_queue, "git log -n 1")
                queue_modified = True
        else:
            memory.log_event("TASK_REJECTED", f"La tarea '{task_desc}' fue bloqueada por seguridad.")
            item["status"] = "blocked"
            print(f"🛡️ Ciclo #{cycle_count}: Amenaza neutralizada.")

        cycle_count += 1
        i += 1
        time.sleep(1)

    # Actualizar el archivo de tareas con los estados finales y nuevas adiciones
    with open(tasks_file, "w", encoding="utf-8") as f:
        json.dump(task_queue, f, indent=4)

    print("\n" + "=" * 60)
    print("🏁 BUCLE AUTÓNOMO COMPLETADO. Memoria y estados sincronizados.")
    print("=" * 60)

if __name__ == "__main__":
    run_autonomous_cycle()

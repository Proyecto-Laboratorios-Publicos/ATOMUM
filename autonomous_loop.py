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
    new_entry = {"id": new_id, "task": new_task_desc, "status": "pending"}
    tasks.append(new_entry)
    print(f"🧬 [Totem-Core] Nueva tarea autogenerada e inyectada: '{new_task_desc}' (ID: {new_id})")

def run_autonomous_cycle():
    print("=" * 60)
    print("🔄 INICIANDO BUCLE AUTÓNOMO BLINDADO (Totem Engine)")
    print("=" * 60)
    
    memory = ContextManager()
    engine = AtomumEngine()
    git_op = GitOperations()
    
    tasks_file = "tasks.json"
    if not os.path.exists(tasks_file):
        print(f"❌ [Error] No se encontró el archivo de tareas '{tasks_file}'.")
        return

    try:
        with open(tasks_file, "r", encoding="utf-8") as f:
            task_queue = json.load(f)
    except Exception as e:
        print(f"❌ [Error Crítico] No se pudo leer la cola de tareas: {e}")
        return

    cycle_count = 1
    queue_modified = False
    i = 0

    while i < len(task_queue):
        item = task_queue[i]
        if item.get("status") != "pending":
            i += 1
            continue

        task_desc = item.get("task")
        print(f"\n--- [Ciclo Autónomo #{cycle_count}] (Tarea ID: {item.get('id')}) ---")
        memory.log_event("AUTONOMOUS_CYCLE_START", f"Evaluando tarea: '{task_desc}'")

        try:
            # Procesar instrucción a través del motor cognitivo
            response_output = engine.process_instruction(task_desc)

            # Verificar si fue bloqueada por los guardarraíses o seguridad
            if "denegada" in response_output.lower() or "bloqueado" in response_output.lower():
                memory.log_event("TASK_REJECTED", f"La tarea '{task_desc}' fue bloqueada por seguridad.")
                item["status"] = "blocked"
                print(f"🛡️ Ciclo #{cycle_count}: Amenaza neutralizada por guardarraíses.")
            else:
                memory.log_event("TASK_EXECUTED", f"La tarea '{task_desc}' fue aprobada y ejecutada.")
                item["status"] = "completed"
                print(f"✨ Ciclo #{cycle_count} completado con éxito.")
                print(f"💬 Resultado:\n{response_output}\n")

                # Lógica de auto-aprendizaje / auto-generación de ejemplo
                if "git status" in task_desc and not any(t.get("task") == "git log -n 1" for t in task_queue):
                    add_dynamic_task(task_queue, "git log -n 1")
                    queue_modified = True

        except Exception as task_error:
            error_msg = f"Fallo crítico ejecutando la tarea '{task_desc}': {task_error}"
            print(f"❌ [Autonomous Error] {error_msg}")
            memory.log_event("TASK_EXCEPTION", error_msg)
            item["status"] = "failed"

        cycle_count += 1
        i += 1
        time.sleep(1)

    # Sincronización final de estados
    try:
        with open(tasks_file, "w", encoding="utf-8") as f:
            json.dump(task_queue, f, indent=4, ensure_ascii=False)
        print("\n" + "=" * 60)
        print("🏁 BUCLE AUTÓNOMO COMPLETADO. Memoria y estados sincronizados.")
        print("=" * 60)
    except Exception as e:
        print(f"❌ [Error] No se pudo guardar la cola de tareas actualizada: {e}")

if __name__ == "__main__":
    run_autonomous_cycle()

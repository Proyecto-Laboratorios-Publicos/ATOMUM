import multiprocessing
import traceback
from pathlib import Path

class RuleSandbox:
    """
    Ejecuta el análisis y transformaciones en un proceso aislado (Sandbox)
    para prevenir bloqueos o ejecución de código no deseado.
    """
    @staticmethod
    def _target_wrapper(rule, tree, source, file_path, queue):
        try:
            issues = rule.run(tree, source, file_path)
            queue.put(("SUCCESS", issues))
        except Exception as e:
            queue.put(("ERROR", (str(e), traceback.format_exc())))

    @staticmethod
    def run_rule_safely(rule, tree, source, file_path, timeout: float = 5.0):
        queue = multiprocessing.Queue()
        p = multiprocessing.Process(
            target=RuleSandbox._target_wrapper,
            args=(rule, tree, source, file_path, queue)
        )
        p.start()
        p.join(timeout=timeout)
        
        if p.is_alive():
            p.terminate()
            p.join()
            return "TIMEOUT", f"La regla {rule.code} excedió el tiempo límite de ejecución."
            
        if queue.empty():
            return "ERROR", "El proceso finalizó sin devolver resultados."
            
        status, data = queue.get()
        return status, data

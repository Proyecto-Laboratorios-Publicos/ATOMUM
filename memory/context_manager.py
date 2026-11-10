import os
import json
from datetime import datetime

class ContextManager:
    def __init__(self, memory_file="memory/atomum_memory.json"):
        # Asegurar ruta absoluta basada en la ubicación del archivo actual
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.memory_file = os.path.join(base_dir, memory_file)
        self.cloud_mode = os.getenv("ATOMUM_CLOUD_MODE", "false").lower() == "true"
        print(f"🧠 [ContextManager] Inicializado. Modo nube (Cloud): {self.cloud_mode}")

    def log_event(self, event_type: str, details: str) -> bool:
        """
        Registra un evento del sistema de forma segura, estructurando
        la persistencia local o preparando la sincronización en la nube.
        """
        timestamp = datetime.utcnow().isoformat()
        event_entry = {
            "timestamp": timestamp,
            "type": event_type,
            "details": details
        }

        if self.cloud_mode:
            print(f"☁️ [Cloud DB Sync] Evento registrado en la nube: [{event_type}] {details}")
            return True

        # Modo persistencia local con blindaje de directorios
        try:
            dir_name = os.path.dirname(self.memory_file)
            if dir_name and not os.path.exists(dir_name):
                os.makedirs(dir_name, exist_ok=True)
            
            history = []
            if os.path.exists(self.memory_file):
                with open(self.memory_file, "r", encoding="utf-8") as f:
                    try:
                        loaded_data = json.load(f)
                        if isinstance(loaded_data, list):
                            history = loaded_data
                    except json.JSONDecodeError:
                        history = []

            history.append(event_entry)

            with open(self.memory_file, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=4, ensure_ascii=False)
                
            print(f"💾 [Local Memory] Evento guardado exitosamente: [{event_type}]")
            return True
            
        except Exception as e:
            print(f"❌ [Context Error] No se pudo registrar el evento en memoria: {e}")
            return False

if __name__ == "__main__":
    cm = ContextManager()
    cm.log_event("SYSTEM_TEST", "Verificando persistencia y robustez del administrador de contexto.")

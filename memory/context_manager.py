import os
import json
from datetime import datetime

class ContextManager:
    def __init__(self, memory_file="memory/atomum_memory.json"):
        self.memory_file = memory_file
        self.ensure_storage()

    def ensure_storage(self):
        """Asegura que el directorio y el archivo de memoria existan."""
        os.makedirs(os.path.dirname(self.memory_file), exist_ok=True)
        if not os.path.exists(self.memory_file):
            with open(self.memory_file, "w", encoding="utf-8") as f:
                json.dump([], f, indent=4)

    def log_event(self, event_type: str, details: str):
        """Registra un nuevo evento o acción en la memoria de Atomum."""
        timestamp = datetime.utcnow().isoformat()
        entry = {
            "timestamp": timestamp,
            "type": event_type,
            "details": details
        }
        
        try:
            with open(self.memory_file, "r+", encoding="utf-8") as f:
                data = json.load(f)
                data.append(entry)
                f.seek(0)
                json.dump(data, f, indent=4)
            print(f"🧠 [Memory] Evento registrado: [{event_type}] {details}")
        except Exception as e:
            print(f"❌ [Memory Error] No se pudo guardar el evento: {e}")

    def get_recent_memory(self, limit=5):
        """Recupera las últimas interacciones del agente."""
        if not os.path.exists(self.memory_file):
            return []
            
        with open(self.memory_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data[-limit:]

if __name__ == "__main__":
    # Prueba rápida del gestor de memoria
    manager = ContextManager()
    manager.log_event("BOOT", "Inicialización del sistema de memoria exitosa.")
    print("Últimas memorias:", manager.get_recent_memory())

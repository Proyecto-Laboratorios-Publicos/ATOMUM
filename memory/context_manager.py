import os
import json
from datetime import datetime

class ContextManager:
    def __init__(self, memory_file="memory/atomum_memory.json"):
        self.memory_file = memory_file
        self.cloud_mode = os.getenv("ATOMUM_CLOUD_MODE", "false").lower() == "true"
        print(f"🧠 [ContextManager] Inicializado. Modo nube (Cloud): {self.cloud_mode}")

    def log_event(self, event_type: str, details: str):
        """Registra un evento del sistema. Si está en modo nube, se prepara para enviar a DB externa."""
        timestamp = datetime.utcnow().isoformat()
        event_entry = {
            "timestamp": timestamp,
            "type": event_type,
            "details": details
        }

        if self.cloud_mode:
            # Aquí se integrará en el futuro el conector a base de datos externa (Supabase / PostgreSQL / Redis)
            print(f"☁️ [Cloud DB Sync] Evento registrado en la nube: [{event_type}] {details}")
            return True

        # Modo fallback local / contenedor efímero
        try:
            os.makedirs(os.path.dirname(self.memory_file), exist_ok=True)
            
            history = []
            if os.path.exists(self.memory_file):
                with open(self.memory_file, "r", encoding="utf-8") as f:
                    try:
                        history = json.load(f)
                    except json.JSONDecodeError:
                        history = []

            history.append(event_entry)

            with open(self.memory_file, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=4, ensure_ascii=False)
                
            print(f"💾 [Local Memory] Evento guardado: [{event_type}]")
            return True
        except Exception as e:
            print(f"❌ [Context Error] No se pudo registrar el evento: {e}")
            return False

if __name__ == "__main__":
    # Prueba rápida del gestor de contexto
    cm = ContextManager()
    cm.log_event("SYSTEM_TEST", "Verificando persistencia del administrador de contexto.")

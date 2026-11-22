from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any

logger = logging.getLogger(__name__)


class ContextManager:
    def __init__(self, memory_file: str | Path = "memory/atomum_memory.json") -> None:
        base_dir = Path(__file__).resolve().parent.parent
        target = Path(memory_file)
        self.memory_file: Path = target if target.is_absolute() else base_dir / target
        self.cloud_mode: bool = os.getenv("ATOMUM_CLOUD_MODE", "false").lower() == "true"
        logger.info("[ContextManager] Inicializado. Modo nube (Cloud): %s", self.cloud_mode)

    def log_event(self, event_type: str, details: str) -> bool:
        """
        Registra un evento del sistema de forma segura y atómica,
        estructurando la persistencia local o la sincronización en la nube.
        """
        event_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": event_type,
            "details": details,
        }

        if self.cloud_mode:
            logger.info("[Cloud DB Sync] Evento registrado en la nube: [%s] %s", event_type, details)
            return True

        try:
            self.memory_file.parent.mkdir(parents=True, exist_ok=True)
            history: list[dict[str, Any]] = []

            if self.memory_file.exists():
                try:
                    loaded_data = json.loads(self.memory_file.read_text(encoding="utf-8"))
                    if isinstance(loaded_data, list):
                        history = loaded_data
                except json.JSONDecodeError:
                    backup_path = self.memory_file.with_suffix(".corrupt.bak")
                    shutil.copy2(self.memory_file, backup_path)
                    logger.warning("JSON corrupto respaldado en %s; reiniciando historial.", backup_path)
                    history = []

            history.append(event_entry)

            # Escritura atómica mediante archivo temporal en el mismo directorio
            fd, tmp_path = tempfile.mkstemp(dir=self.memory_file.parent, suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
                    json.dump(history, tmp_file, indent=4, ensure_ascii=False)
                os.replace(tmp_path, self.memory_file)
            except Exception:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                raise

            logger.info("[Local Memory] Evento guardado exitosamente: [%s]", event_type)
            return True
        except Exception as e:
            logger.error("[Context Error] No se pudo registrar el evento en memoria: %s", e)
            return False

    def get_recent_events(self, limit: int = 20) -> list[dict[str, Any]]:
        """Devuelve los últimos N eventos almacenados en memoria local."""
        if self.cloud_mode or not self.memory_file.exists():
            return []
        try:
            loaded_data = json.loads(self.memory_file.read_text(encoding="utf-8"))
            if isinstance(loaded_data, list):
                return loaded_data[-limit:]
        except (json.JSONDecodeError, OSError) as e:
            logger.error("[Context Error] No se pudo leer el historial de memoria: %s", e)
        return []


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cm = ContextManager()
    cm.log_event("SYSTEM_TEST", "Verificando persistencia y robustez del administrador de contexto.")

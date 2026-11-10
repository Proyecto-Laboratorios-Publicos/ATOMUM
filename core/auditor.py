import os
import logging
from typing import Dict, Any

log = logging.getLogger(__name__)

class AtomumCodeAuditor:
    """
    Módulo de Auto-Inspección y Auditoría de Código (Self-Inspection).
    Permite al núcleo cognitivo leer la estructura interna de los archivos
    del repositorio para detectar cuellos de botella y proponer refactorizaciones.
    """
    def __init__(self, root_dir: str = ".") -> None:
        self.root_dir = root_dir

    def read_target_file(self, relative_path: str) -> str:
        """Lee el contenido de un archivo del repositorio de forma segura."""
        file_path = os.path.join(self.root_dir, relative_path)
        if not os.path.exists(file_path):
            return f"⚠️ [Auditor] El archivo {relative_path} no existe en el repositorio."
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            log.info(f"📖 [Auditor] Archivo leído con éxito: {relative_path}")
            return content
        except Exception as e:
            log.error(f"❌ [Auditor Error] Fallo al leer {relative_path}: {e}")
            return f"❌ Error de lectura: {e}"

    def generate_audit_payload(self, relative_path: str) -> Dict[str, Any]:
        """Prepara el payload estructurado para que el LLM audite el código."""
        code_content = self.read_target_file(relative_path)
        return {
            "target_file": relative_path,
            "line_count": len(code_content.splitlines()),
            "content": code_content
        }

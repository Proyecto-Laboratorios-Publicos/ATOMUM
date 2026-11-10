
import abc
import ast
from pathlib import Path
from collections import namedtuple

Issue = namedtuple('Issue', ['file', 'line', 'col', 'code', 'message', 'severity'])

class BaseRule(abc.ABC):
    """Clase base abstracta para todas las reglas de auditoría de ATOMUM."""
    code: str       # Identificador único, p.ej. "SEC001"
    description: str # Texto legible del problema detectado
    severity: str   # "error", "warning", "suggestion"

    @abc.abstractmethod
    def run(self, tree: ast.AST, source: str, file_path: Path) -> list[Issue]:
        """Ejecuta la validación sobre el AST del archivo."""
        pass

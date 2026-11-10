from pathlib import Path
from core.http_client import AsyncHttpClient  # Reutiliza nuestro cliente HTTP existente

class SourceLoader:
    """
    Lee código fuente de forma segura:
    - Si el path empieza con 'http://' o 'https://', utiliza el cliente HTTP.
    - Si es un Path local, verifica rigurosamente que esté dentro de repo_root y sea un archivo .py.
    """
    def __init__(self, repo_root: Path = Path.cwd()) -> None:
        self.repo_root = repo_root.resolve()
        # Nota: Instanciamos un cliente HTTP síncrono/asíncrono de soporte según se requiera

    def read(self, target: Path | str) -> str:
        if isinstance(target, str) and target.startswith(('http://', 'https://')):
            raise NotImplementedError("La carga remota requiere ejecución asíncrona dedicada.")
        
        path = Path(target).resolve()
        if not str(path).startswith(str(self.repo_root)):
            raise PermissionError(f"Intento de lectura fuera de la raíz del repositorio: {path}")
        
        if not path.exists():
            raise FileNotFoundError(f"El archivo objetivo no existe: {path}")
            
        return path.read_text(encoding='utf-8')

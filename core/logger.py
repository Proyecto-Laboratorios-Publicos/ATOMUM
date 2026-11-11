"""
Módulo de logging seguro para ATOMUM.
Filtra y enmascara automáticamente los secretos antes de emitirlos en consola.
"""

import logging
import re
from logging.handlers import RotatingFileHandler
from typing import Final

# Patrón robusto para detectar claves, tokens y contraseñas dinámicas
SENSITIVE_PATTERN: Final[re.Pattern] = re.compile(
    r'(?i)(password|secret|api[_-]?key|token)\s*=\s*["\']?([^"\',\s]+)["\']?'
)

class SecretMaskFilter(logging.Filter):
    """Reemplaza cualquier coincidencia de datos sensibles por ***."""
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = SENSITIVE_PATTERN.sub(r'\1=***', record.msg)
        return True

def get_logger(name: str = "app") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
        
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(threadName)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Console handler
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    console.addFilter(SecretMaskFilter())
    logger.addHandler(console)
    
    return logger

# Instancia global por defecto
logger = get_logger("atomum")

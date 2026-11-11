"""
Módulo de logging seguro para ATOMUM.
Filtra y enmascara automáticamente los secretos antes de emitirlos en consola.
"""

import logging
import sys
from config.settings import settings

class SecretFilter(logging.Filter):
    """
    Elimina cualquier cadena que coincida con los valores secretos
    de la configuración antes de que el registro sea emitido.
    """
    def filter(self, record: logging.LogRecord) -> bool:
        # Extraer secretos de forma segura desde los campos SecretStr de Pydantic
        secret_values = []
        if hasattr(settings, 'GROQ_API_KEY') and settings.GROQ_API_KEY:
            secret_values.append(settings.GROQ_API_KEY.get_secret_value())
        
        message = record.getMessage()
        for secret in secret_values:
            if secret and secret in message:
                record.msg = message.replace(secret, '[REDACTED]')
        return True

def configure_logging() -> None:
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG if getattr(settings, 'DEBUG_MODE', False) else logging.INFO)
    
    # Evitar duplicidad de handlers si ya están configurados
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            fmt='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        handler.addFilter(SecretFilter())
        logger.addHandler(handler)

# Inicializar logger al importar el módulo
configure_logging()

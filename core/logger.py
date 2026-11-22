"""
Módulo de logging seguro para ATOMUM.
Filtra y enmascara automáticamente secretos, tokens y credenciales antes de emitir logs.
"""

import logging
import os
import re
from typing import Final

# Detecta asignaciones (= o :) y cabeceras Bearer con claves, tokens, API keys o contraseñas.
SENSITIVE_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?i)\b(password|passwd|secret|api[_-]?key|token|access[_-]?token|refresh[_-]?token)\b"
    r"""\s*(?:=|:)\s*["']?([^"',\s;}\]]+)["']?"""
)
BEARER_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?i)\b(bearer)\s+([A-Za-z0-9._\-~+/=]+)"
)


class SecretMaskFilter(logging.Filter):
    """Reemplaza valores sensibles en mensajes formateados por '***'."""

    def filter(self, record: logging.LogRecord) -> bool:
        rendered = record.getMessage()
        if isinstance(rendered, str):
            masked = SENSITIVE_PATTERN.sub(r"\1=***", rendered)
            masked = BEARER_PATTERN.sub(r"\1 ***", masked)
            if masked != rendered:
                # Reemplaza msg con el texto ya enmascarado y limpia args para evitar re-formateo.
                record.msg = masked.replace("%", "%%")
                record.args = ()
        return True


def get_logger(name: str = "app", level: int | str | None = None) -> logging.Logger:
    """Devuelve un logger configurado con filtro de enmascarado de secretos."""
    target_logger = logging.getLogger(name)
    if target_logger.handlers:
        return target_logger

    env_level = level if level is not None else os.getenv("ATOMUM_LOG_LEVEL", "INFO")
    target_logger.setLevel(env_level)
    target_logger.propagate = False

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(threadName)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    console.addFilter(SecretMaskFilter())
    target_logger.addHandler(console)

    return target_logger


# Instancia global por defecto
logger = get_logger("atomum")

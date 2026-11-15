# __init__.py
"""
Subpaquete de escaneo de puertos y auditoría de red de ATOMUM.
Expone el motor asíncrono y las utilidades de validación de seguridad.
"""

from .core import PortScanner, PortResult, OnOpenCallback, OnCloseCallback, OnErrorCallback
from .utils import validate_target, parse_port_range

__all__ = [
    "PortScanner",
    "PortResult",
    "OnOpenCallback",
    "OnCloseCallback",
    "OnErrorCallback",
    "validate_target",
    "parse_port_range",
]

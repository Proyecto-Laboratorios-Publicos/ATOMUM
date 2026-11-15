# utils.py
"""
Utilidades y validaciones de seguridad para el escáner de puertos.
- Incluye validación anti-SSRF para prohibir objetivos en redes locales,
  loopback (127.0.0.1) o rangos privados.
"""
import ipaddress
import socket
from typing import Tuple

def validate_target(target: str) -> Tuple[bool, str]:
    """
    Valida que el objetivo ingresado (IP o dominio) sea seguro y no viole
    las políticas anti-SSRF de la plataforma.
    Retorna: (is_valid: bool, resolved_ip_or_error: str)
    """
    if not target or not target.strip():
        return False, "El objetivo no puede estar vacío."

    target = target.strip()

    # 1. Resolver el hostname a dirección IP para validar el destino real
    try:
        resolved_ip = socket.gethostbyname(target)
    except socket.gaierror:
        return False, f"No se pudo resolver el hostname o IP: {target}"

    # 2. Evaluar si la IP pertenece a rangos privados, loopback, reservados o link-local
    try:
        ip_obj = ipaddress.ip_address(resolved_ip)
        
        if (
            ip_obj.is_private
            or ip_obj.is_loopback
            or ip_obj.is_reserved
            or ip_obj.is_link_local
            or ip_obj.is_unspecified
        ):
            return False, f"Objetivo bloqueado por seguridad (SSRF Shield): {target} resuelve a {resolved_ip} (rango privado/reservado)."
            
    except ValueError:
        return False, f"Dirección IP inválida resultante: {resolved_ip}"

    return True, resolved_ip

def parse_port_range(port_input: str) -> list[int]:
    """
    Parsea un string de puertos (ej: '80,443,8000-8010') a una lista plana de enteros únicos,
    asegurando que estén dentro del rango válido de puertos TCP (1-65535).
    """
    ports = set()
    parts = port_input.split(",")
    
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            subparts = part.split("-")
            if len(subparts) == 2:
                start, end = int(subparts[0]), int(subparts[1])
                for p in range(max(1, start), min(65535, end) + 1):
                    ports.add(p)
        else:
            p = int(part)
            if 1 <= p <= 65535:
                ports.add(p)
                
    return sorted(list(ports))

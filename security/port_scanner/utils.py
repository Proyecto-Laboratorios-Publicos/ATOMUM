# utils.py
"""
Utilidades y validaciones de seguridad para el escáner de puertos.
- Incluye validación anti-SSRF para prohibir objetivos en redes locales,
  loopback (127.0.0.1), multicast o rangos privados/reservados.
"""

import ipaddress
import socket
from typing import List, Tuple
from urllib.parse import urlparse


def _normalize_target_input(target: str) -> str:
    """Limpia espacios y extrae el hostname si el usuario pegó una URL o host:puerto."""
    cleaned = target.strip()
    if "://" in cleaned:
        parsed = urlparse(cleaned)
        if parsed.hostname:
            return parsed.hostname.strip()
    # Evita confundir IPv6 entre corchetes con host:puerto
    if cleaned.startswith("[") and "]" in cleaned:
        return cleaned[1 : cleaned.index("]")].strip()
    if cleaned.count(":") == 1 and not cleaned.endswith(":"):
        host_part, port_part = cleaned.rsplit(":", 1)
        if port_part.isdigit():
            return host_part.strip()
    return cleaned


def _is_forbidden_ip(ip_obj: ipaddress._BaseAddress) -> bool:
    """Indica si una dirección IP pertenece a un rango bloqueado por política anti-SSRF."""
    return bool(
        ip_obj.is_private
        or ip_obj.is_loopback
        or ip_obj.is_reserved
        or ip_obj.is_link_local
        or ip_obj.is_unspecified
        or ip_obj.is_multicast
    )


def validate_target(target: str) -> Tuple[bool, str]:
    """
    Valida que el objetivo ingresado (IP o dominio) sea seguro y no viole
    las políticas anti-SSRF de la plataforma.

    Retorna:
        (is_valid: bool, resolved_ip_or_error: str)
    """
    if not target or not target.strip():
        return False, "El objetivo no puede estar vacío."

    normalized = _normalize_target_input(target)
    if not normalized:
        return False, "El objetivo ingresado no contiene un host válido."

    # Si ingresan notación CIDR (ej. 192.168.1.0/24), rechazar explícitamente
    if "/" in normalized:
        try:
            network = ipaddress.ip_network(normalized, strict=False)
            if _is_forbidden_ip(network.network_address) or _is_forbidden_ip(network.broadcast_address):
                return (
                    False,
                    f"Objetivo bloqueado por seguridad (SSRF Shield): el rango {normalized} "
                    "incluye direcciones privadas, loopback o reservadas.",
                )
            return False, f"El escaneo directo sobre rangos CIDR ({normalized}) no está habilitado aquí."
        except ValueError:
            return False, f"Notación de red o destino inválido: {normalized}"

    # 1. Resolver el hostname a direcciones IP para validar todos los destinos resultantes
    resolved_ips: List[str] = []
    try:
        addr_info = socket.getaddrinfo(normalized, None, type=socket.SOCK_STREAM)
        for item in addr_info:
            ip_str = item[4][0]
            if ip_str not in resolved_ips:
                resolved_ips.append(ip_str)
    except socket.gaierror:
        return False, f"No se pudo resolver el hostname o IP: {normalized}"

    if not resolved_ips:
        return False, f"No se obtuvieron direcciones IP válidas para: {normalized}"

    # 2. Evaluar si alguna IP pertenece a rangos bloqueados
    for ip_str in resolved_ips:
        try:
            ip_obj = ipaddress.ip_address(ip_str)
            if _is_forbidden_ip(ip_obj):
                return (
                    False,
                    f"Objetivo bloqueado por seguridad (SSRF Shield): {normalized} resuelve a "
                    f"{ip_str} (rango privado/reservado/no permitido).",
                )
        except ValueError:
            return False, f"Dirección IP inválida resultante: {ip_str}"

    return True, resolved_ips[0]


def parse_port_range(port_input: str) -> list[int]:
    """
    Parsea un string de puertos (ej: '80,443,8000-8010') a una lista plana de
    enteros únicos, asegurando que estén dentro del rango válido de puertos TCP (1-65535).
    """
    if not port_input or not port_input.strip():
        return []

    ports: set[int] = set()
    for part in port_input.split(","):
        token = part.strip()
        if not token:
            continue

        if "-" in token:
            subparts = [p.strip() for p in token.split("-")]
            if len(subparts) == 2:
                try:
                    start = int(subparts[0])
                    end = int(subparts[1])
                except ValueError:
                    continue
                low, high = min(start, end), max(start, end)
                clamped_start = max(1, low)
                clamped_end = min(65535, high)
                if clamped_start <= clamped_end:
                    ports.update(range(clamped_start, clamped_end + 1))
        else:
            try:
                port_num = int(token)
            except ValueError:
                continue
            if 1 <= port_num <= 65535:
                ports.add(port_num)

    return sorted(ports)

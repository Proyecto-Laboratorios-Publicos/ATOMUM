# security/port_scanner.py

from __future__ import annotations

import socket
import urllib.error
import urllib.request
from typing import Dict, List


# List of security headers we want to check for
_SECURITY_HEADERS: List[str] = [
    "Content-Security-Policy",
    "X-Content-Type-Options",
    "X-Frame-Options",
    "Strict-Transport-Security",
    "Referrer-Policy",
    "X-XSS-Protection",
]


def check_security_headers(url: str) -> Dict[str, bool]:
    """
    Fetches the given URL and returns a mapping of each security header
    in _SECURITY_HEADERS to a boolean indicating its presence.
    """
    result: Dict[str, bool] = {header: False for header in _SECURITY_HEADERS}
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            # urllib returns header keys case‑insensitively; we normalise to title case
            headers = {k.title(): v for k, v in response.getheaders()}
            for header in _SECURITY_HEADERS:
                result[header] = header in headers
    except (urllib.error.URLError, ValueError):
        # On any network error or malformed URL we simply return all False
        pass
    return result


def scan_tcp_port(host: str, port: int, timeout: float = 1.0) -> bool:
    """
    Attempts to establish a TCP connection to ``host`` on ``port``.
    Returns ``True`` if the connection succeeds (port is open), otherwise ``False``.
    The socket is always closed via a ``finally`` block to guarantee resource cleanup.
    """
    sock: socket.socket | None = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        return True
    except socket.error:
        # Connection failed – port is closed or host unreachable
        return False
    finally:
        if sock is not None:
            try:
                sock.close()
            except socket.error:
                # Ignoring errors on close; nothing we can do
                pass

# security/port_scanner.py

from __future__ import annotations

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

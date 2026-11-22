"""
test_streamlit_app.py
---------------------
Prueba de integración para verificar que la interfaz de Streamlit arranca
y responde correctamente.
"""

from __future__ import annotations

import socket
import subprocess
import sys
import time
from typing import Iterator

import pytest
import requests


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_server(url: str, proc: subprocess.Popen[bytes], timeout_s: float = 15.0) -> None:
    deadline = time.monotonic() + timeout_s
    last_err: Exception | None = None

    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(
                f"Streamlit terminó antes de estar listo (código {proc.returncode})."
            )
        try:
            resp = requests.get(url, timeout=1.0)
            if resp.status_code == 200:
                return
        except requests.RequestException as exc:
            last_err = exc
        time.sleep(0.25)

    raise TimeoutError(f"Streamlit no respondió en {url} tras {timeout_s}s: {last_err}")


@pytest.fixture(scope="session")
def streamlit_server() -> Iterator[str]:
    port = _find_free_port()
    base_url = f"http://127.0.0.1:{port}"
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "streamlit_monitor.py",
        "--server.port",
        str(port),
        "--server.address",
        "127.0.0.1",
        "--server.headless",
        "true",
    ]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_for_server(base_url, proc)
        yield base_url
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5.0)


def test_streamlit_startup(streamlit_server: str) -> None:
    response = requests.get(streamlit_server, timeout=5.0)
    assert response.status_code == 200
    assert len(response.text) > 0

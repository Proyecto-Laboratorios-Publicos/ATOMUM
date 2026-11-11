"""
test_streamlit_app.py
---------------------
Prueba de integración para verificar que la interfaz de Streamlit arranca correctamente.
"""

import subprocess
import time
import requests
import pytest

@pytest.fixture(scope="session")
def streamlit_server():
    # Levanta el monitor en un puerto de prueba
    proc = subprocess.Popen(
        ["streamlit", "run", "streamlit_monitor.py", "--server.port", "8502", "--server.headless", "true"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    time.sleep(4) # Esperar arranque del servidor local
    yield "http://localhost:8502"
    proc.terminate()
    proc.wait()

def test_streamlit_startup(streamlit_server):
    response = requests.get(streamlit_server)
    # Verificamos que la app responda satisfactoriamente
    assert response.status_code == 200

import urllib.request
import json

class WebTools:
    def __init__(self):
        print("🌐 [Skills: Web] Herramientas de red y consultas inicializadas.")

    def fetch_url_text(self, url: str):
        """Realiza una consulta GET simple para obtener contenido de texto de una URL."""
        print(f"🌐 [Skills: Web] Consultando endpoint: '{url}'")
        try:
            req = urllib.request.Request(
                url, 
                headers={'User-Agent': 'Mozilla/5.0 (AtomumAgent)'}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                content = response.read().decode('utf-8')
                print(f"✅ [Skills: Web] Datos obtenidos con éxito ({len(content)} bytes).")
                return content
        except Exception as e:
            error_msg = f"❌ [Skills: Web Error] Fallo en la consulta HTTP: {e}"
            print(error_msg)
            return error_msg

if __name__ == "__main__":
    # Prueba rápida del módulo web
    web = WebTools()
    web.fetch_url_text("https://api.github.com")

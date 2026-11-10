import urllib.request
import urllib.error
import json

class WebTools:
    def __init__(self):
        print("🌐 [Skills: Web] Herramientas avanzadas de red y consultas HTTP inicializadas.")

    def fetch_url_text(self, url: str, headers: dict = None) -> str:
        """Realiza una consulta GET para obtener el contenido de texto de una URL con cabeceras personalizables."""
        print(f"🌐 [Skills: Web] Consultando endpoint GET: '{url}'")
        
        default_headers = {'User-Agent': 'Mozilla/5.0 (AtomumAgent/1.0)'}
        if headers:
            default_headers.update(headers)

        try:
            req = urllib.request.Request(url, headers=default_headers)
            with urllib.request.urlopen(req, timeout=15) as response:
                content = response.read().decode('utf-8')
                print(f"✅ [Skills: Web] Datos obtenidos con éxito ({len(content)} bytes).")
                return content
        except urllib.error.HTTPError as e:
            error_msg = f"❌ [Skills: Web Error] Error HTTP {e.code}: {e.reason}"
            print(error_msg)
            return error_msg
        except urllib.error.URLError as e:
            error_msg = f"❌ [Skills: Web Error] Error de conexión URL: {e.reason}"
            print(error_msg)
            return error_msg
        except Exception as e:
            error_msg = f"❌ [Skills: Web Error] Fallo inesperado en la consulta: {e}"
            print(error_msg)
            return error_msg

    def fetch_url_json(self, url: str, headers: dict = None):
        """Realiza una consulta GET y deserializa automáticamente la respuesta a un objeto JSON (Diccionario/Lista)."""
        raw_text = self.fetch_url_text(url, headers=headers)
        try:
            data = json.loads(raw_text)
            print("✅ [Skills: Web] Respuesta JSON parseada correctamente.")
            return data
        except json.JSONDecodeError as e:
            print(f"❌ [Skills: Web Error] La respuesta no tiene un formato JSON válido: {e}")
            return None

if __name__ == "__main__":
    # Prueba rápida del módulo web mejorado
    web = WebTools()
    web.fetch_url_json("https://api.github.com")

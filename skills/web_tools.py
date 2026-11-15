import urllib.request
import urllib.error
import json
from typing import Any, Dict, List, Optional, Union


class WebTools:
    def __init__(self) -> None:
        print("🌐 [Skills: Web] Herramientas avanzadas de red y consultas HTTP inicializadas.")

    def fetch_url_text(self, url: str, headers: Optional[Dict[str, str]] = None) -> str:
        """Realiza una consulta GET para obtener el contenido de texto de una URL con cabeceras personalizables."""
        print(f"🌐 [Skills: Web] Consultando endpoint GET: '{url}'")
        default_headers = {"User-Agent": "Mozilla/5.0 (AtomumAgent/2.0)"}
        if headers:
            default_headers.update(headers)
        try:
            req = urllib.request.Request(url, headers=default_headers)
            with urllib.request.urlopen(req, timeout=15) as response:
                content = response.read().decode("utf-8")
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

    def fetch_url_json(
        self, url: str, headers: Optional[Dict[str, str]] = None
    ) -> Union[Dict[str, Any], List[Any], None]:
        """Realiza una consulta GET y deserializa automáticamente la respuesta a un objeto JSON."""
        raw_text = self.fetch_url_text(url, headers=headers)
        try:
            data = json.loads(raw_text)
            print("✅ [Skills: Web] Respuesta JSON parseada correctamente.")
            return data
        except json.JSONDecodeError as e:
            print(f"❌ [Skills: Web Error] La respuesta no tiene un formato JSON válido: {e}")
            return None

    def post_url_json(
        self,
        url: str,
        payload: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Envía una petición POST con cuerpo JSON y devuelve la respuesta parseada."""
        print(f"🚀 [Skills: Web] Enviando petición POST JSON a: '{url}'")
        default_headers = {
            "User-Agent": "AtomumAgent/2.0",
            "Content-Type": "application/json",
            "Accept": "application/vnd.github+json",
        }
        if headers:
            default_headers

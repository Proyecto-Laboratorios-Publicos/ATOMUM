import json
import os
from typing import Any, Dict, List, Optional


class DataTools:
    """
    Conjunto de utilidades para la carga y procesamiento básico de datos.

    Esta clase está diseñada para ser usada tanto en entornos de desarrollo como
    en producción, manteniendo la compatibilidad total con versiones anteriores
    del proyecto.
    """

    def __init__(self) -> None:
        """
        Inicializa la herramienta de datos.

        Sólo muestra un mensaje informativo; no se lanza ninguna excepción.
        """
        print("📊 [Skills: Data] Herramientas de procesamiento de datos inicializadas.")

    def read_json_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Lee y carga datos estructurados de un archivo JSON de forma segura.

        Parameters
        ----------
        file_path: str
            Ruta absoluta o relativa al archivo JSON que se desea leer.

        Returns
        -------
        Optional[Dict[str, Any]]
            Diccionario con el contenido del JSON si la operación tiene éxito;
            ``None`` si el archivo no existe o ocurre algún error al leerlo.

        Raises
        ------
        None
            Todas las excepciones se capturan y se convierten en mensajes de
            registro, devolviendo ``None`` para preservar la compatibilidad.
        """
        if not os.path.exists(file_path):
            print(f"❌ [Skills: Data Error] El archivo '{file_path}' no existe.")
            return None

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data: Dict[str, Any] = json.load(f)
                print(f"✅ [Skills: Data] Archivo JSON leído con éxito: '{file_path}'")
                return data
        except (json.JSONDecodeError, OSError) as e:
            # Captura errores de parsing y de I/O de forma explícita.
            print(f"❌ [Skills: Data Error] No se pudo leer o parsear el JSON: {e}")
            return None
        except Exception as e:  # pragma: no cover
            # Captura cualquier otro error inesperado sin romper la API.
            print(f"❌ [Skills: Data Error] Error inesperado al leer el JSON: {e}")
            return None

    def summarize_metrics(self, data_list: List[Any]) -> Dict[str, Any]:
        """
        Genera un resumen básico de una lista de eventos o métricas.

        Parameters
        ----------
        data_list: List[Any]
            Lista que contiene los registros a resumir.

        Returns
        -------
        Dict[str, Any]
            Diccionario con el número total de registros y una muestra de los
            primeros tres elementos (si existen).
        """
        total_items: int = len(data_list)
        summary: Dict[str, Any] = {
            "total_records": total_items,
            "sample_records": data_list[:3] if total_items > 0 else [],
        }
        print(f"📈 [Skills: Data] Resumen generado para {total_items} registros.")
        return summary


if __name__ == "__main__":
    # Prueba rápida de las herramientas de datos
    tools = DataTools()
    tools.read_json_file("memory/atomum_memory.json")

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


class DataTools:
    """
    Conjunto de utilidades para la carga y resumen de datos estructurados.

    Las funciones imprimen mensajes de estado para facilitar la depuración
    y son compatibles con versiones de Python 3.8+.
    """

    def __init__(self) -> None:
        """Inicializa la clase mostrando un mensaje informativo."""
        print("📊 [Skills: Data] Herramientas de procesamiento de datos inicializadas.")

    def read_json_file(self, file_path: Union[str, Path]) -> Optional[Dict[str, Any]]:
        """
        Lee y carga datos estructurados de un archivo JSON.

        Parameters
        ----------
        file_path: Union[str, Path]
            Ruta al archivo JSON que se desea leer.

        Returns
        -------
        Optional[Dict[str, Any]]
            Diccionario con el contenido del JSON si la operación tiene éxito;
            ``None`` en caso de error o si el archivo no existe.

        Notes
        -----
        - Se captura ``FileNotFoundError`` y ``json.JSONDecodeError`` de forma
          explícita para evitar capturar excepciones inesperadas.
        - Los mensajes de error se imprimen en consola para mantener el
          comportamiento original del módulo.
        """
        path = Path(file_path)

        if not path.is_file():
            print(f"❌ [Skills: Data Error] El archivo '{path}' no existe.")
            return None

        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
                print(f"✅ [Skills: Data] Archivo JSON leído con éxito: '{path}'")
                return data
        except json.JSONDecodeError as jde:
            print(f"❌ [Skills: Data Error] No se pudo parsear el JSON: {jde}")
        except OSError as ose:
            print(f"❌ [Skills: Data Error] Error al abrir el archivo: {ose}")

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
        total_items = len(data_list)
        summary: Dict[str, Any] = {
            "total_records": total_items,
            "sample_records": data_list[:3] if total_items > 0 else []
        }
        print(f"📈 [Skills: Data] Resumen generado para {total_items} registros.")
        return summary


if __name__ == "__main__":
    # Prueba rápida de las herramientas de datos
    tools = DataTools()
    tools.read_json_file("memory/atomum_memory.json")

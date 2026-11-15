import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


class DataTools:
    """
    Herramientas de procesamiento de datos.

    Esta clase encapsula operaciones comunes sobre archivos JSON y
    generación de resúmenes simples. Mantiene la compatibilidad total
    con la versión anterior, añadiendo tipado estático y manejo
    explícito de excepciones.
    """

    def __init__(self) -> None:
        """
        Inicializa la clase mostrando un mensaje informativo.
        """
        print("📊 [Skills: Data] Herramientas de procesamiento de datos inicializadas.")

    def read_json_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Lee y carga datos estructurados de un archivo JSON de forma segura.

        Args:
            file_path: Ruta al archivo JSON a leer.

        Returns:
            Un diccionario con el contenido del JSON si la operación tiene éxito,
            o ``None`` en caso de error (archivo inexistente, problemas de I/O o
            JSON mal formado).
        """
        path = Path(file_path)

        if not path.is_file():
            print(f"❌ [Skills: Data Error] El archivo '{file_path}' no existe.")
            return None

        try:
            with path.open("r", encoding="utf-8") as f:
                data: Dict[str, Any] = json.load(f)
                print(f"✅ [Skills: Data] Archivo JSON leído con éxito: '{file_path}'")
                return data
        except json.JSONDecodeError as jde:
            print(f"❌ [Skills: Data Error] No se pudo parsear el JSON: {jde}")
        except OSError as ose:
            print(f"❌ [Skills: Data Error] Error al abrir/leer el archivo: {ose}")
        except Exception as e:  # Captura cualquier otra excepción inesperada
            print(f"❌ [Skills: Data Error] Error inesperado: {e}")

        return None

    def summarize_metrics(self, data_list: List[Any]) -> Dict[str, Any]:
        """
        Genera un resumen básico de una lista de eventos o métricas.

        Args:
            data_list: Lista de elementos (pueden ser diccionarios, números, etc.).

        Returns:
            Un diccionario con el número total de registros y una muestra de los
            primeros tres elementos (o una lista vacía si no hay datos).
        """
        total_items: int = len(data_list)
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

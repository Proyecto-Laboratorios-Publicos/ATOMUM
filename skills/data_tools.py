import json
import os
from typing import Any, Dict, List, Optional, Sequence


class DataTools:
    """
    Conjunto de utilidades para la carga y procesamiento básico de datos.

    Esta clase está diseñada para ser utilizada tanto en scripts como en
    entornos de producción, manteniendo la compatibilidad con versiones
    de Python ≥3.8.
    """

    def __init__(self) -> None:
        """Inicializa la herramienta mostrando un mensaje informativo."""
        print("📊 [Skills: Data] Herramientas de procesamiento de datos inicializadas.")

    def read_json_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Lee y carga datos estructurados de un archivo JSON.

        Args:
            file_path: Ruta absoluta o relativa al archivo JSON.

        Returns:
            Un diccionario con el contenido del JSON si la operación tiene éxito;
            ``None`` en caso de error (archivo inexistente o JSON inválido).

        Notas:
            - Se captura explícitamente ``FileNotFoundError`` y ``json.JSONDecodeError``.
            - Los mensajes de error se imprimen para mantener el comportamiento
              original del módulo.
        """
        if not os.path.exists(file_path):
            print(f"❌ [Skills: Data Error] El archivo '{file_path}' no existe.")
            return None

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data: Dict[str, Any] = json.load(f)
                print(f"✅ [Skills: Data] Archivo JSON leído con éxito: '{file_path}'")
                return data
        except FileNotFoundError as fnf_err:
            # Esta rama es redundante con la comprobación anterior, pero se mantiene
            # por completitud en caso de condiciones de carrera.
            print(f"❌ [Skills: Data Error] Archivo no encontrado: {fnf_err}")
        except json.JSONDecodeError as json_err:
            print(f"❌ [Skills: Data Error] No se pudo parsear el JSON: {json_err}")
        except Exception as e:  # pragma: no cover
            # Captura cualquier otro error inesperado, preservando la API anterior.
            print(f"❌ [Skills: Data Error] Error inesperado al leer JSON: {e}")

        return None

    def summarize_metrics(self, data_list: Sequence[Any]) -> Dict[str, Any]:
        """
        Genera un resumen básico de una lista de eventos o métricas.

        Args:
            data_list: Secuencia (lista, tupla, etc.) que contiene los registros a resumir.

        Returns:
            Diccionario con:
                - ``total_records``: número total de elementos.
                - ``sample_records``: hasta los tres primeros registros (si existen).
        """
        total_items: int = len(data_list)
        sample: List[Any] = list(data_list[:3]) if total_items > 0 else []

        summary: Dict[str, Any] = {
            "total_records": total_items,
            "sample_records": sample,
        }

        print(f"📈 [Skills: Data] Resumen generado para {total_items} registros.")
        return summary


if __name__ == "__main__":
    # Prueba rápida de las herramientas de datos
    tools = DataTools()
    tools.read_json_file("memory/atomum_memory.json")

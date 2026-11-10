import json
import os

class DataTools:
    def __init__(self):
        print("📊 [Skills: Data] Herramientas de procesamiento de datos inicializadas.")

    def read_json_file(self, file_path: str):
        """Lee y carga datos estructurados de un archivo JSON de forma segura."""
        if not os.path.exists(file_path):
            print(f"❌ [Skills: Data Error] El archivo '{file_path}' no existe.")
            return None
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                print(f"✅ [Skills: Data] Archivo JSON leído con éxito: '{file_path}'")
                return data
        except Exception as e:
            print(f"❌ [Skills: Data Error] No se pudo parsear el JSON: {e}")
            return None

    def summarize_metrics(self, data_list: list):
        """Genera un resumen básico de una lista de eventos o métricas."""
        total_items = len(data_list)
        summary = {
            "total_records": total_items,
            "sample_records": data_list[:3] if total_items > 0 else []
        }
        print(f"📈 [Skills: Data] Resumen generado para {total_items} registros.")
        return summary

if __name__ == "__main__":
    # Prueba rápida de las herramientas de datos
    tools = DataTools()
    tools.read_json_file("memory/atomum_memory.json")

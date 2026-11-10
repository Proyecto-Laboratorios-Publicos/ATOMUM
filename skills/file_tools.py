import os
import json

class FileTools:
    def __init__(self, base_dir="."):
        self.base_dir = os.path.abspath(base_dir)
        print("📝 [Skills: Files] Herramientas avanzadas de manipulación de archivos inicializadas.")

    def _get_safe_path(self, file_path: str) -> str:
        """Garantiza que la ruta del archivo se mantenga dentro del workspace seguro."""
        abs_path = os.path.abspath(os.path.join(self.base_dir, file_path))
        return abs_path

    def read_text_file(self, file_path: str) -> str:
        """Lee un archivo de texto de forma segura."""
        safe_path = self._get_safe_path(file_path)
        if not os.path.exists(safe_path):
            print(f"❌ [Skills: File Error] El archivo '{file_path}' no existe.")
            return None
        try:
            with open(safe_path, "r", encoding="utf-8") as f:
                content = f.read()
            print(f"✅ [Skills: File] Archivo de texto leído: '{file_path}'")
            return content
        except Exception as e:
            print(f"❌ [Skills: File Error] No se pudo leer el archivo: {e}")
            return None

    def write_text_file(self, file_path: str, content: str) -> bool:
        """Escribe o sobrescribe un archivo de texto de forma controlada."""
        safe_path = self._get_safe_path(file_path)
        try:
            dir_name = os.path.dirname(safe_path)
            if dir_name and not os.path.exists(dir_name):
                os.makedirs(dir_name, exist_ok=True)
                
            with open(safe_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"✅ [Skills: File] Archivo escrito con éxito: '{file_path}'")
            return True
        except Exception as e:
            print(f"❌ [Skills: File Error] No se pudo escribir el archivo: {e}")
            return False

    def read_json_file(self, file_path: str):
        """Lee y deserializa un archivo JSON de forma segura."""
        content = self.read_text_file(file_path)
        if content is None:
            return None
        try:
            data = json.loads(content)
            print(f"✅ [Skills: File] JSON parseado correctamente desde '{file_path}'")
            return data
        except json.JSONDecodeError as e:
            print(f"❌ [Skills: JSON Error] El archivo '{file_path}' tiene un formato JSON inválido: {e}")
            return None

    def write_json_file(self, file_path: str, data) -> bool:
        """Serializa y escribe un objeto de Python en formato JSON estructurado."""
        try:
            json_str = json.dumps(data, indent=4, ensure_ascii=False)
            return self.write_text_file(file_path, json_str)
        except Exception as e:
            print(f"❌ [Skills: JSON Error] No se pudo serializar los datos a JSON: {e}")
            return False

if __name__ == "__main__":
    # Prueba rápida de las herramientas de archivos mejoradas
    ft = FileTools()
    ft.write_text_file("test_output.txt", "Prueba de escritura autónoma mejorada de Atomum.")
    ft.read_text_file("test_output.txt")

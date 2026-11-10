import os

class FileTools:
    def __init__(self):
        print("📝 [Skills: Files] Herramientas de manipulación de archivos inicializadas.")

    def read_text_file(self, file_path: str):
        """Lee un archivo de texto de forma segura."""
        if not os.path.exists(file_path):
            print(f"❌ [Skills: File Error] El archivo '{file_path}' no existe.")
            return None
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                print(f"✅ [Skills: File] Archivo de texto leído: '{file_path}'")
                return content
        except Exception as e:
            print(f"❌ [Skills: File Error] No se pudo leer el archivo: {e}")
            return None

    def write_text_file(self, file_path: str, content: str):
        """Escribe o sobrescribe un archivo de texto de forma controlada."""
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
                print(f"✅ [Skills: File] Archivo escrito con éxito: '{file_path}'")
                return True
        except Exception as e:
            print(f"❌ [Skills: File Error] No se pudo escribir el archivo: {e}")
            return False

if __name__ == "__main__":
    # Prueba rápida de la herramienta de archivos
    ft = FileTools()
    ft.write_text_file("test_output.txt", "Prueba de escritura autónoma de Atomum.")
    ft.read_text_file("test_output.txt")

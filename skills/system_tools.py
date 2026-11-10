import os
import subprocess

class SystemTools:
    def __init__(self):
        print("⚡ [Skills: System] Herramientas de sistema inicializadas.")

    def list_directory(self, path="."):
        """Lista los archivos y carpetas en un directorio dado."""
        try:
            items = os.listdir(path)
            print(f"📂 [Skills: System] Listando directorio '{path}': {items}")
            return items
        except Exception as e:
            print(f"❌ [Skills: System Error] No se pudo listar el directorio: {e}")
            return []

    def execute_safe_command(self, command: str):
        """Ejecuta un comando de forma controlada en la terminal del sistema."""
        print(f"⚙️ [Skills: System] Ejecutando comando seguro: '{command}'")
        try:
            result = subprocess.run(
                command, 
                shell=True, 
                capture_output=True, 
                text=True, 
                timeout=10
            )
            output = result.stdout if result.returncode == 0 else result.stderr
            print(f"✅ [Skills: System] Salida del comando:\n{output}")
            return output
        except Exception as e:
            error_msg = f"❌ [Skills: System Error] Fallo en la ejecución: {e}"
            print(error_msg)
            return error_msg

if __name__ == "__main__":
    # Prueba rápida de las herramientas del sistema
    tools = SystemTools()
    tools.list_directory(".")
    tools.execute_safe_command("python --version")

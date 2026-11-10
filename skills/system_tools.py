import os
import sys
import subprocess
import platform

class SystemTools:
    def __init__(self):
        print("⚡ [Skills: System] Herramientas de sistema avanzadas inicializadas.")

    def list_directory(self, path="."):
        """Lista los archivos y carpetas en un directorio dado de forma segura."""
        try:
            items = os.listdir(path)
            print(f"📂 [Skills: System] Listando directorio '{path}': {len(items)} elementos encontrados.")
            return items
        except Exception as e:
            error_msg = f"❌ [Skills: System Error] No se pudo listar el directorio: {e}"
            print(error_msg)
            return []

    def get_system_info(self) -> dict:
        """Obtiene un diagnóstico rápido del entorno de ejecución de ATOMUM."""
        try:
            info = {
                "platform": platform.system(),
                "release": platform.release(),
                "python_version": platform.python_version(),
                "architecture": platform.machine(),
                "current_working_dir": os.getcwd()
            }
            print(f"📊 [Skills: System] Diagnóstico de entorno obtenido: {info}")
            return info
        except Exception as e:
            print(f"❌ [Skills: System Error] No se pudo obtener la info del sistema: {e}")
            return {}

    def execute_safe_command(self, command: str, timeout_sec: int = 15) -> str:
        """Ejecuta un comando de forma controlada en la terminal del sistema con manejo robusto de errores."""
        print(f"⚙️ [Skills: System] Ejecutando comando seguro: '{command}'")
        try:
            result = subprocess.run(
                command, 
                shell=True, 
                capture_output=True, 
                text=True, 
                encoding='utf-8', 
                errors='replace',
                timeout=timeout_sec
            )
            output = result.stdout if result.returncode == 0 else result.stderr
            print(f"✅ [Skills: System] Comando ejecutado con código {result.returncode}.")
            return output.strip()
        except subprocess.TimeoutExpired:
            error_msg = f"⏱️ [Skills: System Error] El comando excedió el tiempo límite de {timeout_sec} segundos."
            print(error_msg)
            return error_msg
        except Exception as e:
            error_msg = f"❌ [Skills: System Error] Fallo crítico en la ejecución: {e}"
            print(error_msg)
            return error_msg

if __name__ == "__main__":
    # Prueba rápida de las herramientas del sistema mejoradas
    tools = SystemTools()
    tools.list_directory(".")
    tools.get_system_info()

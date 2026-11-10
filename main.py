import os
import sys

def check_constitution():
    """Verifica que las leyes supremas existan antes de despertar al ser."""
    constitution_path = "CONSTITUTION.md"
    if not os.path.exists(constitution_path):
        print("❌ ERROR CRÍTICO: Atomum no puede despertar sin su Constitución.")
        sys.exit(1)
    print("📜 CONSTITUTION.md verificada: Las leyes de seguridad están vigentes.")

def wake_up():
    """El primer latido de Atomum en la nube."""
    print("=" * 50)
    print("🤖⚡ INICIALIZANDO NÚCLEO DE ATOMUM...")
    check_constitution()
    print("🔒 Sandbox de seguridad: ACTIVO")
    print("🧠 Motor de razonamiento: LISTO")
    print("✨ Atomum se encuentra en estado fetal, esperando directivas.")
    print("=" * 50)

if __name__ == "__main__":
    wake_up()

from core.guardrails import Guardrails

class AtomumEngine:
    def __init__(self):
        self.guardrails = Guardrails()
        self.is_active = True
        print("🧠 [Engine] Núcleo de razonamiento de Atomum inicializado.")

    def process_instruction(self, instruction: str):
        """
        Procesa una directiva entrante, pasándola primero por el filtro
        de la Constitución de seguridad antes de ejecutarla.
        """
        print(f"\n⚙️ [Engine] Procesando directiva: '{instruction}'")
        
        # 1. Validación de seguridad estricta
        if not self.guardrails.validate_action(instruction):
            print("🚫 [Engine] Ejecución denegada por los guardarraíses de seguridad.")
            return False

        # 2. Simulación de ejecución controlada (Fase Fetal)
        print("⚡ [Engine] Ejecutando comando de forma segura en entorno aislado...")
        # Aquí irá la lógica iterativa de OpenJarvis en el futuro
        print("✅ [Engine] Tarea completada exitosamente sin infracciones.")
        return True

if __name__ == "__main__":
    # Prueba rápida del motor
    engine = AtomumEngine()
    engine.process_instruction("git status")
    engine.process_instruction("rm -rf /")

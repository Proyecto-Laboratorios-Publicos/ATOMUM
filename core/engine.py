import os
import sys

# Asegurar rutas absolutas exactas antes de cualquier importación interna
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from core.guardrails import Guardrails
from groq import Groq

class AtomumEngine:
    def __init__(self):
        self.guardrails = Guardrails()
        self.is_active = True
        self.api_key = os.getenv("ATOMUM_LLM_API_KEY") or os.getenv("GROQ_API_KEY")
        self.model_name = os.getenv("ATOMUM_LLM_MODEL", "openai/gpt-oss-120b")
        
        # Inicializar el cliente oficial de Groq si la API Key está disponible
        if self.api_key:
            try:
                self.client = Groq(api_key=self.api_key)
                print("🧠 [Engine] Cliente oficial de Groq inicializado con éxito.")
            except Exception as e:
                self.client = None
                print(f"❌ [Engine Error] No se pudo inicializar el cliente de Groq: {e}")
        else:
            self.client = None
            print("⚠️ [Engine] Advertencia: No se encontró API Key de Groq configurada.")

    def process_instruction(self, instruction: str) -> str:
        if not instruction or not isinstance(instruction, str):
            return "⚠️ [Engine] Directiva vacía o inválida recibida."
            
        cleaned_instruction = instruction.strip()
        print(f"\n⚙️ [Engine] Procesando directiva: '{cleaned_instruction}'")
        
        # 1. Validación estricta con los guardarraíses
        if not self.guardrails.validate_action(cleaned_instruction):
            return "🚫 [Engine] Ejecución denegada por los guardarraíses de seguridad suprema."
            
        # 2. Control de patrones destructivos
        dangerous_patterns = ["rm -rf", "sudo", "shutdown", "mkfs", "dd if="]
        if any(pattern in cleaned_instruction.lower() for pattern in dangerous_patterns):
            return "🛡️ [Engine] Alerta de seguridad: Patrón destructivo bloqueado por el motor."
            
        # 3. Conexión con la API Cognitiva mediante el SDK oficial
        if self.client:
            try:
                completion = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {
                            "role": "system", 
                            "content": "Actúas como el núcleo cognitivo autónomo de ATOMUM. Responde de forma directa, técnica y analítica estructurando código y soluciones robustas."
                        },
                        {
                            "role": "user", 
                            "content": cleaned_instruction
                        }
                    ],
                    temperature=0.2,
                    max_tokens=8192
                )
                ai_response = completion.choices[0].message.content
                return ai_response
            except Exception as e:
                return f"❌ [Engine] Fallo en la llamada al SDK de Groq: {e}"
        else:
            return "🧠 [Engine] Modo Autónomo Local: Falta configurar la API Key de Groq en los secretos de Streamlit."

if __name__ == "__main__":
    engine = AtomumEngine()
    print(engine.process_instruction("estado del sistema"))

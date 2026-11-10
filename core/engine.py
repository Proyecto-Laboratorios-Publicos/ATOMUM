import os
import sys
import requests

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
if root_dir not in sys.path:
    sys.path.append(root_dir)

from core.guardrails import Guardrails

class AtomumEngine:
    def __init__(self):
        self.guardrails = Guardrails()
        self.is_active = True
        
        self.api_key = os.getenv("ATOMUM_LLM_API_KEY") or os.getenv("GROQ_API_KEY")
        self.api_endpoint = os.getenv("ATOMUM_LLM_ENDPOINT", "https://api.groq.com/openai/v1/chat/completions")
        # Usamos un modelo rápido, estable y 100% compatible con la API de Groq
        self.model_name = "llama-3.1-8b-instant"
        
        print("🧠 [Engine] Núcleo de razonamiento de Atomum inicializado para Groq.")

    def process_instruction(self, instruction: str):
        if not instruction or not isinstance(instruction, str):
            return "⚠️ [Engine] Directiva vacía o inválida recibida."

        cleaned_instruction = instruction.strip()
        print(f"\n⚙️ [Engine] Procesando directiva: '{cleaned_instruction}'")

        if not self.guardrails.validate_action(cleaned_instruction):
            return "🚫 [Engine] Ejecución denegada por los guardarraíses de seguridad suprema."

        dangerous_patterns = ["rm -rf", "sudo", "shutdown", "mkfs", "dd if="]
        if any(pattern in cleaned_instruction.lower() for pattern in dangerous_patterns):
            return "🛡️ [Engine] Alerta de seguridad: Patrón destructivo bloqueado por el motor."

        if self.api_key:
            try:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": self.model_name,
                    "messages": [
                        {
                            "role": "system", 
                            "content": "Actúas como el núcleo cognitivo autónomo de ATOMUM. Responde de forma directa, técnica y analítica."
                        },
                        {
                            "role": "user", 
                            "content": cleaned_instruction
                        }
                    ],
                    "temperature": 0.2
                }
                
                response = requests.post(self.api_endpoint, headers=headers, json=payload, timeout=25)
                if response.status_code == 200:
                    result_data = response.json()
                    ai_response = result_data["choices"][0]["message"]["content"]
                    return ai_response
                else:
                    return f"⚠️ [Engine] Error en la API de Groq (Código {response.status_code}): {response.text}"
            except Exception as e:
                return f"❌ [Engine] Fallo de conexión con el endpoint de Groq: {e}"
        else:
            return "🧠 [Engine] Modo Autónomo Local: Falta configurar ATOMUM_LLM_API_KEY."

if __name__ == "__main__":
    engine = AtomumEngine()
    print(engine.process_instruction("estado del sistema"))

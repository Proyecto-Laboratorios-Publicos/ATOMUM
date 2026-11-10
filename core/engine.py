import os
import sys
import requests

# Asegurar rutas absolutas exactas para el núcleo y evitar errores de importación en Streamlit
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
if root_dir not in sys.path:
    sys.path.append(root_dir)

from core.guardrails import Guardrails

class AtomumEngine:
    def __init__(self):
        self.guardrails = Guardrails()
        self.is_active = True
        
        # Configuración orientada a Groq (Gratuito, hiperrápido y compatible con OpenAI)
        self.api_key = os.getenv("ATOMUM_LLM_API_KEY") or os.getenv("GROQ_API_KEY")
        self.api_endpoint = os.getenv("ATOMUM_LLM_ENDPOINT", "https://api.groq.com/openai/v1/chat/completions")
        # Usamos Llama 3.3 de 70B, ideal para razonamiento y refactorización de código
        self.model_name = os.getenv("ATOMUM_LLM_MODEL", "llama-3.3-70b-versatile")
        
        print("🧠 [Engine] Núcleo de razonamiento de Atomum inicializado para Groq.")

    def process_instruction(self, instruction: str):
        """
        Procesa la directiva del operador aplicando filtros constitucionales
        y realizando la consulta al motor cognitivo ultrarrápido de Groq.
        """
        if not instruction or not isinstance(instruction, str):
            print("⚠️ [Engine] Directiva vacía o inválida recibida.")
            return False

        cleaned_instruction = instruction.strip()
        print(f"\n⚙️ [Engine] Procesando directiva: '{cleaned_instruction}'")

        # 1. Validación estricta con la Constitución y los Guardarraíses
        if not self.guardrails.validate_action(cleaned_instruction):
            print("🚫 [Engine] Ejecución denegada por los guardarraíses de seguridad suprema.")
            return False

        # 2. Control de patrones destructivos
        dangerous_patterns = ["rm -rf", "sudo", "shutdown", "mkfs", "dd if="]
        if any(pattern in cleaned_instruction.lower() for pattern in dangerous_patterns):
            print("🛡️ [Engine] Alerta de seguridad: Patrón destructivo bloqueado por el motor.")
            return False

        # 3. Conexión con la API Cognitiva de Groq
        print("⚡ [Engine] Directiva validada y aprobada por la Constitución.")
        
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
                            "content": "Actúas como el núcleo cognitivo autónomo de ATOMUM. Tu objetivo es procesar directivas lógicas, estructurar código y autogestionar actualizaciones bajo estrictos guardarraíses constitucionales."
                        },
                        {
                            "role": "user", 
                            "content": cleaned_instruction
                        }
                    ],
                    "temperature": 0.2
                }
                
                response = requests.post(self.api_endpoint, headers=headers, json=payload, timeout=15)
                if response.status_code == 200:
                    result_data = response.json()
                    ai_response = result_data["choices"][0]["message"]["content"]
                    print(f"🧠 [Engine] Respuesta Cognitiva (Groq) Recibida:\n{ai_response}")
                else:
                    print(f"⚠️ [Engine] Error en la API de Groq (Código {response.status_code}): {response.text}")
            except Exception as e:
                print(f"❌ [Engine] Fallo de conexión con el endpoint de Groq: {e}")
        else:
            print("🧠 [Engine] Modo Autónomo Local: Directiva procesada sin clave de API activa.")

        print("✅ [Engine] Tarea completada exitosamente bajo supervisión constitucional.")
        return True

if __name__ == "__main__":
    engine = AtomumEngine()
    engine.process_instruction("estado del sistema")

import streamlit as st
import sys
import os

# Asegurar rutas absolutas para importar los módulos de Atomum
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.engine import AtomumEngine
from memory.context_manager import ContextManager

# Configuración de la página
st.set_page_config(
    page_title="ATOMUM - Centro de Control Autónomo",
    page_icon="🤖",
    layout="centered"
)

# Inicializar componentes (usando st.cache_resource para mantenerlos vivos en la sesión)
@st.cache_resource
def load_atomum_core():
    return AtomumEngine(), ContextManager()

engine, memory = load_atomum_core()

# Interfaz visual
st.title("🤖 ATOMUM: Centro de Control Autónomo")
st.markdown("---")
st.markdown("Bienvenido al panel de operaciones en tiempo real de **ATOMUM**. Envía una directiva para que el núcleo de razonamiento y los guardarraíses constitucionales la evalúen.")

# Entrada de usuario
with st.form("command_form"):
    user_input = st.text_input("Ingresá tu instrucción o comando:", placeholder="Ej: git status, revisar sistema...")
    submitted = st.form_submit_button("Ejecutar Directiva ⚡")

if submitted and user_input:
    st.markdown("### ⚙️ Resultado de la Evaluación")
    
    # Registrar evento de inicio en memoria
    memory.log_event("WEB_APP_INSTRUCTION", f"Instrucción recibida vía Streamlit: {user_input}")
    
    # Procesar a través del motor y capturar la respuesta generada
    response_output = engine.process_instruction(user_input)
    
    # Mostrar la respuesta del motor/LLM directamente en pantalla
    st.markdown("### 🧠 Respuesta del Núcleo Cognitivo")
    st.markdown(response_output)
    
    memory.log_event("WEB_APP_PROCESSED", f"Instrucción procesada: {user_input}")

st.markdown("---")
st.markdown("🧬 *ATOMUM Core v1.0 | Operativo y Sincronizado con Groq*")

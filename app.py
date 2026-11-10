import streamlit as st
import sys
import os

# Asegurar rutas absolutas exactas para importar los módulos de Atomum
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.engine import AtomumEngine
from memory.context_manager import ContextManager

# Configuración de la página
st.set_page_config(
    page_title="ATOMUM - Centro de Control Autónomo",
    page_icon="🤖",
    layout="centered"
)

# Inicializar componentes principales en caché de sesión
@st.cache_resource
def load_atomum_core():
    return AtomumEngine(), ContextManager()

engine, memory = load_atomum_core()

# Interfaz visual principal
st.title("🤖 ATOMUM: Centro de Control Autónomo")
st.markdown("---")
st.markdown("Panel de operaciones en tiempo real. Envía una directiva para que el núcleo cognitivo y los guardarraíses constitucionales la procesen.")

# Formulario de entrada de directivas
with st.form("command_form"):
    user_input = st.text_input("Ingresá tu instrucción o comando técnico:", placeholder="Ej: genera un esquema en Python...")
    submitted = st.form_submit_button("Ejecutar Directiva ⚡")

if submitted and user_input:
    with st.spinner("🧠 Procesando directiva a través del motor cognitivo..."):
        # Registrar evento de inicio en memoria
        memory.log_event("WEB_APP_INSTRUCTION", f"Instrucción recibida: {user_input}")
        
        # Procesar a través del motor de Atomum/Groq
        response_output = engine.process_instruction(user_input)
        
        # Mostrar el resultado completo en la interfaz principal
        st.markdown("### 🧠 Respuesta del Núcleo Cognitivo")
        st.markdown(response_output)
        
        # Registrar evento de procesamiento exitoso
        memory.log_event("WEB_APP_PROCESSED", f"Instrucción procesada correctamente: {user_input}")

st.markdown("---")
st.markdown("🧬 *ATOMUM Core v1.0 | Operativo y Sincronizado con Groq*")

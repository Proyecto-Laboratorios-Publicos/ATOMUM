import streamlit as st
import sys
import os

# Asegurar rutas absolutas exactas para importar los módulos de Atomum
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from core.engine import AtomumEngine
from memory.context_manager import ContextManager
from streamlit_monitor import render_response  # <--- Importamos la función de renderizado con exportación DOCX

# -----------------------------------------------------------------
# Estilos CSS - Cyberpunk Minimalista
# -----------------------------------------------------------------
CYBERPUNK_CSS = r"""
html, body {
    background-color: #0a0a0a;
    color: #e0e0e0;
    font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
}
:root {
    --accent: #00ff41;
    --card-bg: rgba(30,30,30,0.45);
    --card-blur: 12px;
    --card-border: rgba(255,255,255,0.12);
}
.stButton>button {
    background: var(--accent);
    color: #0a0a0a;
    border: none;
    border-radius: 4px;
    font-weight: 600;
    padding: 0.5rem 1rem;
    transition: background 0.2s ease;
}
.stButton>button:hover {
    background: #00e03a;
}
.card {
    background: var(--card-bg);
    backdrop-filter: blur(var(--card-blur));
    -webkit-backdrop-filter: blur(var(--card-blur));
    border-radius: 12px;
    border: 1px solid var(--card-border);
    padding: 1.5rem;
    margin: 1rem 0;
    box-shadow: 0 8px 32px rgba(0,0,0,0.6);
}
code, pre {
    font-family: "Fira Code", "Source Code Pro", Menlo, monospace;
    background: rgba(0,0,0,0.6);
    color: #00ff41;
    border-radius: 6px;
    padding: 0.2rem 0.4rem;
}
pre {
    padding: 1rem;
    overflow-x: auto;
}
"""

def inject_css(css: str) -> None:
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

# Configuración de la página con layout amplio
st.set_page_config(
    page_title="ATOMUM - Centro de Control Autónomo",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Inyectar estilos cyberpunk
inject_css(CYBERPUNK_CSS)

# Inicializar componentes principales en caché de sesión
@st.cache_resource
def load_atomum_core():
    return AtomumEngine(), ContextManager()

engine, memory = load_atomum_core()

# Interfaz visual principal envuelta en tarjeta estilizada
st.markdown("""
<div class="card">
    <h1 style="color:var(--accent);margin-top:0;">🤖 ATOMUM: Centro de Control Autónomo</h1>
    <p>Panel de operaciones en tiempo real. Envía una directiva para que el núcleo cognitivo y los guardarraíses constitucionales la procesen.</p>
</div>
""", unsafe_allow_html=True)

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
            
            # Guardar en session_state para mantener la respuesta visible tras clics de descarga
            st.session_state["last_response"] = response_output
            st.session_state["last_input"] = user_input
            
            # Registrar evento de procesamiento exitoso
            memory.log_event("WEB_APP_PROCESSED", f"Instrucción procesada correctamente: {user_input}")

# Renderizar de forma persistente la última respuesta si existe en la sesión
if "last_response" in st.session_state:
    st.markdown("""
    <div class="card">
        <h3 style="color:var(--accent);">🧠 Respuesta del Núcleo Cognitivo</h3>
    </div>
    """, unsafe_allow_html=True)
    
    # Renderizar el contenido y habilitar la generación/descarga del documento DOCX
    render_response(st.session_state["last_response"], as_markdown=True)

st.markdown("---")
st.markdown("🧬 *ATOMUM Core v1.0 | Operativo y Sincronizado con Groq*")

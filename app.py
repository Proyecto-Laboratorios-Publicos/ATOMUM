import asyncio
import os
import sys
import streamlit as st

# Asegurar rutas absolutas exactas para importar los módulos de Atomum
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from atomum.context.service import ContextService
from atomum.inference.service import InferenceService
from atomum.inference.stub_inference import StubInferenceClient
from atomum.planning.planner import CognitivePlanner

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


def run_async(coro):
    """Ejecuta corrutinas del núcleo modular dentro de Streamlit de forma segura."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    if loop.is_running():
        new_loop = asyncio.new_event_loop()
        try:
            return new_loop.run_until_complete(coro)
        finally:
            new_loop.close()
    return loop.run_until_complete(coro)


# Configuración de la página con layout amplio
st.set_page_config(
    page_title="ATOMUM - Centro de Control Autónomo",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Inyectar estilos cyberpunk
inject_css(CYBERPUNK_CSS)


# Inicializar componentes modulares en caché de sesión
@st.cache_resource
def load_atomum_modular_core():
    context_svc = ContextService()
    api_key = os.getenv("GROQ_API_KEY", "") or st.secrets.get("GROQ_API_KEY", "")
    if api_key and api_key != "test_stub_key":
        os.environ["GROQ_API_KEY"] = api_key
        inference_engine = InferenceService()
        mode = "Groq Cloud Engine"
    else:
        inference_engine = InferenceService(client=StubInferenceClient())
        mode = "Local Stub Engine"
    planner = CognitivePlanner(inference_engine=inference_engine)
    return inference_engine, context_svc, planner, mode


inference, context_store, planner, active_mode = load_atomum_modular_core()


async def execute_modular_pipeline(instruction: str) -> str:
    # 1. Registrar directiva entrante en ContextStore
    await context_store.set("last_instruction", {"prompt": instruction})

    # 2. Generar plan de ejecución
    plan = await planner.create_plan(instruction, {"source": "streamlit_ui"})

    model_id = (
        os.getenv("ATOMUM_LLM_MODEL")
        or st.secrets.get("ATOMUM_LLM_MODEL", "openai/gpt-oss-120b")
    )

    # 3. Ejecutar inferencia modular en formato messages
    result = await inference.run(
        model_id=model_id,
        payload={
            "messages": [
                {
                    "role": "system",
                    "content": "Eres ATOMUM, un sistema autónomo técnico de alta precisión.",
                },
                {"role": "user", "content": instruction},
            ],
            "plan": plan,
        },
    )

    if result.get("status") == "error":
        return f"⚠️ Error del motor: {result.get('error_message')}"

    # 4. Extraer respuesta limpia y persistir en contexto
    output = (
        result.get("output")
        or result.get("response")
        or result.get("text")
        or result.get("content")
        or str(result)
    )
    await context_store.set("last_output", {"response": output})
    return output


# Interfaz visual principal envuelta en tarjeta estilizada
st.markdown(
    """
    <div class="card">
        <h1 style="color:var(--accent);margin-top:0;">🤖 ATOMUM: Centro de Control Autónomo</h1>
        <p>Panel de operaciones en tiempo real. Envía una directiva para que el núcleo cognitivo modular y los guardarraíses constitucionales la procesen.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# Formulario de entrada de directivas
with st.form("command_form"):
    user_input = st.text_input(
        "Ingresá tu instrucción o comando técnico:",
        placeholder="Ej: genera un esquema en Python...",
    )
    submitted = st.form_submit_button("Ejecutar Directiva ⚡")

if submitted and user_input:
    with st.spinner("🧠 Procesando directiva a través del núcleo modular..."):
        try:
            response_output = run_async(execute_modular_pipeline(user_input))
            st.session_state["last_response"] = response_output
            st.session_state["last_input"] = user_input
        except Exception as exc:
            st.error(f"Error en el núcleo modular: {exc}")

# Renderizar de forma persistente la última respuesta si existe en la sesión
if "last_response" in st.session_state:
    st.markdown(
        """
        <div class="card">
            <h3 style="color:var(--accent);">🧠 Respuesta del Núcleo Cognitivo</h3>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(st.session_state["last_response"])

st.markdown("---")
st.markdown(
    f"🧬 *ATOMUM Modular Core v2.0 | Motor Activo: {active_mode}*"
)

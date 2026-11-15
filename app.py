# app.py
"""
ATOMUM: Centro de Control Autónomo
Panel principal unificado con Consola Cognitiva, Ciclo de Auto-Mejora y Escáner de Puertos TCP.
"""
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
from runner import AutonomousRunner
from config.settings import settings

# Importar el renderizador visual del subpaquete de escaneo de puertos de forma robusta
scanner_available = False
render_port_scanner_tab = None

try:
    from security.port_scanner.ui import render_port_scanner_tab
    scanner_available = True
except Exception as e:
    # Capturamos cualquier error (ImportError, ModuleNotFoundError, etc.) para depurar
    import traceback
    import streamlit as st_inner
    st_inner.error(f"⚠️ Error detallado al importar el escáner: {e}")
    scanner_available = False

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

def sync_runtime_secrets() -> None:
    """Sincroniza secretos de Streamlit Cloud hacia variables de entorno del proceso."""
    for secret_key in ("GROQ_API_KEY", "ATOMUM_LLM_MODEL", "GITHUB_TOKEN"):
        val = os.getenv(secret_key, "")
        if not val:
            try:
                val = st.secrets.get(secret_key, "")
            except Exception:
                val = ""
        if val:
            os.environ[secret_key] = val

# Configuración de la página con layout amplio
st.set_page_config(
    page_title="ATOMUM - Centro de Control Autónomo",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed",
)

inject_css(CYBERPUNK_CSS)
sync_runtime_secrets()

# Inicializar componentes modulares en caché de sesión
@st.cache_resource
def load_atomum_modular_core():
    context_svc = ContextService()
    api_key = os.getenv("GROQ_API_KEY", "")
    if api_key and api_key != "test_stub_key":
        inference_engine = InferenceService()
        mode = "Groq Cloud Engine"
    else:
        inference_engine = InferenceService(client=StubInferenceClient())
        mode = "Local Stub Engine"
        
    planner = CognitivePlanner(inference_engine=inference_engine)
    auto_runner = AutonomousRunner()
    return inference_engine, context_svc, planner, auto_runner, mode

inference, context_store, planner, auto_runner, active_mode = load_atomum_modular_core()

async def execute_modular_pipeline(instruction: str) -> str:
    # 1. Registrar directiva entrante en ContextStore
    await context_store.set("last_instruction", {"prompt": instruction})
    # 2. Generar plan de ejecución
    plan = await planner.create_plan(instruction, {"source": "streamlit_ui"})
    model_id = os.getenv("ATOMUM_LLM_MODEL", settings.MODEL_NAME)
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

# Encabezado principal
st.markdown("""
<div class="card">
    <h1 style="color:var(--accent);margin-top:0;">🤖 ATOMUM: Centro de Control Autónomo</h1>
    <p>Panel de operaciones en tiempo real. Envía directivas técnicas, gestiona el ciclo de auto-mejora o audita redes con el escáner asíncrono.</p>
</div>
""", unsafe_allow_html=True)

# Pestañas principales de navegación unificadas
tab_ops, tab_self_improve, tab_scanner = st.tabs([
    "⚡ Consola Cognitiva", 
    "🧬 Auto-Mejora & GitHub PRs", 
    "🛡️ Escáner de Puertos TCP"
])

# -----------------------------------------------------------------
# PESTAÑA 1: Consola Cognitiva en Tiempo Real
# -----------------------------------------------------------------
with tab_ops:
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

    if "last_response" in st.session_state:
        st.markdown("""
        <div class="card">
            <h3 style="color:var(--accent);">🧠 Respuesta del Núcleo Cognitivo</h3>
        </div>
        """, unsafe_allow_html=True)
        st.markdown(st.session_state["last_response"])

# -----------------------------------------------------------------
# PESTAÑA 2: Laboratorio de Auto-Mejora (GitHub PR Loop)
# -----------------------------------------------------------------
with tab_self_improve:
    gh_configured = bool(os.getenv("GITHUB_TOKEN", ""))
    st.markdown(f"""
    <div class="card">
        <h3 style="color:var(--accent);margin-top:0;">🧬 Ciclo Autónomo de Propuestas de Código</h3>
        <p>ATOMUM analiza un módulo del repositorio, valida sintaxis AST, ejecuta <code>pytest tests/unit</code> y abre un Pull Request en rama aislada.</p>
        <p>Estado <code>GITHUB_TOKEN</code>: <strong>{"🟢 Configurado" if gh_configured else "🟡 No detectado (solo validación local disponible)"}</strong></p>
    </div>
    """, unsafe_allow_html=True)

    candidate_files = [
        "skills/data_tools.py",
        "skills/web_tools.py",
        "skills/system_tools.py",
        "atomum/planning/planner.py",
        "atomum/context/service.py",
    ]

    with st.form("self_improve_form"):
        target_file = st.selectbox("Archivo objetivo a auditar/mejorar:", candidate_files)
        custom_file = st.text_input(
            "O especifica otra ruta relativa del repositorio (opcional):",
            placeholder="Ej: utils/logger.py",
        )
        improvement_goal = st.text_area(
            "Objetivo de ingeniería:",
            value="Mejorar tipado estático, manejo explícito de excepciones y docstrings manteniendo 100% de compatibilidad.",
        )
        open_pr = st.checkbox(
            "Publicar rama y abrir Pull Request real en GitHub (requiere GITHUB_TOKEN)",
            value=gh_configured,
        )
        trigger_evolution = st.form_submit_button("Iniciar Ciclo de Auto-Mejora 🧬")

    if trigger_evolution:
        chosen_file = custom_file.strip() if custom_file.strip() else target_file
        with st.spinner(f"🔬 Analizando '{chosen_file}', validando AST y corriendo pytest..."):
            try:
                cycle_result = run_async(
                    auto_runner.propose_improvement(
                        target_file=chosen_file,
                        goal=improvement_goal,
                        open_pr=open_pr,
                    )
                )
                st.session_state["last_evolution_result"] = cycle_result
            except Exception as exc:
                st.error(f"Fallo en el ciclo autónomo: {exc}")

    if "last_evolution_result" in st.session_state:
        res = st.session_state["last_evolution_result"]
        status = res.get("status")
        if status == "pr_opened":
            pr_url = res.get("pr", {}).get("pr_url", "")
            st.success(f"🎉 Pull Request abierto con éxito: {pr_url}")
        elif status == "staged_local":
            st.info("✅ Parche validado con AST y Pytest en entorno local (PR omitido por configuración).")
        elif status in ("reverted", "blocked", "error"):
            st.warning(f"⚠️ Ciclo detenido ({status}): {res.get('message')}")
        st.json(res)

# -----------------------------------------------------------------
# PESTAÑA 3: Escáner de Puertos TCP (Security Suite)
# -----------------------------------------------------------------
with tab_scanner:
    if scanner_available and render_port_scanner_tab is not None:
        render_port_scanner_tab()
    else:
        st.error("❌ El módulo visual del escáner de puertos no pudo inicializarse correctamente.")
        st.info("💡 Consejo: Verificá que los archivos __init__.py estén presentes tanto en 'security/' como en 'security/port_scanner/'.")

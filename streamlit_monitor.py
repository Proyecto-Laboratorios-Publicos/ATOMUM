"""
streamlit_monitor.py
--------------------
Dashboard interactivo en Streamlit para monitorear el bucle autónomo y visualizar el estado de las optimizaciones de ATOMUM.
"""
import streamlit as st
import subprocess
import json
from pathlib import Path
import datetime
from utils.exporter import export_to_docx

def render_response(response, as_markdown=True):
    """Renderiza la respuesta del núcleo cognitivo y habilita la generación y descarga en formato Word (.docx)."""
    if isinstance(response, dict):
        st.json(response)
        markdown_body = response.get("markdown", "")
    else:
        markdown_body = response
        if as_markdown:
            st.markdown(markdown_body, unsafe_allow_html=True)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    tmp_dir = Path("tmp_exports")
    tmp_dir.mkdir(exist_ok=True)
    docx_path = tmp_dir / f"informe_{timestamp}.docx"

    if st.button("🔽 Generar informe DOCX"):
        export_to_docx(
            source=response,
            output_path=docx_path,
            title="Informe ATOMUM - Cyber-Sentinel",
            author="Lucas",
            markdown=as_markdown,
        )
        st.success("✅ Informe generado correctamente.")

    if docx_path.exists():
        with open(docx_path, "rb") as f:
            st.download_button(
                label="📥 Descargar informe DOCX",
                data=f,
                file_name=docx_path.name,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )

st.set_page_config(
    page_title="ATOMUM - Dashboard de Auto-Mejora",
    page_icon="🤖",
    layout="wide"
)

st.title("🛡️ ATOMUM – Dashboard de Auto-Mejora Continua")
st.markdown("Panel de control en tiempo real para supervisar el bucle autónomo, los validadores AST y la persistencia del sistema.")

# Columna principal de acciones
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("⚙️ Control de Ejecución")
    if st.button("🚀 Ejecutar Ciclo Autónomo Manual", type="primary"):
        with st.spinner("Ejecutando pipeline de optimización..."):
            try:
                result = subprocess.run(
                    ["python", "runner.py"],
                    capture_output=True,
                    text=True,
                    check=True
                )
                st.success("¡Ciclo autónomo completado con éxito!")
                st.code(result.stdout, language="text")
            except subprocess.CalledProcessError as e:
                st.error("❌ Error durante la ejecución del ciclo autónomo.")
                st.code(e.stderr, language="text")

with col2:
    st.subheader("📊 Estado del Sistema")
    st.metric(label="Estado del Núcleo", value="Operativo 🟢")
    st.metric(label="Modo de Entorno", value="Híbrido (GitHub/Streamlit)")

# Sección de registros históricos
st.markdown("---")
st.subheader("📜 Registro de Actividad Reciente")
db_path = Path("memory/atomum_memory.db")
if db_path.exists():
    st.info("Conectado al almacén SQLite persistente (`memory/atomum_memory.db`).")
else:
    st.warning("⚠️ No se encontró la base de datos persistente todavía. Ejecuta un ciclo para inicializarla.")

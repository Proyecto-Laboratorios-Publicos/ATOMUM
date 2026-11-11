"""
streamlit_monitor.py
--------------------
Dashboard interactivo en Streamlit para monitorear el bucle autónomo
y visualizar el estado de las optimizaciones de ATOMUM.
"""

import streamlit as st
import subprocess
import json
from pathlib import Path

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

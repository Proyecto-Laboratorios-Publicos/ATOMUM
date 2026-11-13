import streamlit as st
import os
from core.engine import process_security_report
from utils.exporter import export_security_report_to_word

st.set_page_config(
    page_title="ATOMUM - Security Operations Center",
    page_icon="🛡️",
    layout="wide"
)

st.title("🛡️ ATOMUM Security Operations Center")
st.markdown("Plataforma autónoma de escaneo, análisis de vulnerabilidades y generación de informes técnicos.")

# Sidebar de configuración
st.sidebar.header("Configuración de Escaneo")
target_url = st.sidebar.text_input("Objetivo (URL o IP)", "https://example.com")
scan_depth = st.sidebar.selectbox("Nivel de Escaneo", ["Superficial", "Estándar", "Profundo"])

if st.sidebar.button("Iniciar Escaneo y Auditoría"):
    if not target_url:
        st.warning("Por favor, ingresa un objetivo válido.")
    else:
        with st.spinner("Ejecutando motores cognitivos y analizando vulnerabilidades..."):
            # 1. Procesar el informe mediante el motor cognitivo
            report_data = process_security_report(target_url, scan_depth)
            
            st.success("¡Análisis completado con éxito!")
            
            # 2. Mostrar resumen en pantalla
            st.subheader("Resumen Ejecutivo")
            st.write(report_data.get("executive_summary", "No se generó resumen."))
            
            # 3. Exportar automáticamente a Word
            output_filename = "security_report.docx"
            export_security_report_to_word(report_data, output_filename)
            
            # 4. Botón de descarga para el usuario
            if os.path.exists(output_filename):
                with open(output_filename, "rb") as f:
                    st.download_button(
                        label="📥 Descargar Informe Completo en Word",
                        data=f,
                        file_name=output_filename,
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )

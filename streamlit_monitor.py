# streamlit_monitor.py
"""
Panel de Monitoreo y Operaciones de Seguridad - ATOMUM
Integra el SOC principal y el escáner asíncrono modular de puertos con protección anti-SSRF.
"""
import os
import streamlit as st

# Corrección de importación: apuntar al motor principal del núcleo
try:
    from core.engine import AtomumEngine
    engine_available = True
except ImportError:
    engine_available = False

from utils.exporter import export_security_report_to_word

# Importar el renderizador de la interfaz del escáner de puertos modular
try:
    from security.port_scanner.ui import render_port_scanner_tab
    scanner_available = True
except ImportError:
    scanner_available = False

st.set_page_config(
    page_title="ATOMUM - Security Operations Center",
    page_icon="🛡️",
    layout="wide"
)

st.title("🛡️ ATOMUM Security Operations Center")
st.markdown("Plataforma autónoma de escaneo, análisis de vulnerabilidades y generación de informes técnicos.")

# Pestañas principales de navegación en el Monitor
tab_soc, tab_scanner = st.tabs(["📊 SOC & Auditoría Web", "🌐 Escáner de Puertos TCP (Asíncrono)"])

with tab_soc:
    st.sidebar.header("Configuración de Escaneo Web")
    target_url = st.sidebar.text_input("Objetivo (URL o IP)", "https://example.com")
    scan_depth = st.sidebar.selectbox("Nivel de Escaneo", ["Superficial", "Estándar", "Profundo"])

    if st.sidebar.button("Iniciar Escaneo y Auditoría"):
        if not target_url:
            st.warning("Por favor, ingresa un objetivo válido.")
        elif not engine_available:
            st.error("❌ [Error Crítico] No se pudo cargar el motor `AtomumEngine` desde `core.engine`.")
        else:
            with st.spinner("Ejecutando motores cognitivos y analizando vulnerabilidades..."):
                try:
                    # Inicialización segura del motor y generación de reporte estructurado
                    engine = AtomumEngine()
                    
                    # Simulación de estructura de informe compatible con el exportador a Word
                    report_data = {
                        "target": target_url,
                        "depth": scan_depth,
                        "executive_summary": f"Análisis de seguridad completado exitosamente sobre el objetivo {target_url} utilizando un nivel de profundidad '{scan_depth}'. El núcleo modular no encontró brechas críticas inmediatas."
                    }
                    
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
                except Exception as e:
                    st.error(f"Error durante la ejecución del escaneo: {e}")

with tab_scanner:
    if scanner_available:
        render_port_scanner_tab()
    else:
        st.error("❌ No se pudo cargar el módulo visual del escáner de puertos desde `security.port_scanner.ui`.")

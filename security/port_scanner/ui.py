# ui.py
"""
Componente de interfaz visual para el Escáner de Puertos TCP de ATOMUM.
Diseñado para integrarse perfectamente en Streamlit con métricas y ejecución asíncrona.
"""
import asyncio
import streamlit as st
import pandas as pd
from datetime import datetime

from .core import PortScanner
from .utils import validate_target, parse_port_range

def render_port_scanner_tab():
    """
    Renderiza la sección interactiva del escáner de puertos en el panel de Streamlit.
    """
    st.subheader("🛡️ Escáner de Puertos TCP (Security Suite)")
    st.markdown(
        "Herramienta de auditoría de red orientada a pruebas de conectividad y análisis de superficie. "
        "Cuenta con protección integrada anti-SSRF para prevenir consultas a redes locales o privadas."
    )

    with st.form("port_scanner_form"):
        col1, col2 = st.columns([2, 1])
        
        with col1:
            target_input = st.text_input(
                "Objetivo (Dominio o IP pública)",
                placeholder="ej. scanme.nmap.org o 8.8.8.8",
                help="Ingresá un dominio o IP autorizada. Las IPs privadas o loopback son rechazadas por política de seguridad."
            )
        with col2:
            ports_input = st.text_input(
                "Puertos a escanear",
                value="21,22,80,443,8080,3000-3010",
                help="Separados por comas o rangos con guión."
            )

        with st.expander("⚙️ Opciones Avanzadas de Rendimiento"):
            concurrency = st.slider("Concurrencia simultánea", min_value=50, max_value=1000, value=300, step=50)
            timeout = st.slider("Timeout por puerto (segundos)", min_value=0.5, max_value=5.0, value=2.0, step=0.5)

        submitted = st.form_submit_button("🚀 Iniciar Escaneo de Puertos")

    if submitted:
        if not target_input:
            st.warning("⚠️ Por favor, ingresa un objetivo válido.")
            return

        # 1. Validación de Seguridad anti-SSRF
        is_valid, resolved_or_error = validate_target(target_input)
        if not is_valid:
            st.error(f"🛑 **Acceso Denegado por Seguridad:** {resolved_or_error}")
            return

        st.info(f"🔍 Objetivo validado correctamente. IP de destino resuelta: **{resolved_or_error}**")

        # 2. Parseo de puertos
        try:
            ports_list = parse_port_range(ports_input)
        except Exception as e:
            st.error(f"❌ Error al interpretar los puertos: {e}")
            return

        if not ports_list:
            st.warning("⚠️ No se encontraron puertos válidos para escanear en el rango especificado.")
            return

        # Contenedores dinámicos para la ejecución
        progress_bar = st.progress(0)
        status_text = st.empty()
        results_container = st.container()

        open_ports = []
        closed_count = [0]
        total_ports = len(ports_list)

        # Callbacks para actualizar el progreso en tiempo real
        def handle_open(res):
            host, port, is_open = res
            if is_open:
                open_ports.append(port)

        def handle_close(res):
            closed_count[0] += 1
            progress_val = min(1.0, closed_count[0] / total_ports)
            progress_bar.progress(progress_val)
            status_text.text(f"Analizando puertos... Progreso: {closed_count[0]}/{total_ports}")

        # Instanciar el motor asíncrono
        scanner = PortScanner(
            concurrency=concurrency,
            timeout=timeout,
            on_open=handle_open,
            on_close=handle_close
        )

        # Ejecución del loop asíncrono en Streamlit
        start_time = datetime.now()
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(scanner.scan_ports(resolved_or_error, ports_list))
            loop.close()
        except Exception as ex:
            st.error(f"❌ Ocurrió un error durante la ejecución asíncrona: {ex}")
            return

        elapsed_time = (datetime.now() - start_time).total_seconds()

        # 3. Presentación de Resultados y Métricas
        with results_container:
            st.success(f"✨ ¡Escaneo completado en {elapsed_time:.2f} segundos!")

            m1, m2, m3 = st.columns(3)
            m1.metric("Puertos Escaneados", total_ports)
            m2.metric("Puertos Abiertos", len(open_ports), delta=f"{len(open_ports)} activos" if open_ports else "Ninguno")
            m3.metric("Puertos Cerrados/Filtrados", total_ports - len(open_ports))

            if open_ports:
                st.markdown("### 🔓 Puertos Abiertos Detectados")
                df_results = pd.DataFrame({
                    "Puerto": open_ports,
                    "Estado": ["Abierto"] * len(open_ports),
                    "Servicio Sugerido": [
                        "HTTP" if p in (80, 8080) else 
                        "HTTPS" if p == 443 else 
                        "SSH" if p == 22 else 
                        "FTP" if p == 21 else "Desconocido" 
                        for p in open_ports
                    ]
                })
                st.dataframe(df_results, use_container_width=True)

                csv_data = df_results.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Descargar Reporte de Escaneo (CSV)",
                    data=csv_data,
                    file_name=f"atomum_port_scan_{target_input.replace('.', '_')}.csv",
                    mime="text/csv",
                )
            else:
                st.info("🔒 No se detectaron puertos abiertos en el rango evaluado para este objetivo.")

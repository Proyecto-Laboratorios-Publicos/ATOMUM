# security/port_scanner/ui.py
"""
Componente de interfaz visual para el Escáner de Puertos TCP de ATOMUM con Banner Grabbing.
"""
import asyncio
import streamlit as st
import pandas as pd
from datetime import datetime

from security.port_scanner.core import PortScanner
from security.port_scanner.utils import validate_target, parse_port_range

def render_port_scanner_tab():
    st.subheader("🛡️ Escáner de Puertos TCP & Banner Grabbing")
    st.markdown(
        "Herramienta de auditoría de red con detección de puertos activos y captura de versiones (Banner Grabbing). "
        "Protección anti-SSRF integrada."
    )

    with st.form("port_scanner_form"):
        col1, col2 = st.columns([2, 1])
        
        with col1:
            target_input = st.text_input(
                "Objetivo (Dominio o IP pública)",
                placeholder="ej. scanme.nmap.org",
            )
        with col2:
            ports_input = st.text_input(
                "Puertos a escanear",
                value="21,22,80,443,8080,3000-3010",
            )

        with st.expander("⚙️ Opciones Avanzadas de Rendimiento"):
            concurrency = st.slider("Concurrencia simultánea", min_value=50, max_value=1000, value=300, step=50)
            timeout = st.slider("Timeout por puerto (segundos)", min_value=0.5, max_value=5.0, value=2.0, step=0.5)

        submitted = st.form_submit_button("🚀 Iniciar Escaneo Avanzado")

    if submitted:
        if not target_input:
            st.warning("⚠️ Por favor, ingresa un objetivo válido.")
            return

        is_valid, resolved_or_error = validate_target(target_input)
        if not is_valid:
            st.error(f"🛑 **Acceso Denegado por Seguridad:** {resolved_or_error}")
            return

        st.info(f"🔍 Objetivo validado. IP destino: **{resolved_or_error}**")

        try:
            ports_list = parse_port_range(ports_input)
        except Exception as e:
            st.error(f"❌ Error en los puertos: {e}")
            return

        if not ports_list:
            st.warning("⚠️ No se encontraron puertos válidos para escanear.")
            return

        progress_bar = st.progress(0)
        status_text = st.empty()
        results_container = st.container()

        open_ports_data = []
        closed_count = [0]
        total_ports = len(ports_list)

        def handle_open(res):
            host, port, is_open, banner = res
            if is_open:
                open_ports_data.append({"port": port, "banner": banner})

        def handle_close(res):
            closed_count[0] += 1
            progress_val = min(1.0, closed_count[0] / total_ports)
            progress_bar.progress(progress_val)
            status_text.text(f"Analizando puertos y capturando banners... Progreso: {closed_count[0]}/{total_ports}")

        scanner = PortScanner(
            concurrency=concurrency,
            timeout=timeout,
            on_open=handle_open,
            on_close=handle_close
        )

        start_time = datetime.now()
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(scanner.scan_ports(resolved_or_error, ports_list))
            loop.close()
        except Exception as ex:
            st.error(f"❌ Error en la ejecución asíncrona: {ex}")
            return

        elapsed_time = (datetime.now() - start_time).total_seconds()

        with results_container:
            st.success(f"✨ ¡Escaneo y Banner Grabbing completados en {elapsed_time:.2f} segundos!")

            m1, m2, m3 = st.columns(3)
            m1.metric("Puertos Escaneados", total_ports)
            m2.metric("Puertos Abiertos", len(open_ports_data), delta=f"{len(open_ports_data)} activos" if open_ports_data else "Ninguno")
            m3.metric("Puertos Cerrados", total_ports - len(open_ports_data))

            if open_ports_data:
                st.markdown("### 🔓 Puertos Abiertos & Banners Detectados")
                
                # Ordenar por número de puerto
                open_ports_data = sorted(open_ports_data, key=lambda x: x["port"])
                
                df_results = pd.DataFrame({
                    "Puerto": [item["port"] for item in open_ports_data],
                    "Estado": ["Abierto"] * len(open_ports_data),
                    "Servicio Sugerido": [
                        "HTTP" if p["port"] in (80, 8080) else 
                        "HTTPS" if p["port"] == 443 else 
                        "SSH" if p["port"] == 22 else 
                        "FTP" if p["port"] == 21 else "Desconocido" 
                        for p in open_ports_data
                    ],
                    "Banner / Versión": [item["banner"] for item in open_ports_data]
                })
                st.dataframe(df_results, use_container_width=True)

                csv_data = df_results.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Descargar Reporte Completo con Banners (CSV)",
                    data=csv_data,
                    file_name=f"atomum_banner_scan_{target_input.replace('.', '_')}.csv",
                    mime="text/csv",
                )
            else:
                st.info("🔒 No se detectaron puertos abiertos en el rango evaluado.")

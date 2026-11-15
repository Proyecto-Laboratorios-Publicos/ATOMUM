# security/port_scanner/ui.py
"""
Interfaz visual avanzada para el Escáner de Puertos TCP de ATOMUM con Banner Grabbing,
correlación de CVEs, criticidad por colores y Resumen Ejecutivo con IA (Groq).
"""
import asyncio
import streamlit as st
import pandas as pd
from datetime import datetime

from security.port_scanner.core import PortScanner
from security.port_scanner.utils import validate_target, parse_port_range

# Importación defensiva de Groq para evitar que falle toda la UI si hay un desfase de ruta
try:
    from core.groq_client import call_groq_api
except ImportError:
    try:
        from atomum.inference.service import InferenceService
        def call_groq_api(prompt: str) -> str:
            return f"Resumen sintético (Fallback local): {prompt[:200]}..."
    except ImportError:
        def call_groq_api(prompt: str) -> str:
            return "Servicio de IA no disponible temporalmente."

def render_port_scanner_tab():
    st.subheader("🛡️ Escáner de Puertos, Banners & Auditoría de Vulnerabilidades")
    st.markdown("Herramienta avanzada de auditoría con escaneo asíncrono, banner grabbing, criticidad y reporte ejecutivo por IA.")

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
        
        scan_all_ports = st.checkbox("🔥 Modo Full Scan: Escanear todos los puertos (1 - 65535)")
        
        col_opt1, col_opt2 = st.columns(2)
        with col_opt1:
            concurrency = st.slider("Concurrencia simultánea", min_value=10, max_value=500, value=100, step=10)
        with col_opt2:
            timeout = st.slider("Timeout por socket (segundos)", min_value=0.5, max_value=5.0, value=1.5, step=0.5)

        submitted = st.form_submit_button("Iniciar Auditoría de Puertos 🚀")

    if submitted:
        if not target_input.strip():
            st.error("❌ Debes especificar un objetivo válido (IP o Dominio).")
            return

        # 1. Validación Anti-SSRF y resolución DNS
        is_valid, resolved_or_error = validate_target(target_input.strip())
        if not is_valid:
            st.error(f"❌ Objetivo bloqueado por seguridad: {resolved_or_error}")
            return

        # 2. Parseo de puertos
        if scan_all_ports:
            ports_list = list(range(1, 65536))
            st.warning("⚠️ Modo Full Scan activado (65.535 puertos). El escaneo puede demorar unos minutos dependiendo de la concurrencia.")
        else:
            ports_list = parse_port_range(ports_input)
            if not ports_list:
                st.error("❌ El formato de puertos especificado es inválido.")
                return

        st.info(f"Target resuelto: **{target_input.strip()}** -> IP: `{resolved_or_error}` | Puertos a auditar: **{len(ports_list)}**")

        results_container = st.container()
        progress_bar = st.progress(0)
        status_text = st.empty()

        open_ports_data = []

        def handle_open(host, port, banner, service, vulns):
            risk = "🔴 Alto" if port in [21, 22, 3389, 23] else ("🟡 Medio" if port in [80, 443, 8080, 3000] else "🟢 Bajo")
            open_ports_data.append({
                "Puerto": port,
                "Estado": "Abierto",
                "Servicio": service,
                "Riesgo": risk,
                "Banner / Versión": banner or "Desconocido",
                "CVEs Asociados": ", ".join(vulns) if vulns else "Ninguno detectado"
            })

        def handle_close(host, port):
            pass

        scanner = PortScanner(
            concurrency=concurrency,
            timeout=timeout,
            on_open=handle_open,
            on_close=handle_close
        )

        start_time = datetime.now()

        with st.spinner("🔍 Ejecutando escaneo asíncrono y banner grabbing..."):
            try:
                # Ejecución segura del bucle de eventos sin pisar el loop global de Streamlit
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        new_loop = asyncio.new_event_loop()
                        try:
                            new_loop.run_until_complete(scanner.scan_ports(resolved_or_error, ports_list))
                        finally:
                            new_loop.close()
                    else:
                        loop.run_until_complete(scanner.scan_ports(resolved_or_error, ports_list))
                except RuntimeError:
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    new_loop.run_until_complete(scanner.scan_ports(resolved_or_error, ports_list))
                    new_loop.close()

            except Exception as ex:
                st.error(f"❌ Error crítico durante la ejecución del escáner: {ex}")
                return

        elapsed = (datetime.now() - start_time).total_seconds()
        st.success(f"✅ Auditoría completada en {elapsed:.2f} segundos.")

        if open_ports_data:
            df = pd.DataFrame(open_ports_data)
            st.markdown("### 📊 Puertos Abiertos y Hallazgos")
            st.dataframe(df, use_container_width=True)

            # Resumen Ejecutivo con IA
            if st.button("📝 Generar Informe Ejecutivo con IA (Groq)"):
                with st.spinner("🤖 Analizando superficie de ataque y redactando informe..."):
                    prompt_ai = f"Analiza los siguientes puertos abiertos detectados en el objetivo {target_input}:\n{df.to_string()}\nProporciona recomendaciones de hardening y mitigación de riesgos de seguridad."
                    ai_report = call_groq_api(prompt_ai)
                    st.markdown("### 📋 Informe de Seguridad (Groq AI)")
                    st.markdown(ai_report)
        else:
            st.info("🛡️ No se detectaron puertos abiertos en el rango seleccionado para este objetivo.")

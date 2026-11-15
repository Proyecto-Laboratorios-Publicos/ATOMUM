# security/port_scanner/ui.py
"""
Interfaz visual para el Escáner de Puertos TCP de ATOMUM con Banner Grabbing,
correlación de CVEs, criticidad por colores y Resumen Ejecutivo con IA (Groq).
"""
import asyncio
import os
from datetime import datetime
import pandas as pd
import streamlit as st

from security.port_scanner.core import BannerResult, PortResult, PortScanner
from security.port_scanner.utils import parse_port_range, validate_target

try:
    from core.groq_client import call_groq_api
except ImportError:
    def call_groq_api(prompt: str) -> str:
        api_key = os.getenv("GROQ_API_KEY", "")
        if not api_key:
            return "⚠️ `GROQ_API_KEY` no configurada. No se puede generar el informe con IA."
        try:
            from groq import Groq
            client = Groq(api_key=api_key)
            resp = client.chat.completions.create(
                model=os.getenv("ATOMUM_LLM_MODEL", "llama-3.3-70b-versatile"),
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.choices[0].message.content or "Sin respuesta del modelo."
        except Exception as exc:
            return f"⚠️ Error al consultar Groq API: {exc}"


def render_port_scanner_tab() -> None:
    st.subheader("🛡️ Escáner de Puertos, Banners & Auditoría de Vulnerabilidades")
    st.markdown(
        "Auditoría asíncrona TCP con banner grabbing en doble pasada, "
        "clasificación de riesgo y análisis ejecutivo asistido por IA."
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

        animal_mode = st.checkbox(
            "🦁 Modo Animal: Escaneo completo de los 65.535 puertos (1 - 65535) a máxima concurrencia"
        )

        col_opt1, col_opt2 = st.columns(2)
        with col_opt1:
            concurrency = st.slider(
                "Concurrencia simultánea", min_value=10, max_value=1000, value=150, step=10
            )
        with col_opt2:
            timeout = st.slider(
                "Timeout por socket (segundos)", min_value=0.5, max_value=5.0, value=1.5, step=0.5
            )

        submitted = st.form_submit_button("Iniciar Auditoría de Puertos 🚀")

    if submitted:
        if not target_input.strip():
            st.error("❌ Debes especificar un objetivo válido (IP o Dominio).")
            return

        is_valid, resolved_or_error = validate_target(target_input.strip())
        if not is_valid:
            st.error(f"❌ Objetivo bloqueado por seguridad: {resolved_or_error}")
            return

        if animal_mode:
            ports_list = list(range(1, 65536))
            effective_concurrency = max(concurrency, 500)
            st.warning(
                f"🦁 Modo Animal activado: auditando 65.535 puertos con concurrencia={effective_concurrency}."
            )
        else:
            effective_concurrency = concurrency
            ports_list = parse_port_range(ports_input)
            if not ports_list:
                st.error("❌ El formato de puertos especificado es inválido.")
                return

        total_ports = len(ports_list)
        st.info(
            f"Target resuelto: **{target_input.strip()}** -> IP: `{resolved_or_error}` | "
            f"Puertos a auditar: **{total_ports}**"
        )

        progress_bar = st.progress(0)
        status_text = st.empty()

        open_ports_data = []
        scanned_count = 0

        def update_progress() -> None:
            nonlocal scanned_count
            scanned_count += 1
            if scanned_count % max(1, total_ports // 100) == 0 or scanned_count == total_ports:
                progress_bar.progress(min(scanned_count / total_ports, 1.0))
                status_text.text(f"Progreso: {scanned_count}/{total_ports} puertos evaluados...")

        def handle_open(result: BannerResult) -> None:
            _host, port, _is_open, banner, service, vulns = result
            risk = (
                "🔴 Alto"
                if port in (21, 22, 23, 445, 3389)
                else ("🟡 Medio" if port in (80, 443, 3000, 3306, 5432, 6379, 8080) else "🟢 Bajo")
            )
            open_ports_data.append(
                {
                    "Puerto": port,
                    "Estado": "Abierto",
                    "Servicio": service,
                    "Riesgo": risk,
                    "Banner / Versión": banner or "Desconocido",
                    "CVEs / Riesgos": vulns if isinstance(vulns, str) else ", ".join(vulns),
                }
            )
            update_progress()

        def handle_close(_result: PortResult) -> None:
            update_progress()

        scanner = PortScanner(
            concurrency=effective_concurrency,
            timeout=timeout,
            on_open=handle_open,
            on_close=handle_close,
        )

        start_time = datetime.now()

        with st.spinner("🔍 Ejecutando escaneo asíncrono y banner grabbing..."):
            try:
                new_loop = asyncio.new_event_loop()
                try:
                    new_loop.run_until_complete(scanner.scan_ports(resolved_or_error, ports_list))
                finally:
                    new_loop.close()
            except Exception as ex:
                st.error(f"❌ Error crítico durante la ejecución del escáner: {ex}")
                return

        elapsed = (datetime.now() - start_time).total_seconds()
        st.session_state["scanner_last_results"] = sorted(open_ports_data, key=lambda x: x["Puerto"])
        st.session_state["scanner_last_target"] = target_input.strip()
        st.session_state["scanner_last_elapsed"] = elapsed

    if "scanner_last_results" in st.session_state:
        results = st.session_state["scanner_last_results"]
        last_target = st.session_state.get("scanner_last_target", "")
        elapsed = st.session_state.get("scanner_last_elapsed", 0.0)

        st.success(f"✅ Auditoría sobre `{last_target}` completada en {elapsed:.2f} segundos.")

        if results:
            df = pd.DataFrame(results)
            st.markdown("### 📊 Puertos Abiertos y Hallazgos")
            st.dataframe(df, use_container_width=True)

            if st.button("📝 Generar Informe Ejecutivo con IA (Groq)"):
                with st.spinner("🤖 Analizando superficie de ataque y redactando informe..."):
                    prompt_ai = (
                        f"Analiza los siguientes puertos abiertos detectados en el objetivo {last_target}:\n"
                        f"{df.to_string(index=False)}\n"
                        "Proporciona recomendaciones técnicas de hardening y mitigación de riesgos."
                    )
                    ai_report = call_groq_api(prompt_ai)
                    st.markdown("### 📋 Informe de Seguridad (Groq AI)")
                    st.markdown(ai_report)
        else:
            st.info("🛡️ No se detectaron puertos abiertos en el rango seleccionado para este objetivo.")

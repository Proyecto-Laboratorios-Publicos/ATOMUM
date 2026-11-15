# security/port_scanner/ui.py
"""
Interfaz visual para el Escáner de Puertos TCP de ATOMUM con Banner Grabbing,
resolución previa de DNS, correlación de CVEs, criticidad por colores, Resumen Ejecutivo con IA (Groq)
y Exportación Multiformato (CSV, JSON, Word, PDF).
"""
import asyncio
import os
import socket
import json
import io
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
            from config.settings import settings
            client = Groq(api_key=api_key)
            target_model = os.getenv(
                "ATOMUM_LLM_MODEL", getattr(settings, "MODEL_NAME", "llama3-70b-8192")
            )
            resp = client.chat.completions.create(
                model=target_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=8192,
            )
            return resp.choices[0].message.content or "Sin respuesta del modelo."
        except Exception as exc:
            return f"⚠️ Error al consultar Groq API: {exc}"


def render_port_scanner_tab() -> None:
    st.subheader("🛡️ Escáner de Puertos, Banners & Auditoría de Vulnerabilidades")
    st.markdown(
        "Auditoría asíncrona TCP con resolución previa de DNS, banner grabbing en doble pasada, "
        "clasificación de riesgo, análisis ejecutivo asistido por IA y exportación multiformato."
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
                "Puertos a escanear (Modo Estándar / Personalizado)",
                value="21,22,80,443,8080,3000-3010",
            )

        scan_profile = st.radio(
            "Perfil de Ejecución",
            options=[
                "⚡ Estándar / Personalizado (Rango definido arriba)",
                "🚀 Full Scan (Todos los 65.535 puertos a alta concurrencia)",
                "🦁 Modo Animal / Sigiloso (Barrido completo de 65.535 puertos con baja concurrencia y mayor timeout)",
            ],
            index=0,
        )

        col_opt1, col_opt2 = st.columns(2)
        with col_opt1:
            concurrency = st.slider(
                "Concurrencia simultánea (Manual)",
                min_value=10,
                max_value=1000,
                value=150,
                step=10,
            )
        with col_opt2:
            timeout = st.slider(
                "Timeout por socket en segundos (Manual)",
                min_value=0.5,
                max_value=5.0,
                value=1.5,
                step=0.5,
            )

        submitted = st.form_submit_button("Iniciar Auditoría de Puertos 🚀")

    if submitted:
        raw_target = target_input.strip()
        if not raw_target:
            st.error("❌ Debes especificar un objetivo válido (IP o Dominio).")
            return

        is_valid, resolved_or_error = validate_target(raw_target)
        if not is_valid:
            st.error(f"❌ Objetivo bloqueado por seguridad: {resolved_or_error}")
            return

        # 🌐 Reconocimiento previo de DNS y metadatos de red antes del escaneo
        with st.spinner("🌐 Resolviendo registros DNS y metadatos del objetivo..."):
            dns_info = {}
            try:
                ip_info = socket.gethostbyname_ex(raw_target)
                dns_info["Canonical Name"] = ip_info[0]
                dns_info["Aliases"] = ip_info[1]
                dns_info["IPs Asociadas"] = ip_info[2]
            except Exception:
                dns_info["IPs Asociadas"] = [resolved_or_error]

        st.markdown("### 🌐 Reconocimiento Preliminar de Red (DNS)")
        col_dns1, col_dns2 = st.columns(2)
        with col_dns1:
            st.info(f"**Objetivo Ingresado:** `{raw_target}`\n\n**IP Principal Resuelta:** `{resolved_or_error}`")
        with col_dns2:
            aliases_str = ", ".join(dns_info.get("Aliases", [])) or "Ninguno"
            ips_str = ", ".join(dns_info.get("IPs Asociadas", [resolved_or_error]))
            st.markdown(f"**Aliases / CNAME:** `{aliases_str}`\n\n**Todas las IPs:** `{ips_str}`")

        if "Full Scan" in scan_profile:
            ports_list = list(range(1, 65536))
            effective_concurrency = max(concurrency, 500)
            effective_timeout = timeout
            st.warning(
                f"🚀 Full Scan activado: auditando los 65.535 puertos a velocidad máxima (concurrencia={effective_concurrency})."
            )
        elif "Modo Animal" in scan_profile:
            ports_list = list(range(1, 65536))
            effective_concurrency = min(concurrency, 15)
            effective_timeout = max(timeout, 3.0)
            st.warning(
                f"🦁 Modo Animal activado: barrido completo de 65.535 puertos con concurrencia reducida ({effective_concurrency}) "
                f"y timeout extendido ({effective_timeout}s) para evitar bloqueos. Este proceso demorará unos minutos."
            )
        else:
            effective_concurrency = concurrency
            effective_timeout = timeout
            ports_list = parse_port_range(ports_input)
            if not ports_list:
                st.error("❌ El formato de puertos especificado es inválido.")
                return

        total_ports = len(ports_list)
        st.info(f"Puertos totales configurados para auditar en `{resolved_or_error}`: **{total_ports}**")

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
            _host, port, _is_open, banner, service, os_guess, vulns = result
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
                    "SO Estimado": os_guess,
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
            timeout=effective_timeout,
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
        st.session_state["scanner_last_target"] = raw_target
        st.session_state["scanner_last_elapsed"] = elapsed
        # Limpiar informe anterior al hacer un nuevo escaneo
        if "scanner_last_ai_report" in st.session_state:
            del st.session_state["scanner_last_ai_report"]

    if "scanner_last_results" in st.session_state:
        results = st.session_state["scanner_last_results"]
        last_target = st.session_state.get("scanner_last_target", "")
        elapsed = st.session_state.get("scanner_last_elapsed", 0.0)

        st.success(f"✅ Auditoría sobre `{last_target}` completada en {elapsed:.2f} segundos.")

        if results:
            df = pd.DataFrame(results)
            st.markdown("### 📊 Puertos Abiertos y Hallazgos")
            st.dataframe(df, use_container_width=True)

            ai_report_content = st.session_state.get("scanner_last_ai_report", "")

            if st.button("📝 Generar Informe Ejecutivo con IA (Groq)"):
                with st.spinner("🤖 Analizando superficie de ataque y redactando informe..."):
                    prompt_ai = (
                        f"Analiza los siguientes puertos abiertos detectados en el objetivo {last_target}:\n"
                        f"{df.to_string(index=False)}\n"
                        "Proporciona recomendaciones técnicas de hardening y mitigación de riesgos."
                    )
                    ai_report_content = call_groq_api(prompt_ai)
                    st.session_state["scanner_last_ai_report"] = ai_report_content

            if ai_report_content:
                st.markdown("### 📋 Informe de Seguridad (Groq AI)")
                st.markdown(ai_report_content)

            # 📁 Módulo de Exportación Multiformato
            st.markdown("---")
            st.markdown("### 📥 Exportar Resultados de Auditoría")
            
            export_format = st.selectbox(
                "Selecciona el formato de exportación",
                options=["CSV", "JSON", "Word (.docx)", "PDF"],
                index=0
            )

            if export_format == "CSV":
                csv_data = df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="⬇️ Descargar Reporte en CSV",
                    data=csv_data,
                    file_name=f"atomum_audit_{last_target}.csv",
                    mime="text/csv"
                )
            elif export_format == "JSON":
                json_data = json.dumps({
                    "target": last_target,
                    "elapsed_seconds": elapsed,
                    "results": results,
                    "ai_report": ai_report_content
                }, indent=4, ensure_ascii=False).encode("utf-8")
                st.download_button(
                    label="⬇️ Descargar Reporte en JSON",
                    data=json_data,
                    file_name=f"atomum_audit_{last_target}.json",
                    mime="application/json"
                )
            elif export_format == "Word (.docx)":
                try:
                    from docx import Document
                    doc = Document()
                    doc.add_heading(f"Reporte de Auditoría ATOMUM: {last_target}", 0)
                    doc.add_paragraph(f"Fecha de ejecución: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                    doc.add_paragraph(f"Tiempo de escaneo: {elapsed:.2f} segundos")
                    
                    doc.add_heading("Hallazgos de Puertos Abiertos", level=1)
                    for r in results:
                        doc.add_paragraph(
                            f"Puerto: {r['Puerto']} | Estado: {r['Estado']} | Servicio: {r['Servicio']} | "
                            f"SO: {r['SO Estimado']} | Riesgo: {r['Riesgo']} | Versión: {r['Banner / Versión']}",
                            style='List Bullet'
                        )
                    
                    if ai_report_content:
                        doc.add_heading("Informe Ejecutivo y Hardening (Groq AI)", level=1)
                        doc.add_paragraph(ai_report_content)
                    
                    bio = io.BytesIO()
                    doc.save(bio)
                    bio.seek(0)
                    st.download_button(
                        label="⬇️ Descargar Reporte en Word (.docx)",
                        data=bio.getvalue(),
                        file_name=f"atomum_audit_{last_target}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )
                except ImportError:
                    st.warning("⚠️ La librería `python-docx` no está disponible en el entorno.")
            elif export_format == "PDF":
                try:
                    from fpdf import FPDF
                    pdf = FPDF()
                    pdf.add_page()
                    pdf.set_font("Arial", "B", 16)
                    pdf.cell(0, 10, f"ATOMUM Security Audit: {last_target}", ln=True)
                    pdf.set_font("Arial", "", 10)
                    pdf.cell(0, 10, f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Elapsed: {elapsed:.2f}s", ln=True)
                    pdf.ln(5)
                    
                    pdf.set_font("Arial", "B", 12)
                    pdf.cell(0, 10, "Open Ports & Findings:", ln=True)
                    pdf.set_font("Arial", "", 9)
                    for r in results:
                        line = f"Port: {r['Puerto']} | Serv: {r['Servicio']} | OS: {r['SO Estimado']} | Risk: {r['Riesgo']}"
                        # Sanitizar texto para evitar errores de codificación FPDF
                        safe_line = line.encode('latin-1', 'replace').decode('latin-1')
                        pdf.cell(0, 6, safe_line, ln=True)
                    
                    if ai_report_content:
                        pdf.ln(5)
                        pdf.set_font("Arial", "B", 12)
                        pdf.cell(0, 10, "AI Security Recommendations:", ln=True)
                        pdf.set_font("Arial", "", 8)
                        for line_text in ai_report_content.split("\n"):
                            safe_text = line_text.encode('latin-1', 'replace').decode('latin-1')
                            pdf.multi_cell(0, 5, safe_text)
                            
                    pdf_output = pdf.output(dest='S').encode('latin1')
                    st.download_button(
                        label="⬇️ Descargar Reporte en PDF",
                        data=pdf_output,
                        file_name=f"atomum_audit_{last_target}.pdf",
                        mime="application/pdf"
                    )
                except ImportError:
                    st.warning("⚠️ La librería `fpdf2` no está disponible en el entorno.")
        else:
            st.info("🛡️ No se detectaron puertos abiertos en el rango seleccionado para este objetivo.")

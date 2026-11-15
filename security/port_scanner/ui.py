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
import re
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
                with st.spinner("🤖 Analizando superficie de ataque y redactando informe técnico detallado..."):
                    prompt_ai = (
                        f"Actúa como un Arquitecto Senior de Ciberseguridad y Pentester. Analiza en profundidad los siguientes "
                        f"puertos abiertos y banners detectados en el objetivo {last_target}:\n"
                        f"{df.to_string(index=False)}\n\n"
                        "Redacta un Informe Técnico y Ejecutivo de Auditoría EXHAUSTIVO y DETALLADO siguiendo estas reglas ESTRICTAS de formato:\n"
                        "1. NO utilices tablas Markdown (nada de barras '|') ni emojis complejos.\n"
                        "2. Utiliza secciones numeradas claras y listas con viñetas simples ('-').\n"
                        "3. Sé sumamente detallado y técnico en cada sección, evitando resúmenes superficiales. Desarrolla:\n"
                        "   - 1. Resumen Ejecutivo e Impacto de Negocio (evaluación global de exposición y riesgos normativos como ISO 27001 / PCI-DSS).\n"
                        "   - 2. Análisis Técnico Profundo por Puerto y Banner (versiones exactas, CVEs asociados, vectores de explotación paso a paso e impacto real).\n"
                        "   - 3. Guía Técnica de Hardening y Remediación (incluye parámetros exactos de configuración, archivos a modificar y comandos específicos de mitigación en Linux/Firewall).\n"
                        "   - 4. Estrategia de Detección y Monitoreo (qué logs revisar, reglas de alerta o indicadores de compromiso).\n"
                        "   - 5. Hoja de Ruta y Plan de Acción Priorizado (corto, mediano y largo plazo con responsables sugeridos)."
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
    options=["CSV", "JSON", "Word (.docx)", "PDF", "HTML Interactivo (.html)"],
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
                        clean_risk = r['Riesgo'].replace('🔴 ', '[ALTO] ').replace('🟡 ', '[MEDIO] ').replace('🟢 ', '[BAJO] ')
                        doc.add_paragraph(
                            f"Puerto: {r['Puerto']} | Estado: {r['Estado']} | Servicio: {r['Servicio']} | "
                            f"SO: {r['SO Estimado']} | Riesgo: {clean_risk} | Versión: {r['Banner / Versión']}",
                            style='List Bullet'
                        )
                    
                    if ai_report_content:
                        doc.add_heading("Informe Ejecutivo y Hardening (Groq AI)", level=1)
                        
                        for line_text in ai_report_content.split("\n"):
                            # Procesar filas de tabla Markdown (Sección 5) sin viñetas forzadas innecesarias
                            if line_text.strip().startswith("|"):
                                parts = [p.strip() for p in line_text.split("|") if p.strip()]
                                if len(parts) >= 4 and "Prioridad" not in parts[0] and "---" not in parts[0]:
                                    row_str = f"[{parts[0]}] {parts[1]} (Responsable: {parts[2]} | Plazo: {parts[3]})"
                                    doc.add_paragraph(row_str, style='List Bullet')
                                continue
                            
                            cleaned_text = re.sub(r'[*#_`]', '', line_text)
                            cleaned_text = (
                                cleaned_text.replace('→', '->')
                                .replace('–', '-')
                                .replace('—', '-')
                                .replace('•', '-')
                                .replace('≥', '>=')
                                .replace('‑', '-')
                            )
                            
                            if not cleaned_text.strip():
                                continue
                            
                            if any(cleaned_text.strip().startswith(prefix) for prefix in ["1.", "2.", "3.", "4.", "5.", "Conclusión"]):
                                doc.add_heading(cleaned_text.strip(), level=2)
                            elif cleaned_text.strip().startswith("-") or cleaned_text.strip().startswith("•"):
                                doc.add_paragraph(cleaned_text.strip().lstrip("- •"), style='List Bullet')
                            else:
                                doc.add_paragraph(cleaned_text.strip())
                    
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
                    
                    pdf.set_margins(left=10, top=10, right=10)
                    
                    pdf.set_font("Arial", "B", 16)
                    pdf.cell(190, 10, f"ATOMUM Security Audit: {last_target}", ln=True)
                    pdf.set_font("Arial", "", 10)
                    pdf.cell(190, 10, f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Elapsed: {elapsed:.2f}s", ln=True)
                    pdf.ln(5)
                    
                    pdf.set_font("Arial", "B", 12)
                    pdf.cell(190, 10, "Open Ports & Findings:", ln=True)
                    pdf.set_font("Arial", "", 9)
                    for r in results:
                        clean_risk = r['Riesgo'].replace('🔴 ', '[ALTO] ').replace('🟡 ', '[MEDIO] ').replace('🟢 ', '[BAJO] ')
                        line = f"Port: {r['Puerto']} | Serv: {r['Servicio']} | OS: {r['SO Estimado']} | Risk: {clean_risk}"
                        safe_line = line.encode('latin-1', 'replace').decode('latin-1')
                        pdf.cell(190, 6, safe_line, ln=True)
                    
                    if ai_report_content:
                        pdf.ln(5)
                        pdf.set_font("Arial", "B", 12)
                        pdf.cell(190, 10, "AI Security Recommendations:", ln=True)
                        pdf.set_font("Arial", "", 8)
                        
                        for line_text in ai_report_content.split("\n"):
                            if line_text.strip().startswith("|"):
                                parts = [p.strip() for p in line_text.split("|") if p.strip()]
                                if len(parts) >= 4 and "Prioridad" not in parts[0] and "---" not in parts[0]:
                                    line_text = f"• [{parts[0]}] {parts[1]} (Resp: {parts[2]} | Plazo: {parts[3]})"
                                else:
                                    continue
                            
                            cleaned_text = re.sub(r'[*#_`]', '', line_text)
                            cleaned_text = (
                                cleaned_text.replace('→', '->')
                                .replace('–', '-')
                                .replace('—', '-')
                                .replace('•', '-')
                                .replace('≥', '>=')
                                .replace('‑', '-')
                            )
                            cleaned_text = cleaned_text.replace('\u202f', ' ').replace('\u00a0', ' ')
                            
                            safe_text = cleaned_text.encode('latin-1', 'replace').decode('latin-1')
                            
                            if not safe_text.strip():
                                pdf.ln(3)
                                continue
                            
                            pdf.set_x(10)
                            
                            if len(safe_text.strip()) < 65 and not safe_text.strip().endswith('.'):
                                pdf.set_font("Arial", "B", 9)
                                pdf.multi_cell(190, 5, safe_text.strip(), new_x="LMARGIN", new_y="NEXT")
                                pdf.set_font("Arial", "", 8)
                            else:
                                pdf.multi_cell(190, 5, safe_text.strip(), new_x="LMARGIN", new_y="NEXT")
                            
                    pdf_output = bytes(pdf.output())

                    st.download_button(
                        label="⬇️ Descargar Reporte en PDF",
                        data=pdf_output,
                        file_name=f"atomum_audit_{last_target}.pdf",
                        mime="application/pdf"
                    )
                except ImportError:
                    st.warning("⚠️ La librería `fpdf2` no está disponible en el entorno.")
            elif export_format == "HTML Interactivo (.html)":
            try:
                # Calcular métricas KPI para el resumen superior
                total_ports_count = len(results)
                high_risks_count = sum(1 for r in results if "ALTO" in r['Riesgo'].upper() or "🔴" in r['Riesgo'])
                med_low_count = total_ports_count - high_risks_count

                # Estructura HTML corporativa avanzada con interactividad JS
                html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reporte de Auditoría ATOMUM: {last_target}</title>
    <style>
        :root {{
            --bg-main: #0d1117;
            --bg-card: #161b22;
            --bg-hover: #21262d;
            --border-color: #30363d;
            --text-main: #c9d1d9;
            --text-muted: #8b949e;
            --accent-blue: #58a6ff;
            --risk-high: #f85149;
            --risk-med: #d29922;
            --risk-low: #3fb950;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg-main);
            color: var(--text-main);
            margin: 0;
            padding: 30px;
            line-height: 1.6;
        }}
        .container {{
            max-width: 1050px;
            margin: auto;
            background: var(--bg-card);
            padding: 40px;
            border-radius: 12px;
            border: 1px solid var(--border-color);
            box-shadow: 0 8px 24px rgba(0,0,0,0.6);
        }}
        header {{
            border-bottom: 2px solid var(--border-color);
            padding-bottom: 20px;
            margin-bottom: 25px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 15px;
        }}
        h1 {{
            color: var(--accent-blue);
            font-size: 26px;
            margin: 0;
        }}
        /* KPI Cards */
        .kpi-container {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }}
        .kpi-card {{
            background: var(--bg-hover);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 15px;
            text-align: center;
        }}
        .kpi-value {{
            font-size: 24px;
            font-weight: bold;
            font-family: monospace;
            color: var(--accent-blue);
            margin-top: 5px;
        }}
        .kpi-value.danger {{ color: var(--risk-high); }}
        .kpi-title {{
            font-size: 12px;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        h2 {{
            color: #7ee787;
            font-size: 18px;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 8px;
            margin-top: 35px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            cursor: pointer;
        }}
        .port-grid {{
            display: grid;
            grid-template-columns: 1fr;
            gap: 12px;
            margin-bottom: 25px;
        }}
        .port-card {{
            background: var(--bg-hover);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 15px 20px;
            display: flex;
            flex-wrap: wrap;
            justify-content: space-between;
            align-items: center;
            transition: border-color 0.2s;
        }}
        .port-card:hover {{
            border-color: var(--accent-blue);
        }}
        .port-badge {{
            font-weight: bold;
            font-family: monospace;
            font-size: 15px;
            color: var(--accent-blue);
        }}
        .risk-tag {{
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
            text-transform: uppercase;
        }}
        .risk-high {{ background: rgba(248, 81, 73, 0.15); color: var(--risk-high); border: 1px solid var(--risk-high); }}
        .risk-med {{ background: rgba(210, 153, 34, 0.15); color: var(--risk-med); border: 1px solid var(--risk-med); }}
        .risk-low {{ background: rgba(63, 185, 80, 0.15); color: var(--risk-low); border: 1px solid var(--risk-low); }}
        
        /* Contenedor IA con Botón de Copiado */
        .ai-wrapper {{
            position: relative;
            margin-top: 15px;
        }}
        .copy-btn {{
            position: absolute;
            top: 12px;
            right: 12px;
            background: #30363d;
            color: var(--text-main);
            border: 1px solid var(--border-color);
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 12px;
            cursor: pointer;
            transition: background 0.2s;
        }}
        .copy-btn:hover {{
            background: var(--accent-blue);
            color: #fff;
        }}
        .ai-report {{
            background: var(--bg-main);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 25px;
            padding-top: 45px;
            white-space: pre-wrap;
            font-size: 13.5px;
            color: #d2d6dc;
            font-family: ui-monospace, SFMono-Regular, SF Mono, Menlo, Consolas, monospace;
            max-height: 600px;
            overflow-y: auto;
        }}
        /* Estilos de Acordeón */
        .collapsible-content {{
            overflow: hidden;
            transition: max-height 0.3s ease-out;
        }}
        footer {{
            margin-top: 45px;
            text-align: center;
            font-size: 12px;
            color: var(--text-muted);
            border-top: 1px solid var(--border-color);
            padding-top: 20px;
        }}
    </style>
    <script>
        function toggleSection(id) {{
            var content = document.getElementById(id);
            if (content.style.maxHeight) {{
                content.style.maxHeight = null;
            }} else {{
                content.style.maxHeight = content.scrollHeight + "px";
            }}
        }}
        function copyAiReport() {{
            var text = document.getElementById("aiReportText").innerText;
            navigator.clipboard.writeText(text).then(function() {{
                var btn = document.getElementById("copyBtn");
                btn.innerText = "¡Copiado! ✅";
                setTimeout(function() {{ btn.innerText = "📋 Copiar Informe"; }}, 2000);
            }});
        }}
    </script>
</head>
<body>
    <div class="container">
        <header>
            <div>
                <h1>🛡️ Reporte de Auditoría ATOMUM</h1>
                <div style="font-size: 14px; color: var(--text-muted); margin-top: 4px;">Objetivo analizado: <strong style="color: var(--accent-blue);">{last_target}</strong></div>
            </div>
            <div style="text-align: right; font-size: 13px; color: var(--text-muted);">
                📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br>
                ⏱️ Tiempo: {elapsed:.2f}s
            </div>
        </header>

        <!-- KPI Cards -->
        <div class="kpi-container">
            <div class="kpi-card">
                <div class="kpi-title">Puertos Abiertos</div>
                <div class="kpi-value">{total_ports_count}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">Hallazgos Críticos (Alto)</div>
                <div class="kpi-value danger">{high_risks_count}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">Riesgo Moderado / Bajo</div>
                <div class="kpi-value">{med_low_count}</div>
            </div>
        </div>

        <h2 onclick="toggleSection('portsSection')">📊 Puertos Abiertos y Hallazgos <span>▼</span></h2>
        <div id="portsSection" class="collapsible-content" style="max-height: 1000px;">
            <div class="port-grid" style="margin-top: 15px;">
"""
                for r in results:
                    risk_val = r['Riesgo']
                    css_risk = "risk-high" if "ALTO" in risk_val.upper() or "🔴" in risk_val else ("risk-med" if "MEDIO" in risk_val.upper() or "🟡" in risk_val else "risk-low")
                    clean_risk_text = risk_val.replace('🔴 ', '').replace('🟡 ', '').replace('🟢 ', '')
                    
                    html_content += f"""                <div class="port-card">
                    <div>
                        <span class="port-badge">Puerto {r['Puerto']} ({r['Servicio']})</span><br>
                        <span style="font-size: 13px; color: var(--text-muted);">SO Estimado: {r['SO Estimado']} | Versión: {r['Banner / Versión']}</span>
                    </div>
                    <div>
                        <span class="risk-tag {css_risk}">{clean_risk_text}</span>
                    </div>
                </div>\n"""

                html_content += """            </div>
        </div>\n"""

                if ai_report_content:
                    html_content += f"""        <h2 onclick="toggleSection('aiSection')" style="margin-top: 25px;">🤖 Informe Ejecutivo y Hardening (Groq AI) <span>▼</span></h2>
        <div id="aiSection" class="collapsible-content" style="max-height: 2000px;">
            <div class="ai-wrapper">
                <button id="copyBtn" class="copy-btn" onclick="copyAiReport()">📋 Copiar Informe</button>
                <div id="aiReportText" class="ai-report">{ai_report_content}</div>
            </div>
        </div>\n"""

                html_content += f"""        <footer>
            ATOMUM Modular Core v2.0 &bull; Motor Activo: Groq Cloud Engine &bull; Auditoría Autónoma de Seguridad
        </footer>
    </div>
</body>
</html>"""

                st.download_button(
                    label="⬇️ Descargar Reporte HTML Corporativo Avanzado (.html)",
                    data=html_content.encode('utf-8'),
                    file_name=f"atomum_audit_{last_target}.html",
                    mime="text/html"
                )
            except Exception as e:
                st.error(f"⚠️ Error generando el reporte HTML corporativo: {e}")
        else:
            st.info("🛡️ No se detectaron puertos abiertos en el rango seleccionado para este objetivo.")

import pathlib
from typing import List, Dict, Any
from docx import Document
from docx.shared import Pt, Inches
import logging

log = logging.getLogger(__name__)

def _add_heading(doc: Document, text: str, level: int = 1):
    heading = doc.add_heading(text, level=level)
    heading.runs[0].font.size = Pt(14 if level == 1 else 12)

def _add_table(doc: Document, findings: List[Dict[str, Any]]):
    """
    Crea una tabla con columnas: ID, Severidad, Archivo, Línea, Descripción, Remediación.
    """
    table = doc.add_table(rows=1, cols=6)
    hdr_cells = table.rows[0].cells
    headers = ["ID", "Severidad", "Archivo", "Línea", "Descripción", "Remediación"]
    for i, h in enumerate(headers):
        hdr_cells[i].text = h
        hdr_cells[i].paragraphs[0].runs[0].font.bold = True

    for f in findings:
        row_cells = table.add_row().cells
        row_cells[0].text = f.get("id", "")
        row_cells[1].text = f.get("severity", "")
        row_cells[2].text = f.get("file", "")
        row_cells[3].text = str(f.get("line", ""))
        row_cells[4].text = f.get("title", "")
        row_cells[5].text = f.get("remediation", "N/A")

def export_security_report_to_word(
    report_json: Dict[str, Any],
    alerts: List[Dict[str, Any]],
    output_path: pathlib.Path,
) -> None:
    """
    Genera un documento .docx con:
    • Resumen ejecutivo (total de hallazgos, críticos, altos, medios, bajos)
    • Tabla detallada de los hallazgos críticos/alto riesgo (incluye remediación)
    • Anexos opcionales (lista completa de hallazgos si se desea).

    Parameters
    ----------
    report_json : dict
        JSON completo devuelto por core.security_analyzer.
    alerts : list[dict]
        Subconjunto filtrado por severidad (CRITICAL/HIGH) ya enriquecido.
    output_path : pathlib.Path
        Ruta destino del archivo .docx.
    """
    doc = Document()

    # ------------------------------------------------------------------
    # Portada / Título
    # ------------------------------------------------------------------
    doc.add_heading("Informe de Seguridad – Análisis Automático", level=0)
    doc.add_paragraph(f"Fecha de generación: {output_path.stem.split('_')[-1]}")
    doc.add_page_break()

    # ------------------------------------------------------------------
    # Resumen ejecutivo
    # ------------------------------------------------------------------
    total = sum(len(entry.get("issues", [])) for entry in report_json.get("results", []))
    severity_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for entry in report_json.get("results", []):
        for issue in entry.get("issues", []):
            sev = issue.get("severity", "LOW")
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

    _add_heading(doc, "Resumen Ejecutivo", level=1)
    doc.add_paragraph(f"Total de hallazgos detectados: {total}")
    for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        doc.add_paragraph(f"- {sev}: {severity_counts.get(sev,0)}")

    # ------------------------------------------------------------------
    # Tabla de alertas críticas/alto riesgo
    # ------------------------------------------------------------------
    if alerts:
        _add_heading(doc, "Hallazgos Críticos / Alto Riesgo", level=2)
        _add_table(doc, alerts)
    else:
        doc.add_paragraph("No se encontraron vulnerabilidades críticas ni de alto riesgo.")

    # ------------------------------------------------------------------
    # Anexo completo (opcional)
    # ------------------------------------------------------------------
    _add_heading(doc, "Anexo – Lista completa de hallazgos", level=2)
    for entry in report_json.get("results", []):
        file_path = entry.get("file", "")
        for issue in entry.get("issues", []):
            p = doc.add_paragraph()
            p.add_run(f"[{issue.get('severity')}] {issue.get('id')} – ").bold = True
            p.add_run(f"{issue.get('title')} (Archivo: {file_path})")

    # ------------------------------------------------------------------
    # Guardar documento
    # ------------------------------------------------------------------
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
    log.info(f"Documento Word exportado a {output_path}")

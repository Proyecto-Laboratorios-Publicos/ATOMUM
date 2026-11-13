# utils/exporter.py
import json
from pathlib import Path
from typing import Union, Dict, Any, List

import markdown2  # opcional, solo si se procesa Markdown → HTML
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.enum.style import WD_STYLE_TYPE


def _add_heading(doc: Document, text: str, level: int = 1):
    """Añade un encabezado con estilo jerárquico."""
    heading = doc.add_heading(text, level=level)
    # Opcional: aplicar fuente uniforme
    for run in heading.runs:
        run.font.name = "Calibri"
        run.font.size = Pt(14 - level)  # disminuye ligeramente con la profundidad


def _add_paragraph(doc: Document, text: str):
    """Párrafo simple con justificación completa."""
    p = doc.add_paragraph(text)
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    for run in p.runs:
        run.font.name = "Calibri"
        run.font.size = Pt(11)


def _add_table(doc: Document, headers: List[str], rows: List[List[Any]]):
    """Crea tabla con manejo seguro de celdas para evitar desbordamientos."""
    cols = len(headers)
    table = doc.add_table(rows=1, cols=cols)
    table.style = "Table Grid"

    hdr_cells = table.rows[0].cells
    for i, header in enumerate(headers):
        if i < len(hdr_cells):
            hdr_cells[i].text = str(header)
            if hdr_cells[i].paragraphs and hdr_cells[i].paragraphs[0].runs:
                hdr_cells[i].paragraphs[0].runs[0].font.bold = True

    for row in rows:
        row_cells = table.add_row().cells
        for i, cell in enumerate(row):
            if i < len(row_cells):
                row_cells[i].text = str(cell)


def _process_markdown(doc: Document, md_text: str):
    """
    Convierte Markdown a bloques docx.
    Se usa markdown2 → HTML → parsing manual (simple).
    Para casos complejos (listas anidadas, código) se recomienda pandoc.
    """
    html = markdown2.markdown(md_text, extras=["tables", "fenced-code-blocks"])

    # Utilizamos BeautifulSoup para extraer la estructura HTML.
    from bs4 import BeautifulSoup  # bs4 está en la mayoría de los entornos; si no, añadir a requirements

    soup = BeautifulSoup(html, "html.parser")

    for element in soup.children:
        if element.name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            level = int(element.name[1])
            _add_heading(doc, element.get_text(), level=level)
        elif element.name == "p":
            _add_paragraph(doc, element.get_text())
        elif element.name == "ul":
            for li in element.find_all("li", recursive=False):
                _add_paragraph(doc, f"• {li.get_text()}")
        elif element.name == "ol":
            for idx, li in enumerate(element.find_all("li", recursive=False), start=1):
                _add_paragraph(doc, f"{idx}. {li.get_text()}")
        elif element.name == "table":
            # Extraer encabezados y filas
            headers = [th.get_text() for th in element.find_all("th")]
            rows = [
                [td.get_text() for td in tr.find_all("td")]
                for tr in element.find_all("tr")[1:]  # saltar la fila de encabezado
            ]
            _add_table(doc, headers, rows)
        # Se pueden añadir más casos (blockquote, code, img, etc.) según necesidad.


def export_to_docx(
    source: Union[str, Dict[str, Any]],
    output_path: Union[str, Path],
    *,
    title: str = "Informe ATOMUM",
    author: str = "ATOMUM",
    markdown: bool = True,
) -> Path:
    # Normalizar ruta
    output_path = Path(output_path).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Crear documento base
    doc = Document()
    # Metadatos básicos
    core_props = doc.core_properties
    core_props.title = title
    core_props.author = author

    # Título principal del informe
    _add_heading(doc, title, level=0)

    # -------------------------------------------------
    # 1️⃣ Procesar entrada
    # -------------------------------------------------
    if isinstance(source, dict):
        # Estructura JSON esperada:
        # {
        #   "title": "Título opcional",
        #   "sections": [
        #       {"heading": "Sección 1", "content": "Texto libre", "tables": [...]},
        #       ...
        #   ]
        # }
        if "title" in source:
            _add_heading(doc, source["title"], level=1)

        for sec in source.get("sections", []):
            heading = sec.get("heading")
            if heading:
                _add_heading(doc, heading, level=2)

            content = sec.get("content")
            if content:
                if markdown:
                    _process_markdown(doc, content)
                else:
                    _add_paragraph(doc, content)

            # Tablas opcionales
            for tbl in sec.get("tables", []):
                # tbl = {"headers": [...], "rows": [[...], [...]]}
                _add_table(doc, tbl.get("headers", []), tbl.get("rows", []))

    elif isinstance(source, str):
        # Texto plano o Markdown
        if markdown:
            _process_markdown(doc, source)
        else:
            _add_paragraph(doc, source)

    else:
        raise TypeError("source must be str or dict")

    # -------------------------------------------------
    # 2️⃣ Guardar archivo
    # -------------------------------------------------
    doc.save(str(output_path))
    return output_path

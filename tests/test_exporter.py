# tests/test_exporter.py
import tempfile
from pathlib import Path
from utils.exporter import export_to_docx

def test_export_markdown():
    md = "# Título de Prueba\n\nEste es un párrafo de validación.\n\n| Col A | Col B |\n|---|---|\n| 1 | 2 |\n"
    with tempfile.TemporaryDirectory() as td:
        out = export_to_docx(md, Path(td) / "test.docx")
        assert out.exists()

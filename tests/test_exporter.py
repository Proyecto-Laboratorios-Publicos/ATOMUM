import zipfile
from pathlib import Path

from utils.exporter import export_to_docx


def test_export_markdown(tmp_path: Path) -> None:
    md = (
        "# Título de Prueba\n\n"
        "Este es un párrafo de validación.\n\n"
        "| Col A | Col B |\n"
        "|---|---|\n"
        "| 1 | 2 |\n"
    )
    target_path = tmp_path / "test.docx"
    out = export_to_docx(md, target_path)

    assert Path(out).exists()
    assert Path(out).stat().st_size > 0
    assert zipfile.is_zipfile(out)


def test_export_empty_markdown_creates_non_empty_docx(tmp_path: Path) -> None:
    target_path = tmp_path / "empty.docx"
    out = export_to_docx("", target_path)

    assert Path(out).exists()
    assert Path(out).stat().st_size > 0

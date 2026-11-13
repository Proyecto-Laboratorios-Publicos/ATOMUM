from pathlib import Path
from typing import Union, Dict, Any

def export_to_docx(
    source: Union[str, Dict[str, Any]],
    output_path: Union[str, Path],
    *,
    title: str = "Informe ATOMUM",
    author: str = "ATOMUM",
    markdown: bool = True,
) -> Path:
    """
    Convierte contenido Markdown o JSON estructurado a un archivo .docx.

    Parámetros
    ----------
    source : str | dict
        - Si es `str` y `markdown=True` → se interpreta como Markdown.
        - Si es `str` y `markdown=False` → se interpreta como texto plano.
        - Si es `dict` → estructura JSON con claves: `title`, `sections`, `tables`.
    output_path : str | Path
        Ruta completa donde se guardará el .docx.
    title : str, opcional
        Título del documento (se inserta como encabezado de nivel 0).
    author : str, opcional
        Metadato de autor.
    markdown : bool, opcional
        Indica si `source` es Markdown (solo cuando `source` es str).

    Returns
    -------
    Path
        Ruta absoluta del archivo generado.
    """
    ...

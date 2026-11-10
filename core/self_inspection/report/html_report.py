from pathlib import Path

class HtmlReport:
    """Genera una vista visual e interactiva en HTML del reporte de auto-inspección."""
    def __init__(self, result) -> None:
        self.result = result

    def write(self, path: Path) -> None:
        issues_html = "".join(
            f"<li><b>{i.file}</b> [Línea {i.line}]: [{i.code}] {i.message} (Severidad: {i.severity})</li>"
            for i in self.result.issues
        ) or "<li>No se detectaron problemas críticos. ¡Excelente trabajo!</li>"

        html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>ATOMUM - Reporte de Auto-Inspección</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #f8fafc; padding: 40px; }}
        h1 {{ color: #38bdf8; }}
        ul {{ background: #1e293b; padding: 20px; border-radius: 8px; list-style-type: none; }}
        li {{ padding: 8px 0; border-bottom: 1px solid #334155; }}
    </style>
</head>
<body>
    <h1>🤖 ATOMUM: Reporte de Auditoría Interna</h1>
    <p>Resultados del análisis estático y generación de parches del núcleo cognitivo.</p>
    <h2>Issues Detectados:</h2>
    <ul>
        {issues_html}
    </ul>
</body>
</html>
"""
        path.write_text(html_content, encoding='utf-8')

from pathlib import Path
from .analyzer import SelfInspectionAnalyzer
from .report.json_report import JsonReport
from .report.html_report import HtmlReport

class SelfInspectionService:
    """Punto de entrada único del subsistema de autoinspección de ATOMUM."""
    def __init__(self, repo_root: Path = Path.cwd()) -> None:
        self.repo_root = repo_root
        self.analyzer = SelfInspectionAnalyzer(repo_root)

    def run(self, paths: list[Path] | None = None, *, output_dir: Path = Path('self_inspection_reports')):
        if paths is None:
            paths = [p for p in self.repo_root.rglob('*.py') if p.is_file() and 'self_inspection' not in p.parts]
            
        result = self.analyzer.inspect(paths)
        
        output_dir.mkdir(parents=True, exist_ok=True)
        JsonReport(result).write(output_dir / 'report.json')
        HtmlReport(result).write(output_dir / 'report.html')
        
        return result

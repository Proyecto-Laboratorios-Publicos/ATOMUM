import ast
from pathlib import Path
from collections import namedtuple
from .loader import SourceLoader
from .rules import load_all_rules

Issue = namedtuple('Issue', ['file', 'line', 'col', 'code', 'message', 'severity'])
InspectionResult = namedtuple('InspectionResult', ['issues'])

class SelfInspectionAnalyzer:
    """Orquesta la lectura y el análisis estático de los archivos del repositorio."""
    def __init__(self, repo_root: Path = Path.cwd()) -> None:
        self.repo_root = repo_root
        self.loader = SourceLoader(repo_root)
        self.rules = load_all_rules()

    def inspect(self, files: list[Path]) -> InspectionResult:
        issues = []
        for file_path in files:
            try:
                source = self.loader.read(file_path)
                tree = ast.parse(source, filename=str(file_path))
                
                # Ejecutar cada regla sobre el árbol AST del archivo
                for rule in self.rules:
                    rule_issues = rule.run(tree, source, file_path)
                    issues.extend(rule_issues)
            except Exception as e:
                print(f"❌ [Analyzer Error] Fallo al inspeccionar {file_path}: {e}")
                
        return InspectionResult(issues=issues)

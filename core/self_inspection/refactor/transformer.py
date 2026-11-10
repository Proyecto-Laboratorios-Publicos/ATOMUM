import libcst as cst
from pathlib import Path
from core.self_inspection.rules.base import BaseRule

class RefactorEngine:
    """
    Aplica transformaciones declaradas por reglas que lo soporten.
    Utiliza LibCST para preservar la estructura y el formato original del código.
    """
    def apply(self, source: str, file_path: Path, rules: list[BaseRule]) -> str:
        try:
            module = cst.parse_module(source)
            for rule in rules:
                if hasattr(rule, "suggest_transform"):
                    transformer = rule.suggest_transform()
                    module = module.visit(transformer)
            return module.code
        except Exception as e:
            print(f"❌ [RefactorEngine Error] Fallo al transformar {file_path}: {e}")
            return source

import ast
import re
from pathlib import Path
from .base import BaseRule, Issue

class HardcodedSecretRule(BaseRule):
    code = "SEC001"
    description = "Hard-coded secret strings (API keys, passwords)."
    severity = "warning"
    
    SECRET_PATTERN = re.compile(
        r'(?i)(api[_-]?key|secret|token)[\'"]?\s*[:=]\s*[\'"][A-Za-z0-9\-_]{20,}[\'"]'
    )

    def run(self, tree: ast.AST, source: str, file_path: Path) -> list[Issue]:
        issues = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                if self.SECRET_PATTERN.search(node.value.value):
                    issues.append(
                        Issue(
                            file=file_path,
                            line=node.lineno,
                            col=node.col_offset,
                            code=self.code,
                            message=self.description,
                            severity=self.severity
                        )
                    )
        return issues

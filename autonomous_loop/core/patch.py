"""
patch.py
--------
PatchProposal y PatchBuilder: Gestionan la transformación de los diffs
propuestos por el motor cognitivo en estructuras AST analizables.
"""

import ast
import pathlib
import tempfile
from typing import Dict, Any

class PatchProposal:
    def __init__(self, proposal_id: str, diff_content: str, diff_path: pathlib.Path, ast_trees: Dict[str, ast.AST]):
        self.id = proposal_id
        self.diff_content = diff_content
        self.diff_path = diff_path
        self.ast_trees = ast_trees

class PatchBuilder:
    def __init__(self, raw_diff: str, goal):
        self.raw_diff = raw_diff
        self.goal = goal

    def build(self) -> PatchProposal:
        """Construye un archivo temporal con el diff y parsea los árboles AST afectados."""
        # Crear archivo temporal para el diff
        fd, path = tempfile.mkstemp(suffix=".diff", prefix="atomum_patch_")
        diff_path = pathlib.Path(path)
        
        with open(fd, "w", encoding="utf-8") as f:
            f.write(self.raw_diff)

        # Parsear los archivos afectados a AST para validación estática
        ast_trees = {}
        for file_path in self.goal.context_files:
            try:
                full_path = pathlib.Path(file_path)
                if full_path.exists():
                    source_code = full_path.read_text(encoding="utf-8")
                    ast_trees[file_path] = ast.parse(source_code, filename=file_path)
            except Exception as e:
                # Si no se puede parsear, se registra un árbol vacío o se maneja el error
                ast_trees[file_path] = ast.parse("pass", filename=file_path)

        proposal_id = f"proposal-{abs(hash(self.raw_diff)) % 10000:04d}"
        return PatchProposal(
            proposal_id=proposal_id,
            diff_content=self.raw_diff,
            diff_path=diff_path,
            ast_trees=ast_trees
        )

import difflib
from pathlib import Path

class DiffBuilder:
    """Genera diferencias en formato unificado (Unified Diff) entre el código original y el refactorizado."""
    def unified_diff(self, original: str, modified: str, file_path: Path) -> str:
        orig_lines = original.splitlines(keepends=True)
        mod_lines = modified.splitlines(keepends=True)
        
        diff = difflib.unified_diff(
            orig_lines,
            mod_lines,
            fromfile=str(file_path),
            tofile=str(file_path) + ".refactored",
            lineterm=''
        )
        return ''.join(diff)

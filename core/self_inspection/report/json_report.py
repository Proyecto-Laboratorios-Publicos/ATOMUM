import json
from pathlib import Path

class JsonReport:
    """Genera un reporte estructurado en formato JSON con los problemas e issues detectados."""
    def __init__(self, result) -> None:
        self.result = result

    def write(self, path: Path) -> None:
        data = {
            "issues": [i._asdict() for i in self.result.issues],
            "patches": [p._asdict() for p in self.result.patches],
        }
        path.write_text(json.dumps(data, indent=2), encoding='utf-8')

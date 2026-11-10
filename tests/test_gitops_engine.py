import json
import pytest
from pathlib import Path
from core.gitops_engine import load_improvement, generate_branch_name

@pytest.fixture
def sample_improvement(tmp_path: Path) -> Path:
    data = {
        "ticket_id": "AT-1234",
        "title": "Optimizar algoritmo de cálculo",
        "description": "Se reduce la complejidad.",
        "type": "performance"
    }
    f = tmp_path / "improvement.json"
    f.write_text(json.dumps(data))
    return f

def test_load_improvement(sample_improvement: Path):
    imp = load_improvement(sample_improvement)
    assert imp["ticket_id"] == "AT-1234"
    assert imp["type"] == "performance"

def test_generate_branch_name():
    imp = {"ticket_id": "AT-9999", "title": "Actualizar dependencias críticas"}
    branch = generate_branch_name(imp)
    assert branch.startswith("improve/AT-9999/actualizar-dependencias")
    assert len(branch.split("-")[-1]) == 8

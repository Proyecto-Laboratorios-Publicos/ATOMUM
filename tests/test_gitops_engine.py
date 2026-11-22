import json
from pathlib import Path

import pytest

from core.gitops_engine import generate_branch_name, load_improvement


@pytest.fixture
def sample_improvement(tmp_path: Path) -> Path:
    data = {
        "ticket_id": "AT-1234",
        "title": "Optimizar algoritmo de cálculo",
        "description": "Se reduce la complejidad.",
        "type": "performance",
    }
    f = tmp_path / "improvement.json"
    f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return f


def test_load_improvement(sample_improvement: Path) -> None:
    imp = load_improvement(sample_improvement)
    assert imp["ticket_id"] == "AT-1234"
    assert imp["type"] == "performance"
    assert imp["title"] == "Optimizar algoritmo de cálculo"


def test_generate_branch_name() -> None:
    imp = {
        "ticket_id": "AT-9999",
        "title": "Actualizar dependencias críticas",
    }
    branch = generate_branch_name(imp)
    assert branch.startswith("improve/AT-9999/actualizar-dependencias")
    assert len(branch.split("-")[-1]) == 8


def test_load_improvement_missing_file_raises(tmp_path: Path) -> None:
    missing = tmp_path / "no_existe.json"
    with pytest.raises((FileNotFoundError, json.JSONDecodeError, OSError)):
        load_improvement(missing)

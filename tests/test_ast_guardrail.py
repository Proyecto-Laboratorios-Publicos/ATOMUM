"""
test_ast_guardrail.py
---------------------
Pruebas unitarias para validar los guardarraíles de AST y rechazo de nodos prohibidos.
"""

import ast
import pytest
from core.validator import ASTValidator

def test_allowed_nodes():
    source_code = "a = 1\nprint(a)"
    validator = ASTValidator(source_code)
    assert validator.is_valid() is True

def test_forbidden_calls():
    # Intento de inyección de código prohibido
    source_code = "import os\nos.system('echo hacked')"
    validator = ASTValidator(source_code)
    # Como os.system está en la lista de llamadas prohibidas, debe invalidarlo
    assert validator.is_valid() is False

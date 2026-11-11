"""
Suite de Pruebas Unitarias de Seguridad para ATOMUM.
Valida el funcionamiento del logger, los guardarraíses AST y el motor.
"""

import pytest
import logging
from core.logger import get_logger, SecretMaskFilter
from core.guardrails import validate_user_code, GuardrailViolation, Guardrails
from core.engine import AtomumEngine

def test_logger_secret_masking():
    """Verifica que el logger enmascare correctamente las claves sensibles."""
    filter_obj = SecretMaskFilter()
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="Conectando con api_key=secret_groq_xyz123 usando password=supersecret",
        args=(), exc_info=None
    )
    assert filter_obj.filter(record) is True
    assert "secret_groq_xyz123" not in record.msg
    assert "supersecret" not in record.msg
    assert "api_key=***" in record.msg
    assert "password=***" in record.msg

def test_guardrails_ast_blocking():
    """Verifica que el AST bloquee importaciones prohibidas y funciones peligrosas."""
    # Código malicioso prohibido
    malicious_code = "import os; os.system('ls')"
    with pytest.raises(GuardrailViolation):
        validate_user_code(malicious_code)

    # Código seguro permitido
    safe_code = "result = 2 + 2"
    # No debe lanzar excepción
    validate_user_code(safe_code)

def test_guardrails_text_validation():
    """Verifica que los comandos destructivos de consola sean bloqueados."""
    g = Guardrails()
    assert g.validate_action("analiza el repositorio") is True
    assert g.validate_action("rm -rf /") is False

def test_engine_initialization():
    """Verifica que el motor se inicialice correctamente en modo local o con config."""
    engine = AtomumEngine(concurrency_limit=5)
    assert engine.is_active is True
    assert engine.guardrails is not None

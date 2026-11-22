"""
Suite de Pruebas Unitarias de Seguridad para ATOMUM.
Valida el funcionamiento del logger, los guardarraíses AST y el motor.
"""

import logging
import pytest

from core.engine import AtomumEngine
from core.guardrails import Guardrails, GuardrailViolation, validate_user_code
from core.logger import SecretMaskFilter, get_logger


def test_logger_secret_masking():
    """Verifica que el logger y el filtro enmascaren correctamente las claves sensibles."""
    filter_obj = SecretMaskFilter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Conectando con api_key=secret_groq_xyz123 usando password=supersecret",
        args=(),
        exc_info=None,
    )
    assert filter_obj.filter(record) is True
    assert "secret_groq_xyz123" not in record.msg
    assert "supersecret" not in record.msg
    assert "api_key=***" in record.msg
    assert "password=***" in record.msg

    logger = get_logger("atomum.test.security")
    assert isinstance(logger, logging.Logger)


def test_guardrails_ast_blocking():
    """Verifica que el AST bloquee importaciones prohibidas y funciones peligrosas."""
    malicious_code = "import os; os.system('ls')"
    with pytest.raises(GuardrailViolation):
        validate_user_code(malicious_code)

    safe_code = "result = 2 + 2"
    validate_user_code(safe_code)


def test_guardrails_text_validation():
    """Verifica que los comandos destructivos de consola sean bloqueados."""
    g = Guardrails()
    assert g.validate_action("analiza el repositorio") is True
    assert g.validate_action("rm -rf /") is False


def test_engine_initialization():
    """Verifica que el motor se inicialice correctamente con los parámetros esperados."""
    engine = AtomumEngine(concurrency_limit=5)
    assert engine.is_active is True
    assert engine.guardrails is not None

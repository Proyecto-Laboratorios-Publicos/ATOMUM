from __future__ import annotations
from datetime import datetime
from unittest.mock import MagicMock
from memory.episodic.context_manager import EpisodicMemoryContextManager
from autonomous_loop.memory.episodic.store import EpisodicMemoryStore
from autonomous_loop.memory.episodic.models import EpisodicEvent

def test_log_action_success():
    """Verifica que se registre una acción exitosamente."""
    mock_store = MagicMock(spec=EpisodicMemoryStore)
    mock_store.save_event.return_value = True
    
    manager = EpisodicMemoryContextManager(store=mock_store)
    
    result = manager.log_action(
        agent_role="threat_intel",
        action="scan_ports",
        inputs={"target": "192.168.1.50"},
        outputs={"open_ports": [80, 443]},
        result_status="success"
    )
    
    assert result is True
    # Verificamos que se haya llamado a save_event
    mock_store.save_event.assert_called_once()

def test_get_recent_context():
    """Verifica la recuperación de los eventos más recientes."""
    mock_store = MagicMock(spec=EpisodicMemoryStore)
    
    event = EpisodicEvent(
        agent_role="critic",
        action="review_critical",
        inputs={},
        outputs={},
        result_status="accept"
    )
    mock_store.query_events.return_value = [event]
    
    manager = EpisodicMemoryContextManager(store=mock_store)
    context = manager.get_recent_context(limit=5)
    
    assert len(context) == 1
    assert context[0].agent_role == "critic"
    mock_store.query_events.assert_called_once_with(limit=5)

def test_get_agent_history():
    """Verifica la recuperación del historial de un agente específico."""
    mock_store = MagicMock(spec=EpisodicMemoryStore)
    
    event = EpisodicEvent(
        agent_role="coder",
        action="patch_proposal",
        inputs={},
        outputs={},
        result_status="success"
    )
    mock_store.query_events.return_value = [event]
    
    manager = EpisodicMemoryContextManager(store=mock_store)
    history = manager.get_agent_history(agent_role="coder", limit=10)
    
    assert len(history) == 1
    assert history[0].agent_role == "coder"
    mock_store.query_events.assert_called_once_with(agent_role="coder", limit=10)

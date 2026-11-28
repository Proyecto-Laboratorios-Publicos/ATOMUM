from core.governance import GovernanceController, ScopePolicy
from memory.procedural.procedural_memory_manager import ProceduralMemoryManager
from memory.procedural.store import ProceduralMemoryStore
from memory.procedural.playbook import Playbook, PlaybookStep
from unittest.mock import patch
from datetime import datetime, timezone

@patch('memory.procedural.store.psycopg2.connect')
@patch('memory.procedural.store.redis.Redis')
def test_procedural_memory_manager_integration(mock_redis_class, mock_db_connect):
    # Configurar mock de Redis para simular cache miss
    mock_redis = mock_redis_class.return_value
    mock_redis.get.return_value = None
    
    # Configurar mock de base de datos para simular playbook existente
    mock_conn = mock_db_connect.return_value
    mock_cursor = mock_conn.cursor.return_value
    
    # Primera llamada a fetchone devuelve el playbook directamente
    mock_now = datetime.now(timezone.utc)
    mock_cursor.fetchone.return_value = (
        "PB-001",
        "Host Isolation Playbook",
        "Standard procedure to isolate a compromised host.",
        "Contención",
        [{"step_id": "STEP-1", "action": "isolate_host", "description": "Isolate the affected host from the network.", "expected_outcome": "Host isolated."}],
        ["security", "incident-response"],
        mock_now
    )
    
    # Inicializar controlador de gobernanza base
    policy = ScopePolicy()
    governance = GovernanceController(policy)
    
    # Inicializar componentes de memoria procedimental
    store = ProceduralMemoryStore()
    memory_manager = ProceduralMemoryManager(store)
    
    # Crear un playbook de ejemplo
    step1 = PlaybookStep(
        step_id="STEP-1",
        action="isolate_host",
        description="Isolate the affected host from the network.",
        expected_outcome="Host isolated."
    )
    playbook = Playbook(
        playbook_id="PB-001",
        title="Host Isolation Playbook",
        description="Standard procedure to isolate a compromised host.",
        category="Contención",
        steps=[step1],
        tags=["security", "incident-response"]
    )
    
    # Probar guardado y recuperación
    memory_manager.save_playbook(playbook)
    retrieved_playbook = memory_manager.get_playbook("PB-001")
    
    assert retrieved_playbook is not None
    assert retrieved_playbook.playbook_id == "PB-001"
    assert retrieved_playbook.title == "Host Isolation Playbook"
    assert len(retrieved_playbook.steps) == 1
    assert retrieved_playbook.steps[0].step_id == "STEP-1"

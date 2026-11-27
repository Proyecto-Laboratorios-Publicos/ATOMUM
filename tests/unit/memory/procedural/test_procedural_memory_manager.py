from core.governance import GovernanceController, ScopePolicy
from memory.procedural.procedural_memory_manager import ProceduralMemoryManager
from memory.procedural.store import ProceduralMemoryStore
from memory.procedural.playbook import Playbook, PlaybookStep
from unittest.mock import patch

@patch('memory.procedural.store.redis.Redis')
def test_procedural_memory_manager_integration(mock_redis_class):
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

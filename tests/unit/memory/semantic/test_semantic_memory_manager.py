from core.governance import GovernanceController, ScopePolicy
from memory.semantic.semantic_memory_manager import SemanticMemoryManager
from memory.semantic.threat_intel import ThreatIntelligence
from memory.semantic.compliance import SecurityPolicy
from memory.semantic.assets import Asset
from memory.semantic.incident_lessons import LessonLearned

def test_semantic_memory_manager_integration():
    # Inicializar controlador de gobernanza base
    policy = ScopePolicy()
    governance = GovernanceController(policy)
    
    # Inicializar administrador de memoria semántica
    memory_manager = SemanticMemoryManager(governance)
    
    # 1. Probar registro y recuperación de amenazas
    threat = ThreatIntelligence(
        threat_id="THREAT-001",
        name="Ransomware Prototype",
        actors=["APT-Group"],
        malware_families=["CryptoBlocker"]
    )
    memory_manager.add_threat(threat)
    retrieved_threat = memory_manager.get_threat("THREAT-001")
    assert retrieved_threat is not None
    assert retrieved_threat.name == "Ransomware Prototype"
    assert "APT-Group" in retrieved_threat.actors
    
    # 2. Probar registro y recuperación de políticas
    policy_doc = SecurityPolicy(
        policy_id="POL-001",
        title="Data Encryption Standard",
        description="Requires AES-256 for all at-rest data.",
        category="Encryption"
    )
    memory_manager.add_policy(policy_doc)
    retrieved_policy = memory_manager.get_policy("POL-001")
    assert retrieved_policy is not None
    assert retrieved_policy.title == "Data Encryption Standard"
    
    # 3. Probar registro y recuperación de activos
    asset = Asset(
        asset_id="ASSET-100",
        name="Production-DB",
        type="Database",
        criticality=5
    )
    memory_manager.register_asset(asset)
    retrieved_asset = memory_manager.get_asset("ASSET-100")
    assert retrieved_asset is not None
    assert retrieved_asset.name == "Production-DB"
    assert retrieved_asset.criticality == 5
    
    # 4. Probar registro y recuperación de lecciones aprendidas
    lesson = LessonLearned(
        lesson_id="LESSON-55",
        category="Incident Response",
        finding="Log truncation caused visibility gap.",
        recommendation="Implement real-time centralized logging.",
        preventive_measure="Configured alerts for log agent failure."
    )
    memory_manager.log_lesson(lesson)
    all_lessons = memory_manager.get_all_lessons()
    assert len(all_lessons) == 1
    assert all_lessons[0].lesson_id == "LESSON-55"
    assert all_lessons[0].finding == "Log truncation caused visibility gap."

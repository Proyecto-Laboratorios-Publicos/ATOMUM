from typing import Dict, List, Optional
from core.governance import GovernanceController
from memory.semantic.threat_intel import ThreatIntelligence
from memory.semantic.compliance import SecurityPolicy
from memory.semantic.assets import Asset
from memory.semantic.incident_lessons import LessonLearned

class SemanticMemoryManager:
    """Administrador central para la gestión y recuperación de la memoria semántica."""

    def __init__(self, governance: GovernanceController):
        self.governance = governance
        self._threat_intelligence: Dict[str, ThreatIntelligence] = {}
        self._compliance_policies: Dict[str, SecurityPolicy] = {}
        self._assets: Dict[str, Asset] = {}
        self._incident_lessons: Dict[str, LessonLearned] = {}

    def add_threat(self, threat: ThreatIntelligence) -> None:
        """Registra una nueva inteligencia de amenazas."""
        self._threat_intelligence[threat.threat_id] = threat

    def get_threat(self, threat_id: str) -> Optional[ThreatIntelligence]:
        """Recupera una inteligencia de amenazas."""
        return self._threat_intelligence.get(threat_id)

    def add_policy(self, policy: SecurityPolicy) -> None:
        """Registra una nueva política de seguridad."""
        self._compliance_policies[policy.policy_id] = policy

    def get_policy(self, policy_id: str) -> Optional[SecurityPolicy]:
        """Recupera una política de seguridad."""
        return self._compliance_policies.get(policy_id)

    def register_asset(self, asset: Asset) -> None:
        """Registra un nuevo activo."""
        self._assets[asset.asset_id] = asset

    def get_asset(self, asset_id: str) -> Optional[Asset]:
        """Recupera un activo registrado."""
        return self._assets.get(asset_id)

    def log_lesson(self, lesson: LessonLearned) -> None:
        """Registra una nueva lección aprendida."""
        self._incident_lessons[lesson.lesson_id] = lesson

    def get_all_lessons(self) -> List[LessonLearned]:
        """Recupera todas las lecciones aprendidas."""
        return list(self._incident_lessons.values())

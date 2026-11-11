"""
decision.py
-----------
AcceptancePolicy: Evalúa si un parche cumple con los estándares mínimos
de calidad y seguridad antes de permitir su commit en el repositorio.
"""

from dataclasses import dataclass

@dataclass
class AcceptanceCriteria:
    min_pass_rate: float = 1.0  # 100% de tests aprobados por defecto
    min_coverage_gain: float = 0.0

class AcceptancePolicy:
    def __init__(self, criteria: AcceptanceCriteria = None):
        self.criteria = criteria or AcceptanceCriteria()

    def accept(self, feedback) -> bool:
        """Determina si el parche es apto para integrarse al repositorio."""
        if feedback.status != "completed":
            return False
        if feedback.tests_failed > 0:
            return False
        
        total_tests = feedback.tests_passed + feedback.tests_failed
        if total_tests > 0:
            pass_rate = feedback.tests_passed / total_tests
            if pass_rate < self.criteria.min_pass_rate:
                return False
                
        if feedback.coverage_delta < self.criteria.min_coverage_gain:
            return False
            
        return True

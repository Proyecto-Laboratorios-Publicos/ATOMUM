"""
feedback.py
-----------
FeedbackCollector: Procesa los resultados del sandbox y genera un resumen
estructurado para la política de decisión y el motor cognitivo.
"""

class FeedbackCollector:
    def __init__(self, test_result: dict):
        self.status = test_result.get("status", "unknown")
        self.tests_passed = test_result.get("tests_passed", 0)
        self.tests_failed = test_result.get("tests_failed", 0)
        self.coverage_delta = test_result.get("coverage_delta", 0.0)
        self.runtime_ms = test_result.get("runtime_ms", 0.0)
        self.raw_output = test_result.get("raw_output", "")

    def summary(self) -> str:
        return f"Status: {self.status} | Passed: {self.tests_passed} | Failed: {self.tests_failed} | Coverage Delta: {self.coverage_delta}%"

    def to_markdown(self) -> str:
        return f"""### 📊 Feedback de Ejecución Autónoma
- **Estado:** {self.status}
- **Tests Exitosos:** {self.tests_passed}
- **Tests Fallidos:** {self.tests_failed}
- **Variación de Cobertura:** {self.coverage_delta}%
- **Tiempo de Ejecución:** {self.runtime_ms} ms
"""

import pytest

from atomum.context.stub_context import StubContextStore
from atomum.inference.stub_inference import StubInferenceClient
from atomum.planning.stub_planning import StubPlanner
from atomum.runner.main import AtomumRunner


@pytest.mark.asyncio
@pytest.mark.integration
async def test_full_mission_with_stubs() -> None:
    runner = AtomumRunner()
    # Inyectamos los stubs para aislar la prueba de la red y de servicios externos
    runner.inference_service = StubInferenceClient()
    runner.context_service = StubContextStore()
    runner.planning_service = StubPlanner()

    goal = "Validar flujo modular completo"
    result = await runner.execute_mission(goal)

    assert result["status"] == "planned"
    assert len(result["plan"]) == 2
    assert result["plan"][0]["action"] == "stub_analyze"

    saved_goal = await runner.context_service.get("current_goal")
    assert saved_goal == goal

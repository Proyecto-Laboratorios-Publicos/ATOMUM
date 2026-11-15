import pytest
from atomum.runner.main import AtomumRunner
from atomum.inference.stub_inference import StubInferenceClient
from atomum.context.stub_context import StubContextStore
from atomum.planning.stub_planning import StubPlanner

@pytest.mark.asyncio
@pytest.mark.integration
async def test_full_mission_with_stubs():
    runner = AtomumRunner()
    # Inyectamos los stubs para aislar la prueba de la red
    runner.inference_service = StubInferenceClient()
    runner.context_service = StubContextStore()
    runner.planning_service = StubPlanner()

    result = await runner.execute_mission("Validar flujo modular completo")
    
    assert result["status"] == "planned"
    assert len(result["plan"]) == 2
    saved_goal = await runner.context_service.get("current_goal")
    assert saved_goal == "Validar flujo modular completo"

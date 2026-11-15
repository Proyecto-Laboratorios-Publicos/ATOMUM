import pytest
from atomum.inference.stub_inference import StubInferenceClient
from atomum.context.stub_context import StubContextStore
from atomum.planning.stub_planning import StubPlanner

@pytest.mark.asyncio
async def test_stub_inference():
    client = StubInferenceClient()
    res = await client.run("llama3-70b-8192", {"messages": [{"role": "user", "content": "Hola Atomum"}]})
    assert res["status"] == "success"
    assert "Hola Atomum" in res["content"]

@pytest.mark.asyncio
async def test_stub_context():
    store = StubContextStore()
    await store.set("objetivo", "Refactorizar arquitectura")
    val = await store.get("objetivo")
    assert val == "Refactorizar arquitectura"

@pytest.mark.asyncio
async def test_stub_planner():
    planner = StubPlanner()
    plan = await planner.create_plan("Optimizar agente", {})
    assert len(plan) == 2
    assert plan[0]["action"] == "stub_analyze"

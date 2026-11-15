from fastapi import FastAPI, APIRouter
from typing import Any, Dict
from atomum.inference.service import InferenceService
from atomum.planning.service import PlanningService

app = FastAPI(title="ATOMUM Planning Service")
router = APIRouter()
planning_svc = PlanningService(inference_engine=InferenceService())

@router.get("/health")
async def health_check() -> Dict[str, str]:
    return {"service": "planning", "status": "ok"}

@router.post("/plan")
async def create_plan(payload: Dict[str, Any]) -> Dict[str, Any]:
    goal = payload.get("goal", "")
    context = payload.get("context", {})
    plan = await planning_svc.create_plan(goal, context)
    return {"goal": goal, "plan": plan}

app.include_router(router)

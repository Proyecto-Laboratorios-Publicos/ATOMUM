from fastapi import FastAPI, APIRouter
from typing import Any, Dict
from atomum.context.service import ContextService

app = FastAPI(title="ATOMUM Context Service")
router = APIRouter()
context_svc = ContextService()

@router.get("/health")
async def health_check() -> Dict[str, str]:
    return {"service": "context", "status": "ok"}

@router.get("/context/{key}")
async def get_context(key: str) -> Dict[str, Any]:
    val = await context_svc.get(key)
    return {"key": key, "value": val}

@router.post("/context/{key}")
async def set_context(key: str, payload: Dict[str, Any]) -> Dict[str, str]:
    await context_svc.set(key, payload.get("value"), payload.get("ttl"))
    return {"status": "saved", "key": key}

app.include_router(router)

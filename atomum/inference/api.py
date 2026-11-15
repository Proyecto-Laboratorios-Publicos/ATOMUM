from fastapi import FastAPI, APIRouter, HTTPException
from typing import Any, Dict
from atomum.inference.service import InferenceService
from atomum.core.config import settings

app = FastAPI(title="ATOMUM Inference Service")
router = APIRouter()
inference_svc = InferenceService()

@router.get("/health")
async def health_check() -> Dict[str, str]:
    if not settings.groq_api_key:
        raise HTTPException(status_code=503, detail="GROQ_API_KEY no configurada")
    return {"service": "inference", "status": "ok"}

@router.post("/run")
async def run_inference(payload: Dict[str, Any]) -> Dict[str, Any]:
    model_id = payload.get("model_id", settings.default_model)
    input_data = payload.get("input", {})
    return await inference_svc.run(model_id, input_data)

app.include_router(router)

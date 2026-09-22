from functools import lru_cache
from fastapi import FastAPI, Depends
from pydantic import BaseModel
from core.config import Settings
from router.smart_router import SmartRouter

@lru_cache()
def get_settings():
    return Settings()

@lru_cache()
def get_router():
    return SmartRouter()

app = FastAPI(title="Kikos AI Core", version="0.1.0")

class RouteRequest(BaseModel):
    prompt: str
    task_type: str = "auto"

@app.get("/health")
def health(settings: Settings = Depends(get_settings)):
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.environment,
        "version": settings.app_version
    }

@app.post("/route")
def route_prompt(req: RouteRequest, router: SmartRouter = Depends(get_router)):
    selected_model = router.route(req.prompt, req.task_type)
    return {
        "prompt": req.prompt,
        "selected_model": selected_model
    }

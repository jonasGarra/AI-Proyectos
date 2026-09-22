from functools import lru_cache
from fastapi import FastAPI, Depends
from pydantic import BaseModel
import httpx
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
async def route_prompt(req: RouteRequest, router: SmartRouter = Depends(get_router)):
    selected_model = router.route(req.prompt, req.task_type)
    
    # Preparamos la petición para OmniRoute
    omniroute_url = "http://127.0.0.1:8001/v1/chat/completions"
    payload = {
        "model": selected_model,
        "messages": [{"role": "user", "content": req.prompt}]
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(omniroute_url, json=payload, timeout=30.0)
            
            if response.status_code != 200:
                return {"status": "error", "selected_model": selected_model, "omniroute_response": response.text}
                
            data = response.json()
            return {"status": "success", "selected_model": selected_model, "reply": data["choices"][0]["message"]["content"]}
            
    except Exception as e:
        return {
            "status": "connection_error", 
            "selected_model": selected_model,
            "message": "OmniRoute está apagado o inaccesible.",
            "error": str(e)
        }

from functools import lru_cache
from fastapi import FastAPI, Depends
from core.config import Settings

@lru_cache()
def get_settings():
    return Settings()

app = FastAPI(title="Kikos AI Core", version="0.1.0")

@app.get("/health")
def health(settings: Settings = Depends(get_settings)):
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.environment,
        "version": settings.app_version
    }

import os
import asyncio
from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

# 1. Imports de la Arquitectura Enterprise (Claude)
from core.config import Settings
from core.chat_store import ChatStore
from core.memory_manager import MemoryManager
from core.gateway import Gateway
from router.smart_router import SmartRouter
from core.orchestrator import Orchestrator
from core.service import KikosService
from core.errors import ApiError

# 2. Import de nuestro Gestor de Seguridad
from core.auth import AuthManager

# --- INICIALIZACIÓN DE MÓDULOS ---
settings = Settings.from_env()
store = ChatStore(settings.db_path, settings.workspaces_dir)
memory = MemoryManager(
    base_path=settings.workspaces_dir,
    max_context_chars=settings.context_max_chars,
    max_file_bytes=settings.context_max_file_bytes,
    history_max_messages=settings.history_max_messages,
    history_max_chars=settings.history_max_chars
)
gateway = Gateway(
    url=settings.gateway_url,
    api_key=settings.gateway_api_key,
    connect_timeout=settings.connect_timeout,
    read_timeout=settings.read_timeout
)
router = SmartRouter()
orchestrator = Orchestrator(router, gateway, total_timeout=settings.total_timeout)

# Inyectamos todo en el servicio centralizado
service = KikosService(settings, store, memory, orchestrator, gateway)
auth = AuthManager()

app = FastAPI(title="Kikos AI - Enterprise Edition")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- MANEJADOR DE ERRORES ---
@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError):
    return JSONResponse(status_code=exc.status, content=exc.to_dict())

# --- SEGURIDAD (Dependencia VIP) ---
async def get_current_user(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No autorizado")
    token = authorization.split(" ")[1]
    user = auth.verify_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Token expirado o inválido")
    return user

# --- MODELOS DE DATOS ---
class LoginRequest(BaseModel):
    username: str
    password: str

class ChatPayload(BaseModel):
    prompt: str
    mode: str = "pensativo"
    workspace: str = "default"
    regenerate: bool = False
    conversation_id: Optional[int] = None
    subproject_id: Optional[int] = None
    attachments: Optional[List[Dict[str, Any]]] = None
    images: Optional[List[Dict[str, Any]]] = None
    image_data: Optional[str] = None

# --- RUTAS DE LA API (Endpoints) ---

@app.post("/login")
async def login(request: LoginRequest):
    if auth.authenticate_user(request.username, request.password):
        token = auth.create_token(request.username)
        return {"status": "success", "token": token}
    raise HTTPException(status_code=401, detail="Credenciales incorrectas")

@app.get("/api/health")
async def health(user: str = Depends(get_current_user)):
    return service.health()

@app.get("/workspaces")
async def get_workspaces(user: str = Depends(get_current_user)):
    return service.workspaces()

@app.get("/api/tree")
async def get_tree(user: str = Depends(get_current_user)):
    return service.tree()

@app.post("/route")
async def route_chat(payload: ChatPayload, request: Request, user: str = Depends(get_current_user)):
    async def is_disconnected():
        return await request.is_disconnected()
    
    # Pasamos el payload convertido a diccionario al servicio inteligente
    return await service.send(payload.dict(), is_disconnected)


# --- SERVIR EL FRONTEND WEB ---
# Si un archivo existe en kikos_web, lo sirve (index.html, style.css, app.js). 
# Al estar abajo del todo, no pisa las rutas de la API.
app.mount("/", StaticFiles(directory="frontend", html=True), name="web")

"""Casos de uso de Kikos AI (proyectos, chats, envío de mensajes).

No depende de FastAPI: `main.py` solo conecta las rutas HTTP con estos métodos. Toda la entrada
se valida aquí, porque no se puede confiar en lo que envía el navegador.
"""
import asyncio
import functools
import logging
import re
import sqlite3
from typing import Callable, List, Optional

from core.chat_store import ChatStore
from core.config import IMAGE_TYPES, TEXT_EXTENSIONS, Settings
from core.errors import ApiError
from core.gateway import Gateway
from core.memory_manager import MemoryManager, ScopeContext
from core.orchestrator import AllModelsFailed, Orchestrator
from router.smart_router import MODES

log = logging.getLogger("kikos.service")

_IMAGE_DATA_URL = re.compile(r"data:image/(?:" + "|".join(IMAGE_TYPES) + r");base64,[A-Za-z0-9+/=]+")
_HTTP_STATUS_BY_CODE = {"gateway_down": 503, "timeout": 504, "too_long": 413}


class ClientDisconnected(Exception):
    """El navegador cerró la petición (por ejemplo, con el botón Detener)."""


def api_guard(fn):
    """Convierte cualquier fallo inesperado en un error genérico y deja el detalle en el log."""
    def failure(exc: Exception) -> ApiError:
        if isinstance(exc, sqlite3.Error):
            log.exception("Error de almacenamiento")
            return ApiError(500, "storage_error", "No se pudo acceder al almacenamiento de conversaciones.")
        log.exception("Error inesperado")
        return ApiError(500, "internal", "Ha ocurrido un error interno. Inténtalo de nuevo.")

    if asyncio.iscoroutinefunction(fn):
        @functools.wraps(fn)
        async def async_wrapper(*args, **kwargs):
            try:
                return await fn(*args, **kwargs)
            except ApiError:
                raise
            except Exception as exc:
                raise failure(exc)
        return async_wrapper

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ApiError:
            raise
        except Exception as exc:
            raise failure(exc)
    return wrapper


def _optional_id(value, field: str) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ApiError(400, "invalid_request", "El campo " + field + " no es válido.")
    return value


class KikosService:
    def __init__(self, settings: Settings, store: ChatStore, memory: MemoryManager,
                 orchestrator: Orchestrator, gateway: Gateway):
        self.settings = settings
        self.store = store
        self.memory = memory
        self.orchestrator = orchestrator
        self.gateway = gateway

    # ---------- estado general ----------
    @api_guard
    def health(self) -> dict:
        s = self.settings
        return {
            "status": "ok",
            "auth_required": s.auth_required,
            "gateway": self.gateway.health(),
            "limits": {
                "text_extensions": list(TEXT_EXTENSIONS),
                "image_types": list(IMAGE_TYPES),
                "max_text_attachments": s.max_text_attachments,
                "max_text_attachment_kb": s.max_text_attachment_chars // 1000,
                "max_images": s.max_images,
                "max_image_mb": round(s.max_image_chars * 3 / 4 / 1000000, 1),
                "max_prompt_chars": s.max_prompt_chars,
            },
        }

    @api_guard
    def workspaces(self) -> dict:
        return {"workspaces": self.memory.get_available_workspaces()}

    @api_guard
    def tree(self) -> dict:
        try:
            self.memory.sync_with_store(self.store)
        except Exception:
            log.exception("No se pudieron sincronizar las carpetas de memoria")
        return {"projects": self.store.tree()}

    # ---------- proyectos y subproyectos ----------
    @api_guard
    def create_project(self, name: str) -> dict:
        project = self.store.create_project(name)
        self.memory.ensure_workspace(project["slug"])
        return {"id": project["id"], "name": project["name"]}

    @api_guard
    def rename_project(self, project_id: int, name: str) -> dict:
        return self.store.rename_project(project_id, name)

    @api_guard
    def delete_project(self, project_id: int) -> dict:
        info = self.store.delete_project(project_id)
        self.memory.archive_workspace(info["slug"])
        return {"status": "success"}

    @api_guard
    def create_subproject(self, project_id: int, name: str) -> dict:
        sub = self.store.create_subproject(project_id, name)
        self.memory.ensure_workspace(sub["project_slug"], sub["slug"])
        return {"id": sub["id"], "name": sub["name"], "project_id": project_id}

    @api_guard
    def rename_subproject(self, subproject_id: int, name: str) -> dict:
        return self.store.rename_subproject(subproject_id, name)

    @api_guard
    def delete_subproject(self, subproject_id: int) -> dict:
        info = self.store.delete_subproject(subproject_id)
        self.memory.archive_workspace(info["project_slug"], info["slug"])
        return {"status": "success"}

    # ---------- conversaciones ----------
    @api_guard
    def create_conversation(self, subproject_id: int, title: Optional[str] = None) -> dict:
        return self.store.create_conversation(subproject_id, title)

    @api_guard
    def get_conversation(self, conversation_id: int) -> dict:
        conversation = self.store.get_conversation(conversation_id)
        scope = self.store.get_scope(conversation["subproject_id"])
        return {
            "conversation": conversation,
            "scope": {
                "project_id": scope["project_id"], "project_name": scope["project_name"],
                "subproject_id": scope["subproject_id"], "subproject_name": scope["sub_name"],
            },
            "messages": self.store.messages(conversation_id),
        }

    @api_guard
    def rename_conversation(self, conversation_id: int, title: str) -> dict:
        return self.store.rename_conversation(conversation_id, title)

    @api_guard
    def delete_conversation(self, conversation_id: int) -> dict:
        self.store.delete_conversation(conversation_id)
        return {"status": "success"}

    # ---------- validación de lo que llega del navegador ----------
    def _validate_files(self, raw) -> List[dict]:
        s = self.settings
        if raw in (None, []):
            return []
        if not isinstance(raw, list) or len(raw) > s.max_text_attachments:
            raise ApiError(400, "invalid_request", "Se admiten como máximo " + str(s.max_text_attachments) + " archivos de texto.")
        files = []
        for item in raw:
            if not isinstance(item, dict) or not isinstance(item.get("name"), str) or not isinstance(item.get("content"), str):
                raise ApiError(400, "invalid_request", "Un archivo adjunto no es válido.")
            name = re.sub(r"[\x00-\x1f\x7f]", "", re.split(r"[\\/]", item["name"])[-1]).strip()[:100] or "archivo"
            ext = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
            if ext not in TEXT_EXTENSIONS:
                raise ApiError(
                    400, "unsupported_file",
                    "Archivo no compatible: " + name + ". Tipos admitidos: " + ", ".join(TEXT_EXTENSIONS) + " e imágenes.",
                )
            content = item["content"]
            if len(content) > s.max_text_attachment_chars:
                raise ApiError(413, "file_too_large", "El archivo " + name + " es demasiado grande (máximo " + str(s.max_text_attachment_chars // 1000) + " KB).")
            files.append({"name": name, "kind": "text", "size": len(content.encode("utf-8")), "content": content})
        return files

    def _validate_images(self, raw, legacy) -> List[dict]:
        s = self.settings
        items = []
        if legacy:
            items.append({"name": "imagen", "data": legacy})
        if raw:
            if not isinstance(raw, list):
                raise ApiError(400, "invalid_request", "Las imágenes no son válidas.")
            items += raw
        if len(items) > s.max_images:
            raise ApiError(400, "invalid_request", "Se admiten como máximo " + str(s.max_images) + " imágenes por mensaje.")
        images = []
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("data"), str):
                raise ApiError(400, "invalid_request", "Una imagen adjunta no es válida.")
            name = re.sub(r"[\x00-\x1f\x7f]", "", re.split(r"[\\/]", str(item.get("name") or "imagen"))[-1]).strip()[:100] or "imagen"
            data = item["data"]
            if len(data) > s.max_image_chars:
                raise ApiError(413, "file_too_large", "La imagen " + name + " es demasiado grande.")
            if not _IMAGE_DATA_URL.fullmatch(data):
                raise ApiError(400, "unsupported_file", "Imagen no compatible: " + name + ". Formatos admitidos: " + ", ".join(IMAGE_TYPES) + ".")
            images.append({"name": name, "kind": "image", "size": len(data) * 3 // 4, "data": data})
        return images

    def _validate_send(self, payload: dict) -> dict:
        s = self.settings
        prompt = payload.get("prompt") or ""
        if not isinstance(prompt, str):
            raise ApiError(400, "invalid_request", "El mensaje no es válido.")
        prompt = prompt.strip()
        if len(prompt) > s.max_prompt_chars:
            raise ApiError(413, "prompt_too_long", "El mensaje es demasiado largo (máximo " + str(s.max_prompt_chars) + " caracteres).")
        mode = payload.get("mode") or "pensativo"
        if mode not in MODES:
            raise ApiError(400, "invalid_request", "El modo elegido no es válido.")
        workspace = payload.get("workspace") or "default"
        if not isinstance(workspace, str) or len(workspace) > 130:
            raise ApiError(400, "invalid_request", "El espacio de trabajo no es válido.")
        data = {
            "prompt": prompt,
            "mode": mode,
            "workspace": workspace,
            "regenerate": bool(payload.get("regenerate")),
            "conversation_id": _optional_id(payload.get("conversation_id"), "conversation_id"),
            "subproject_id": _optional_id(payload.get("subproject_id"), "subproject_id"),
            "files": self._validate_files(payload.get("attachments")),
            "images": self._validate_images(payload.get("images"), payload.get("image_data")),
        }
        if data["regenerate"] and data["conversation_id"] is None:
            raise ApiError(400, "invalid_request", "Para regenerar hay que indicar la conversación.")
        if not data["regenerate"] and not (prompt or data["files"] or data["images"]):
            raise ApiError(400, "empty_message", "Escribe un mensaje o adjunta un archivo.")
        return data

    # ---------- envío de mensajes ----------
    @staticmethod
    async def _run_cancellable(fn: Callable, is_disconnected: Callable):
        """Ejecuta la llamada al modelo en un hilo y la abandona si el navegador cierra la conexión."""
        loop = asyncio.get_running_loop()
        future = loop.run_in_executor(None, fn)
        while True:
            done, _pending = await asyncio.wait({future}, timeout=0.3)
            if done:
                return future.result()
            if await is_disconnected():
                future.add_done_callback(lambda f: f.cancelled() or f.exception())
                raise ClientDisconnected()

    def _load_context(self, scope: Optional[dict], workspace: str, conversation_id: Optional[int], warnings: list):
        """Archivos de contexto + resumen de otras conversaciones. Siempre del MISMO subproyecto."""
        context, recap_rows = ScopeContext(), []
        try:
            if scope is not None:
                if not scope["is_general"]:
                    context = self.memory.get_scope_context(scope["project_slug"], scope["sub_slug"])
                    recap_rows = self.store.recap(scope["subproject_id"], conversation_id)
            elif workspace != "default":
                segments = workspace.split("/")
                if len(segments) > 2 or not self.memory.valid_workspace(workspace):
                    raise ApiError(400, "invalid_workspace", "El espacio de trabajo no es válido.")
                context = self.memory.get_scope_context(segments[0], segments[1] if len(segments) == 2 else None)
        except ApiError:
            raise
        except Exception:
            log.exception("Error de memoria: se responde sin contexto")
            warnings.append("memory")
            context, recap_rows = ScopeContext(), []
        return context, recap_rows

    @api_guard
    async def send(self, payload: dict, is_disconnected: Callable) -> dict:
        data = self._validate_send(payload)
        store = self.store

        # 1. ¿En qué conversación y en qué subproyecto estamos?
        conversation_id, scope = data["conversation_id"], None
        if conversation_id is not None:
            scope = store.get_conversation_scope(conversation_id)
        elif data["subproject_id"] is not None:
            scope = store.get_scope(data["subproject_id"])
            conversation_id = store.create_conversation(data["subproject_id"])["id"]

        # 2. Historial y mensaje del usuario
        stored_attachments = data["files"] + [
            {"name": i["name"], "kind": "image", "size": i["size"]} for i in data["images"]
        ]
        user_public, old_assistant, images = None, None, [i["data"] for i in data["images"]]
        if conversation_id is None:                              # petición sin guardar (compatibilidad)
            history = [{"role": "user", "content": data["prompt"], "attachments": stored_attachments, "meta": {}}]
        else:
            history = store.messages(conversation_id, with_content=True)
            if data["regenerate"]:
                if history and history[-1]["role"] == "assistant":
                    old_assistant = history.pop()
                if not history or history[-1]["role"] != "user":
                    raise ApiError(400, "invalid_request", "No hay ningún mensaje del usuario que regenerar.")
                images = []
            else:
                user_public = store.add_message(
                    conversation_id, "user", data["prompt"], attachments=stored_attachments or None
                )
                store.maybe_autotitle(
                    conversation_id,
                    data["prompt"] or (stored_attachments[0]["name"] if stored_attachments else ""),
                )
                history.append({
                    "role": "user", "content": data["prompt"], "attachments": stored_attachments, "meta": {},
                })

        # 3. Memoria: contexto del subproyecto + historial
        warnings: list = []
        context, recap_rows = self._load_context(scope, data["workspace"], conversation_id, warnings)
        messages = self.memory.build_messages(
            history, context.text, self.memory.format_recap(recap_rows), images or None
        )

        last_user = history[-1]
        classify_text = (last_user["content"] + " " + " ".join(a["name"] for a in last_user.get("attachments") or [])).strip()
        previous_task = next(
            (m["meta"].get("task") for m in reversed(history[:-1]) if m["role"] == "assistant" and m.get("meta")), None
        )
        input_length = sum(
            len(m["content"]) if isinstance(m["content"], str)
            else sum(len(p.get("text", "")) for p in m["content"] if p.get("type") == "text")
            for m in messages
        )
        has_text_files = any(a.get("kind") == "text" for a in last_user.get("attachments") or [])

        def work():
            return self.orchestrator.generate(
                classify_text, messages, data["mode"], has_image=bool(images), input_length=input_length,
                previous_task=previous_task, has_attachments=has_text_files,
            )

        def partial_info() -> dict:
            info = {}
            if conversation_id is not None:
                info["conversation"] = store.get_conversation(conversation_id)
            if user_public is not None:
                info["user_message"] = user_public
            return info

        # 4. Modelo (con fallback dentro del orquestador)
        try:
            generation = await self._run_cancellable(work, is_disconnected)
        except ClientDisconnected:
            log.info("El cliente canceló la petición; no se guarda ninguna respuesta")
            raise ApiError(499, "client_closed", "Petición cancelada.")
        except AllModelsFailed as exc:
            extra = partial_info()
            extra["attempts"] = exc.attempts
            raise ApiError(_HTTP_STATUS_BY_CODE.get(exc.code, 502), exc.code, exc.user_message, extra)

        # 5. Guardar la respuesta (memoria de esta y de futuras conversaciones)
        meta = {
            "task": generation.task,
            "model": generation.model,
            "mode": generation.mode,
            "confidence": generation.confidence,
            "latency_ms": generation.latency_ms,
            "fallback": generation.fallback,
            "attempts": generation.attempts,
            "context_files": context.files,
            "recap_messages": len(recap_rows),
            "warnings": warnings,
        }
        result = {
            "status": "success",
            "workspace": (scope["project_slug"] + "/" + scope["sub_slug"]) if scope else data["workspace"],
            "model": generation.model,
            "reply": generation.reply,
            "meta": meta,
        }
        if conversation_id is not None:
            if old_assistant is not None:
                store.delete_message(old_assistant["id"])
            result["message"] = store.add_message(conversation_id, "assistant", generation.reply, meta=meta)
            result["conversation"] = store.get_conversation(conversation_id)
            if user_public is not None:
                result["user_message"] = user_public
        return result

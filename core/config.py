"""Configuración de Kikos AI.

Todo se lee de variables de entorno. Si existe un archivo `.env` en la carpeta del
proyecto, se cargan sus valores sin pisar las variables que ya estén definidas.
Las rutas son relativas a la carpeta desde la que arrancas (o a KIKOS_HOME).
"""
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

# Tipos de archivo de texto que se pueden usar como contexto o adjuntar al chat
TEXT_EXTENSIONS = (".md", ".txt", ".java", ".cs", ".py", ".sql", ".json", ".js", ".html", ".css", ".sh")
IMAGE_TYPES = ("png", "jpeg", "webp", "gif")


def _load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _number(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return float(default)


def _flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "si", "sí", "on")


@dataclass(frozen=True)
class Settings:
    base_dir: Path
    gateway_url: str
    gateway_api_key: str
    connect_timeout: float
    read_timeout: float
    total_timeout: float
    auth_required: bool
    db_path: Path
    workspaces_dir: Path
    frontend_dir: Path
    log_dir: Path
    allowed_origins: Tuple[str, ...]
    # Límites de entrada y de contexto
    max_prompt_chars: int = 20000
    max_text_attachments: int = 5
    max_text_attachment_chars: int = 200000
    max_images: int = 3
    max_image_chars: int = 6000000          # data-URL en base64 (~4,5 MB de imagen)
    history_max_messages: int = 24
    history_max_chars: int = 30000
    context_max_chars: int = 60000
    context_max_file_bytes: int = 100000
    long_context_chars: int = 20000

    @classmethod
    def from_env(cls) -> "Settings":
        base = Path(os.environ.get("KIKOS_HOME", ".")).resolve()
        _load_env_file(base / ".env")
        origins = os.environ.get("KIKOS_ALLOWED_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000")
        return cls(
            base_dir=base,
            gateway_url=os.environ.get("KIKOS_GATEWAY_URL", "http://127.0.0.1:8001/v1/chat/completions"),
            gateway_api_key=os.environ.get("KIKOS_GATEWAY_API_KEY", ""),
            connect_timeout=_number("KIKOS_CONNECT_TIMEOUT", 5),
            read_timeout=_number("KIKOS_READ_TIMEOUT", 90),
            total_timeout=_number("KIKOS_TOTAL_TIMEOUT", 150),
            auth_required=_flag("KIKOS_AUTH_REQUIRED", False),
            db_path=Path(os.environ.get("KIKOS_DB_PATH", base / "data" / "kikos_chats.db")),
            workspaces_dir=Path(os.environ.get("KIKOS_WORKSPACES_DIR", base / "core" / "memory" / "workspaces")),
            frontend_dir=Path(os.environ.get("KIKOS_FRONTEND_DIR", base / "frontend")),
            log_dir=Path(os.environ.get("KIKOS_LOG_DIR", base / "logs")),
            allowed_origins=tuple(o.strip() for o in origins.split(",") if o.strip()),
        )

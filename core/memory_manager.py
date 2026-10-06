"""Memoria de Kikos AI.

Qué es cada cosa (no se mezclan):
  - proyecto / subproyecto : carpetas en  base_path/<proyecto>/<subproyecto>  (y filas en la BD)
  - conversación / mensajes: viven en la BD (chat_store.py)
  - memoria                : lo que se le da al modelo además del mensaje:
        1. archivos de contexto de la carpeta del proyecto (solo los de su nivel) y de la
           carpeta del subproyecto (recursivo). Nunca los de otro proyecto ni los de un
           subproyecto hermano.
        2. historial de la conversación actual.
        3. resumen de otras conversaciones del MISMO subproyecto.
"""
import os
import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from core.config import TEXT_EXTENSIONS

# Un nombre de carpeta válido: sin barras, sin empezar por punto/guion bajo
_SEGMENT = re.compile(r"^[^\W_][\w .\-]{0,63}$", re.UNICODE)
_SKIP_DIRS = {"node_modules", "__pycache__", "venv", "dist", "build"}

SYSTEM_INSTRUCTION = (
    "Eres Kikos AI, un asistente de IA avanzado. Responde en el idioma del usuario y usa Markdown "
    "(listas y bloques de código con ```) cuando ayude a la claridad.\n"
    "REGLA DE COMPORTAMIENTO ESTRICTA: Si te proporcionan código, archivos o memoria a continuación, "
    "SOLO debes hablar de ellos si la pregunta del usuario está relacionada. "
    "Si el usuario solo te saluda, bromea o hace una pregunta genérica, RESPONDE CON NATURALIDAD "
    "y omite por completo la existencia de los archivos."
)


@dataclass
class ScopeContext:
    text: str = ""
    files: int = 0
    truncated: bool = False


class MemoryManager:
    def __init__(self, base_path="core/memory/workspaces", max_context_chars=60000,
                 max_file_bytes=100000, history_max_messages=24, history_max_chars=30000):
        self.base_path = Path(base_path)
        os.makedirs(self.base_path, exist_ok=True)
        self.allowed_ext = set(TEXT_EXTENSIONS)
        self.max_context_chars = max_context_chars
        self.max_file_bytes = max_file_bytes
        self.history_max_messages = history_max_messages
        self.history_max_chars = history_max_chars

    # ---------- carpetas ----------
    @staticmethod
    def _visible(name: str) -> bool:
        return not name.startswith((".", "_")) and name not in _SKIP_DIRS

    def _safe_dir(self, *segments: str) -> Optional[Path]:
        """Devuelve la carpeta pedida solo si es válida y está dentro de base_path."""
        base = self.base_path.resolve()
        path = base
        for segment in segments:
            if not isinstance(segment, str) or not _SEGMENT.match(segment) or ".." in segment:
                return None
            path = path / segment
        try:
            resolved = path.resolve()
            resolved.relative_to(base)
        except (ValueError, OSError):
            return None
        return resolved

    def get_available_workspaces(self) -> list:
        workspaces = ["default"]
        for root, dirs, _files in os.walk(self.base_path):
            dirs[:] = sorted(d for d in dirs if self._visible(d))
            rel_path = os.path.relpath(root, self.base_path)
            if rel_path != ".":
                workspaces.append(rel_path.replace("\\", "/"))
        return sorted(set(workspaces))

    def valid_workspace(self, workspace_name: str) -> bool:
        """¿Es un nombre 'proyecto' o 'proyecto/subproyecto' seguro (sin salirse de base_path)?"""
        return self._safe_dir(*workspace_name.split("/")) is not None

    def ensure_workspace(self, *segments: str) -> None:
        path = self._safe_dir(*segments)
        if path is not None:
            path.mkdir(parents=True, exist_ok=True)

    def archive_workspace(self, *segments: str) -> None:
        """Al eliminar un proyecto no se borran sus archivos: si la carpeta está vacía se quita,
        y si tiene archivos se aparta con un nombre oculto para que no vuelva a aparecer."""
        path = self._safe_dir(*segments)
        if path is None or not path.is_dir():
            return
        try:
            if not any(path.iterdir()):
                path.rmdir()
            else:
                path.rename(path.with_name(".eliminado-" + path.name + "-" + str(int(time.time()))))
        except OSError:
            pass

    def sync_with_store(self, store) -> None:
        """Las carpetas que ya existen en disco (nivel 1 = proyecto, nivel 2 = subproyecto)
        aparecen como proyectos y subproyectos en la interfaz."""
        for project_dir in self._subdirs(self.base_path):
            project_id = store.ensure_project(project_dir.name, project_dir.name)
            for sub_dir in self._subdirs(project_dir):
                store.ensure_subproject(project_id, sub_dir.name, sub_dir.name)

    def _subdirs(self, directory: Path) -> List[Path]:
        try:
            entries = sorted(directory.iterdir(), key=lambda p: p.name.lower())
        except OSError:
            return []
        return [
            p for p in entries
            if p.is_dir() and not p.is_symlink() and self._visible(p.name) and _SEGMENT.match(p.name)
        ]

    # ---------- archivos de contexto ----------
    def _collect_files(self, directory: Path, recursive: bool, budget: int):
        """Devuelve ([(ruta relativa, texto)], archivos_leidos, recortado)."""
        found, count, truncated = [], 0, False
        if recursive:
            walker = os.walk(directory)
        else:
            walker = [(str(directory), [], [f.name for f in directory.iterdir() if f.is_file()])]
        for root, dirs, files in walker:
            dirs[:] = sorted(d for d in dirs if self._visible(d))
            for name in sorted(files):
                if name.startswith(".") or os.path.splitext(name)[1].lower() not in self.allowed_ext:
                    continue
                path = Path(root) / name
                try:
                    if path.stat().st_size > self.max_file_bytes:
                        continue
                    text = path.read_text(encoding="utf-8").strip()
                except (OSError, UnicodeDecodeError):
                    continue
                if budget - len(text) < 0:
                    truncated = True
                    continue
                budget -= len(text)
                found.append((path.relative_to(directory).as_posix(), text))
                count += 1
        return found, count, truncated, budget

    def get_scope_context(self, project_slug: str, sub_slug: Optional[str] = None) -> ScopeContext:
        """Contexto de UN subproyecto: archivos de su proyecto (solo su nivel) + los del propio subproyecto."""
        project_dir = self._safe_dir(project_slug)
        if project_dir is None or not project_dir.is_dir():
            return ScopeContext()
        budget = self.max_context_chars
        blocks, total, truncated = [], 0, False

        files, n, cut, budget = self._collect_files(project_dir, recursive=False, budget=budget)
        truncated = truncated or cut
        total += n
        if files:
            blocks.append("ARCHIVOS DEL PROYECTO '" + project_slug + "':")
            blocks += ["--- " + rel + " ---\n" + text + "\n" for rel, text in files]

        if sub_slug:
            sub_dir = self._safe_dir(project_slug, sub_slug)
            if sub_dir is not None and sub_dir.is_dir():
                files, n, cut, budget = self._collect_files(sub_dir, recursive=True, budget=budget)
                truncated = truncated or cut
                total += n
                if files:
                    blocks.append("ARCHIVOS DEL SUBPROYECTO '" + sub_slug + "':")
                    blocks += ["--- " + rel + " ---\n" + text + "\n" for rel, text in files]

        if total == 0:
            return ScopeContext()
        if truncated:
            blocks.append("(Algunos archivos se omitieron por exceder el límite de contexto.)")
        return ScopeContext(text="\n".join(blocks), files=total, truncated=truncated)

    def get_workspace_content(self, workspace_name: str, recursive: bool = True) -> str:
        """Compatibilidad con la versión anterior: contenido de un espacio de trabajo por nombre."""
        if not workspace_name or workspace_name == "default":
            return ""
        segments = workspace_name.split("/")
        directory = self._safe_dir(*segments)
        if directory is None or not directory.is_dir():
            return ""
        files, n, _cut, _left = self._collect_files(directory, recursive, self.max_context_chars)
        if n == 0:
            return ""
        parts = ["ARCHIVOS DEL PROYECTO '" + workspace_name + "':\n"]
        parts += ["--- " + rel + " ---\n" + text + "\n" for rel, text in files]
        return "\n".join(parts)

    # ---------- construcción del prompt ----------
    @staticmethod
    def format_recap(rows: List[dict], per_message: int = 300, total: int = 2400) -> str:
        """Resumen de otras conversaciones del subproyecto. No usa ningún modelo: recorta los últimos mensajes."""
        if not rows:
            return ""
        lines = []
        for row in rows:
            who = "Usuario" if row["role"] == "user" else "Kikos AI"
            text = re.sub(r"\s+", " ", row["content"]).strip()
            if len(text) > per_message:
                text = text[: per_message - 1].rstrip() + "…"
            lines.append("- (" + row["title"] + ") " + who + ": " + text)
        body = "\n".join(lines)
        if len(body) > total:
            body = body[-total:]
        return (
            "MEMORIA DE OTRAS CONVERSACIONES DE ESTE SUBPROYECTO (solo referencia; no la menciones "
            "salvo que venga al caso):\n" + body
        )

    def build_system_prompt(self, files_text: str = "", recap_text: str = "") -> str:
        parts = [SYSTEM_INSTRUCTION]
        if files_text:
            parts.append(files_text)
        if recap_text:
            parts.append(recap_text)
        return "\n\n".join(parts)

    @staticmethod
    def _render_user_text(message: dict, skip_image_tags: bool) -> str:
        text = message["content"]
        for att in message.get("attachments") or []:
            if att.get("kind") == "text":
                text += "\n\n[Archivo adjunto: " + att["name"] + "]\n```\n" + att.get("content", "") + "\n```"
            elif att.get("kind") == "image" and not skip_image_tags:
                text += "\n\n[Imagen adjunta: " + att["name"] + "]"
        return text.strip()

    def build_messages(self, history: List[dict], files_text: str = "", recap_text: str = "",
                       images: Optional[List[str]] = None) -> list:
        """Mensajes en formato chat/completions. `history` termina siempre en un mensaje del usuario."""
        last_index = len(history) - 1
        rendered = []
        for i, message in enumerate(history):
            if message["role"] == "user":
                text = self._render_user_text(message, skip_image_tags=bool(images) and i == last_index)
            else:
                text = message["content"]
            rendered.append({"role": message["role"], "content": text})

        # Recortamos los mensajes más antiguos si el historial es demasiado largo
        kept, used = [], 0
        for item in reversed(rendered):
            if len(kept) >= self.history_max_messages:
                break
            if kept and used + len(item["content"]) > self.history_max_chars:
                break
            kept.append(item)
            used += len(item["content"])
        kept.reverse()
        while kept and kept[0]["role"] != "user":
            kept.pop(0)

        if images and kept:
            parts = [{"type": "text", "text": kept[-1]["content"] or "Describe la imagen."}]
            parts += [{"type": "image_url", "image_url": {"url": url}} for url in images]
            kept[-1] = {"role": "user", "content": parts}

        return [{"role": "system", "content": self.build_system_prompt(files_text, recap_text)}] + kept

    def build_prompt(self, user_prompt: str, workspace_name: str = "default") -> str:
        """Compatibilidad con la versión anterior (un único texto)."""
        context = self.get_workspace_content(workspace_name)
        return self.build_system_prompt(context) + "\n\nPREGUNTA DEL USUARIO:\n" + user_prompt

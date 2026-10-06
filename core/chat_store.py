"""Almacén de conversaciones (SQLite, solo librería estándar).

Jerarquía:  proyecto → subproyecto → conversación → mensajes.
Cada conversación pertenece a UN subproyecto y cada subproyecto a UN proyecto, y todas
las consultas filtran por esos identificadores: es lo que impide que el contexto de un
proyecto o subproyecto llegue a otro.
"""
import json
import re
import sqlite3
import unicodedata
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from core.errors import ApiError

GENERAL_PROJECT_SLUG = "_general"      # empieza por "_": nunca coincide con una carpeta real
GENERAL_PROJECT_NAME = "General"
GENERAL_SUB_SLUG = "preguntas-rapidas"
GENERAL_SUB_NAME = "Preguntas rápidas"
DEFAULT_TITLE = "Nueva conversación"
NAME_MAX = 60
TITLE_MAX = 60


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def slugify(text: str, fallback: str = "espacio") -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")[:40].strip("-")
    return slug or fallback


def clean_name(value, field: str = "nombre", max_len: int = NAME_MAX) -> str:
    if not isinstance(value, str):
        raise ApiError(400, "invalid_name", "El " + field + " no es válido.")
    name = re.sub(r"\s+", " ", re.sub(r"[\x00-\x1f\x7f]+", " ", value)).strip()
    if not name:
        raise ApiError(400, "invalid_name", "Escribe un " + field + ".")
    if len(name) > max_len:
        raise ApiError(400, "invalid_name", "El " + field + " no puede superar los " + str(max_len) + " caracteres.")
    return name


class ChatStore:
    def __init__(self, db_path, workspaces_dir):
        self.db_path = Path(db_path)
        self.workspaces_dir = Path(workspaces_dir)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self.ensure_general()

    # ---------- conexión ----------
    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(str(self.db_path), timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._conn() as c:
            c.executescript(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    slug TEXT NOT NULL UNIQUE,
                    is_general INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS subprojects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    slug TEXT NOT NULL,
                    is_general INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    UNIQUE (project_id, slug)
                );
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subproject_id INTEGER NOT NULL REFERENCES subprojects(id) ON DELETE CASCADE,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    attachments TEXT,
                    meta TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages (conversation_id, id);
                CREATE INDEX IF NOT EXISTS idx_conv_sub ON conversations (subproject_id, updated_at);
                """
            )

    # ---------- General ----------
    def ensure_general(self) -> None:
        with self._conn() as c:
            row = c.execute("SELECT id FROM projects WHERE slug = ?", (GENERAL_PROJECT_SLUG,)).fetchone()
            if row:
                project_id = row["id"]
            else:
                project_id = c.execute(
                    "INSERT INTO projects (name, slug, is_general, created_at) VALUES (?, ?, 1, ?)",
                    (GENERAL_PROJECT_NAME, GENERAL_PROJECT_SLUG, _now()),
                ).lastrowid
            if not c.execute(
                "SELECT 1 FROM subprojects WHERE project_id = ? AND slug = ?", (project_id, GENERAL_SUB_SLUG)
            ).fetchone():
                c.execute(
                    "INSERT INTO subprojects (project_id, name, slug, is_general, created_at) VALUES (?, ?, ?, 1, ?)",
                    (project_id, GENERAL_SUB_NAME, GENERAL_SUB_SLUG, _now()),
                )

    # ---------- árbol para la barra lateral ----------
    def tree(self) -> list:
        with self._conn() as c:
            projects = c.execute(
                "SELECT id, name, is_general FROM projects ORDER BY is_general DESC, name COLLATE NOCASE"
            ).fetchall()
            subs = c.execute(
                "SELECT id, project_id, name, is_general FROM subprojects ORDER BY is_general DESC, name COLLATE NOCASE"
            ).fetchall()
            convs = c.execute(
                "SELECT id, subproject_id, title, updated_at FROM conversations ORDER BY updated_at DESC, id DESC"
            ).fetchall()
        convs_by_sub = {}
        for r in convs:
            convs_by_sub.setdefault(r["subproject_id"], []).append(
                {"id": r["id"], "title": r["title"], "updated_at": r["updated_at"]}
            )
        subs_by_project = {}
        for r in subs:
            subs_by_project.setdefault(r["project_id"], []).append(
                {
                    "id": r["id"],
                    "name": r["name"],
                    "is_general": bool(r["is_general"]),
                    "conversations": convs_by_sub.get(r["id"], []),
                }
            )
        return [
            {
                "id": r["id"],
                "name": r["name"],
                "is_general": bool(r["is_general"]),
                "subprojects": subs_by_project.get(r["id"], []),
            }
            for r in projects
        ]

    # ---------- proyectos ----------
    def _unique_slug(self, c, table: str, base: str, parent_id: Optional[int], parent_dir: Path) -> str:
        slug, n = base, 1
        while True:
            if table == "projects":
                taken = c.execute("SELECT 1 FROM projects WHERE slug = ?", (slug,)).fetchone()
            else:
                taken = c.execute(
                    "SELECT 1 FROM subprojects WHERE project_id = ? AND slug = ?", (parent_id, slug)
                ).fetchone()
            # Una carpeta que ya existe en disco sin pertenecer a nadie tampoco se reutiliza:
            # así un proyecto nuevo nunca hereda archivos de uno eliminado.
            if not taken and not (parent_dir / slug).exists():
                return slug
            n += 1
            slug = base + "-" + str(n)

    def create_project(self, name: str) -> dict:
        name = clean_name(name, "nombre del proyecto")
        with self._conn() as c:
            slug = self._unique_slug(c, "projects", slugify(name, "proyecto"), None, self.workspaces_dir)
            pid = c.execute(
                "INSERT INTO projects (name, slug, is_general, created_at) VALUES (?, ?, 0, ?)",
                (name, slug, _now()),
            ).lastrowid
        return {"id": pid, "name": name, "slug": slug}

    def ensure_project(self, name: str, slug: str) -> int:
        """Usado al importar carpetas que ya existen en disco."""
        with self._conn() as c:
            row = c.execute("SELECT id FROM projects WHERE slug = ?", (slug,)).fetchone()
            if row:
                return row["id"]
            return c.execute(
                "INSERT INTO projects (name, slug, is_general, created_at) VALUES (?, ?, 0, ?)",
                (name[:NAME_MAX], slug, _now()),
            ).lastrowid

    def _get_project(self, c, project_id: int):
        row = c.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        if not row:
            raise ApiError(404, "not_found", "El proyecto no existe.")
        return row

    def rename_project(self, project_id: int, name: str) -> dict:
        name = clean_name(name, "nombre del proyecto")
        with self._conn() as c:
            row = self._get_project(c, project_id)
            if row["is_general"]:
                raise ApiError(403, "protected", "El proyecto General no se puede modificar.")
            c.execute("UPDATE projects SET name = ? WHERE id = ?", (name, project_id))
        return {"id": project_id, "name": name}

    def delete_project(self, project_id: int) -> dict:
        with self._conn() as c:
            row = self._get_project(c, project_id)
            if row["is_general"]:
                raise ApiError(403, "protected", "El proyecto General no se puede eliminar.")
            slug = row["slug"]
            c.execute("DELETE FROM projects WHERE id = ?", (project_id,))  # cascada: subproyectos, chats, mensajes
        return {"slug": slug}

    # ---------- subproyectos ----------
    def create_subproject(self, project_id: int, name: str) -> dict:
        name = clean_name(name, "nombre del subproyecto")
        with self._conn() as c:
            project = self._get_project(c, project_id)
            if project["is_general"]:
                raise ApiError(403, "protected", "El proyecto General no admite subproyectos.")
            slug = self._unique_slug(
                c, "subprojects", slugify(name, "subproyecto"), project_id, self.workspaces_dir / project["slug"]
            )
            sid = c.execute(
                "INSERT INTO subprojects (project_id, name, slug, is_general, created_at) VALUES (?, ?, ?, 0, ?)",
                (project_id, name, slug, _now()),
            ).lastrowid
        return {"id": sid, "name": name, "slug": slug, "project_slug": project["slug"]}

    def ensure_subproject(self, project_id: int, name: str, slug: str) -> int:
        with self._conn() as c:
            row = c.execute(
                "SELECT id FROM subprojects WHERE project_id = ? AND slug = ?", (project_id, slug)
            ).fetchone()
            if row:
                return row["id"]
            return c.execute(
                "INSERT INTO subprojects (project_id, name, slug, is_general, created_at) VALUES (?, ?, ?, 0, ?)",
                (project_id, name[:NAME_MAX], slug, _now()),
            ).lastrowid

    def _get_sub(self, c, subproject_id: int):
        row = c.execute(
            """SELECT s.*, p.slug AS project_slug, p.name AS project_name, p.is_general AS project_general
               FROM subprojects s JOIN projects p ON p.id = s.project_id WHERE s.id = ?""",
            (subproject_id,),
        ).fetchone()
        if not row:
            raise ApiError(404, "not_found", "El subproyecto no existe.")
        return row

    def rename_subproject(self, subproject_id: int, name: str) -> dict:
        name = clean_name(name, "nombre del subproyecto")
        with self._conn() as c:
            row = self._get_sub(c, subproject_id)
            if row["is_general"]:
                raise ApiError(403, "protected", "El subproyecto de General no se puede modificar.")
            c.execute("UPDATE subprojects SET name = ? WHERE id = ?", (name, subproject_id))
        return {"id": subproject_id, "name": name}

    def delete_subproject(self, subproject_id: int) -> dict:
        with self._conn() as c:
            row = self._get_sub(c, subproject_id)
            if row["is_general"]:
                raise ApiError(403, "protected", "El subproyecto de General no se puede eliminar.")
            info = {"project_slug": row["project_slug"], "slug": row["slug"]}
            c.execute("DELETE FROM subprojects WHERE id = ?", (subproject_id,))
        return info

    def get_scope(self, subproject_id: int) -> dict:
        """Dónde vive un subproyecto: es la única fuente de verdad para elegir su contexto."""
        with self._conn() as c:
            row = self._get_sub(c, subproject_id)
        return {
            "project_id": row["project_id"],
            "project_name": row["project_name"],
            "project_slug": row["project_slug"],
            "subproject_id": row["id"],
            "sub_name": row["name"],
            "sub_slug": row["slug"],
            "is_general": bool(row["project_general"]),
        }

    # ---------- conversaciones ----------
    def create_conversation(self, subproject_id: int, title: Optional[str] = None) -> dict:
        title = clean_name(title, "título", TITLE_MAX) if title else DEFAULT_TITLE
        with self._conn() as c:
            self._get_sub(c, subproject_id)
            now = _now()
            cid = c.execute(
                "INSERT INTO conversations (subproject_id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (subproject_id, title, now, now),
            ).lastrowid
        return {"id": cid, "title": title, "subproject_id": subproject_id, "updated_at": now}

    def _get_conv(self, c, conversation_id: int):
        row = c.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
        if not row:
            raise ApiError(404, "not_found", "La conversación no existe.")
        return row

    def get_conversation(self, conversation_id: int) -> dict:
        with self._conn() as c:
            row = self._get_conv(c, conversation_id)
        return {
            "id": row["id"],
            "title": row["title"],
            "subproject_id": row["subproject_id"],
            "updated_at": row["updated_at"],
        }

    def get_conversation_scope(self, conversation_id: int) -> dict:
        conv = self.get_conversation(conversation_id)
        return self.get_scope(conv["subproject_id"])

    def rename_conversation(self, conversation_id: int, title: str) -> dict:
        title = clean_name(title, "título", TITLE_MAX)
        with self._conn() as c:
            self._get_conv(c, conversation_id)
            c.execute("UPDATE conversations SET title = ? WHERE id = ?", (title, conversation_id))
        return {"id": conversation_id, "title": title}

    def delete_conversation(self, conversation_id: int) -> None:
        with self._conn() as c:
            self._get_conv(c, conversation_id)
            c.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))

    def maybe_autotitle(self, conversation_id: int, text: str) -> None:
        """Pone como título el principio del primer mensaje (sin gastar ninguna llamada a un modelo)."""
        text = re.sub(r"\s+", " ", text or "").strip()
        if not text:
            return
        title = text if len(text) <= 48 else text[:47].rstrip() + "…"
        with self._conn() as c:
            c.execute(
                "UPDATE conversations SET title = ? WHERE id = ? AND title = ?",
                (title, conversation_id, DEFAULT_TITLE),
            )

    # ---------- mensajes ----------
    @staticmethod
    def _message_dict(row, with_content: bool) -> dict:
        attachments = json.loads(row["attachments"]) if row["attachments"] else []
        meta = json.loads(row["meta"]) if row["meta"] else {}
        if not with_content:
            attachments = [{k: v for k, v in a.items() if k != "content"} for a in attachments]
        return {
            "id": row["id"],
            "role": row["role"],
            "content": row["content"],
            "attachments": attachments,
            "meta": meta,
            "created_at": row["created_at"],
        }

    def messages(self, conversation_id: int, with_content: bool = False) -> List[dict]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT id, role, content, attachments, meta, created_at FROM messages "
                "WHERE conversation_id = ? ORDER BY id",
                (conversation_id,),
            ).fetchall()
        return [self._message_dict(r, with_content) for r in rows]

    def add_message(self, conversation_id: int, role: str, content: str,
                    attachments: Optional[list] = None, meta: Optional[dict] = None) -> dict:
        now = _now()
        with self._conn() as c:
            self._get_conv(c, conversation_id)
            mid = c.execute(
                "INSERT INTO messages (conversation_id, role, content, attachments, meta, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    conversation_id,
                    role,
                    content,
                    json.dumps(attachments, ensure_ascii=False) if attachments else None,
                    json.dumps(meta, ensure_ascii=False) if meta else None,
                    now,
                ),
            ).lastrowid
            c.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (now, conversation_id))
            row = c.execute(
                "SELECT id, role, content, attachments, meta, created_at FROM messages WHERE id = ?", (mid,)
            ).fetchone()
        return self._message_dict(row, with_content=False)

    def delete_message(self, message_id: int) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM messages WHERE id = ?", (message_id,))

    # ---------- memoria entre conversaciones ----------
    def recap(self, subproject_id: int, exclude_conversation_id: Optional[int], limit: int = 8) -> List[dict]:
        """Últimos mensajes de OTRAS conversaciones del MISMO subproyecto (nunca de otros subproyectos)."""
        with self._conn() as c:
            rows = c.execute(
                """SELECT m.role, m.content, c.title
                   FROM messages m JOIN conversations c ON c.id = m.conversation_id
                   WHERE c.subproject_id = ? AND c.id <> ?
                   ORDER BY m.id DESC LIMIT ?""",
                (subproject_id, exclude_conversation_id or -1, limit),
            ).fetchall()
        return [dict(r) for r in reversed(rows)]

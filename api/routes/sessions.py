from __future__ import annotations
import asyncio
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage


class SessionStore:
    def __init__(self, db_path: str = ".ontopilot.db"):
        self._db_path = db_path
        self._queues: dict[str, asyncio.Queue] = {}
        self._init_db()
        self._sessions: dict[str, dict] = self._load_all()

    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT,
                    role TEXT,
                    warehouse_id TEXT,
                    title TEXT,
                    pending_action TEXT,
                    messages TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
            """)

    def _load_all(self) -> dict[str, dict]:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM sessions").fetchall()
        sessions = {}
        for r in rows:
            sessions[r["id"]] = {
                "user_id": r["user_id"],
                "role": r["role"],
                "warehouse_id": r["warehouse_id"],
                "title": r["title"],
                "pending_action": json.loads(r["pending_action"]) if r["pending_action"] else None,
                "messages": json.loads(r["messages"]) if r["messages"] else [],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
            }
        return sessions

    def _persist(self, session_id: str) -> None:
        s = self._sessions[session_id]
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """INSERT INTO sessions
                    (id, user_id, role, warehouse_id, title, pending_action, messages, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET
                    user_id=excluded.user_id, role=excluded.role, warehouse_id=excluded.warehouse_id,
                    title=excluded.title, pending_action=excluded.pending_action,
                    messages=excluded.messages, updated_at=excluded.updated_at""",
                (
                    session_id, s["user_id"], s["role"], s["warehouse_id"], s.get("title"),
                    json.dumps(s["pending_action"]) if s.get("pending_action") is not None else None,
                    json.dumps(s.get("messages", [])),
                    s["created_at"], s["updated_at"],
                ),
            )

    def create_session(self, user_id: str, role: str, warehouse_id: str) -> str:
        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        self._sessions[session_id] = {
            "user_id": user_id,
            "role": role,
            "warehouse_id": warehouse_id,
            "messages": [],
            "pending_action": None,
            "title": None,
            "created_at": now,
            "updated_at": now,
        }
        self._queues[session_id] = asyncio.Queue()
        self._persist(session_id)
        return session_id

    def get(self, session_id: str) -> dict | None:
        return self._sessions.get(session_id)

    def update(self, session_id: str, **kwargs) -> None:
        if session_id in self._sessions:
            self._sessions[session_id].update(kwargs)
            self._sessions[session_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._persist(session_id)

    def add_message(self, session_id: str, role: str, content: str) -> None:
        session = self._sessions.get(session_id)
        if not session:
            return
        session.setdefault("messages", []).append({
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        session["updated_at"] = datetime.now(timezone.utc).isoformat()
        # Set title from first user message
        if role == "human" and not session.get("title"):
            session["title"] = content[:80] + ("…" if len(content) > 80 else "")
        self._persist(session_id)

    def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
        self._queues.pop(session_id, None)
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))

    def get_history(self, session_id: str) -> list[BaseMessage]:
        """Reconstruct BaseMessage list from stored message dicts."""
        session = self._sessions.get(session_id)
        if not session:
            return []
        msgs = []
        for m in session.get("messages", []):
            if m["role"] == "human":
                msgs.append(HumanMessage(content=m["content"]))
            elif m["role"] == "ai":
                msgs.append(AIMessage(content=m["content"]))
        return msgs[-20:]

    def list_summaries(self) -> list[dict]:
        """Return summary of all sessions for the session list API."""
        result = []
        for sid, s in self._sessions.items():
            msgs = s.get("messages", [])
            result.append({
                "id": sid,
                "title": s.get("title") or "新对话",
                "created_at": s.get("created_at", ""),
                "updated_at": s.get("updated_at", ""),
                "message_count": len(msgs),
                "user_id": s.get("user_id", ""),
                "role": s.get("role", ""),
            })
        # Most recent first
        result.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        return result

    def get_session_messages(self, session_id: str) -> list[dict]:
        """Return serializable messages for a session."""
        session = self._sessions.get(session_id)
        if not session:
            return []
        return session.get("messages", [])

    def get_queue(self, session_id: str) -> asyncio.Queue | None:
        if session_id not in self._queues and session_id in self._sessions:
            self._queues[session_id] = asyncio.Queue()
        return self._queues.get(session_id)

    def push_event(self, session_id: str, event: dict) -> None:
        q = self._queues.get(session_id)
        if q:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass


session_store = SessionStore()
router = APIRouter()


@router.get("/sessions")
async def list_sessions() -> dict:
    return {"sessions": session_store.list_summaries()}


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str) -> dict:
    session = session_store.get(session_id)
    if not session:
        return {"status": "error", "message": "Session not found"}
    session_store.delete(session_id)
    return {"status": "ok", "message": "会话已删除"}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str) -> dict:
    session = session_store.get(session_id)
    if not session:
        return {"session": None}
    return {
        "session": {
            "id": session_id,
            "title": session.get("title") or "新对话",
            "created_at": session.get("created_at", ""),
            "updated_at": session.get("updated_at", ""),
            "user_id": session.get("user_id", ""),
            "role": session.get("role", ""),
            "messages": session.get("messages", []),
        }
    }

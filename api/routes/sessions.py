from __future__ import annotations
import asyncio
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage


class SessionStore:
    def __init__(self):
        self._sessions: dict[str, dict] = {}
        self._queues: dict[str, asyncio.Queue] = {}

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
        return session_id

    def get(self, session_id: str) -> dict | None:
        return self._sessions.get(session_id)

    def update(self, session_id: str, **kwargs) -> None:
        if session_id in self._sessions:
            self._sessions[session_id].update(kwargs)
            self._sessions[session_id]["updated_at"] = datetime.now(timezone.utc).isoformat()

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
    del session_store._sessions[session_id]
    session_store._queues.pop(session_id, None)
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

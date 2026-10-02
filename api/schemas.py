from __future__ import annotations
from pydantic import BaseModel
from typing import Any


class ChatRequest(BaseModel):
    session_id: str | None = None
    context_id: str = ""
    message: str
    confirmed: bool = False
    model_id: str | None = None
    ontology_id: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    response: str
    turn_id: str
    awaiting_confirmation: bool
    pending_action: dict | None
    trace_events: list[dict[str, Any]]


class AuditEntry(BaseModel):
    id: str
    timestamp: str
    user_id: str
    operation: str
    object_type: str | None
    object_id: str | None
    params: str
    result: str
    permission_result: str

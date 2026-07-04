from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class TraceEvent:
    id: str
    conversation_id: str
    turn_id: str
    timestamp: datetime
    layer: str           # context | query | logic | action | governance | simulation | response
    name: str
    status: str          # started | success | failed | denied | pending_confirmation
    input_summary: dict[str, Any]
    output_summary: dict[str, Any]
    permission_result: str  # pass | deny | not_applicable
    duration_ms: int
    audit_id: str | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "turn_id": self.turn_id,
            "timestamp": self.timestamp.isoformat(),
            "layer": self.layer,
            "name": self.name,
            "status": self.status,
            "input_summary": self.input_summary,
            "output_summary": self.output_summary,
            "permission_result": self.permission_result,
            "duration_ms": self.duration_ms,
            "audit_id": self.audit_id,
            "error": self.error,
        }


class TraceRecorder:
    def __init__(self, conversation_id: str):
        self.conversation_id = conversation_id
        self._events: dict[str, list[TraceEvent]] = {}

    def record(self, event: TraceEvent) -> None:
        self._events.setdefault(event.turn_id, []).append(event)

    def get_events(self, turn_id: str) -> list[TraceEvent]:
        return list(self._events.get(turn_id, []))

    def get_all_events(self) -> list[TraceEvent]:
        result = []
        for events in self._events.values():
            result.extend(events)
        return result

    def flush(self, turn_id: str) -> None:
        self._events.pop(turn_id, None)

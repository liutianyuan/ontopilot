import tempfile, os
from datetime import datetime, timezone
from ontopilot.trace import TraceEvent, TraceRecorder
from ontopilot.audit import AuditLogger


def test_trace_recorder_stores_and_retrieves():
    rec = TraceRecorder(conversation_id="conv-1")
    event = TraceEvent(
        id="evt-1", conversation_id="conv-1", turn_id="turn-1",
        timestamp=datetime.now(timezone.utc), layer="query", name="object_query:Shipment",
        status="success", input_summary={"object_type": "Shipment"},
        output_summary={"result_count": 3}, permission_result="pass",
        duration_ms=50
    )
    rec.record(event)
    events = rec.get_events("turn-1")
    assert len(events) == 1
    assert events[0].name == "object_query:Shipment"


def test_trace_flush_clears_turn():
    rec = TraceRecorder(conversation_id="conv-1")
    event = TraceEvent(
        id="evt-2", conversation_id="conv-1", turn_id="turn-2",
        timestamp=datetime.now(timezone.utc), layer="action", name="preview_action:assignCarrier",
        status="pending_confirmation", input_summary={}, output_summary={},
        permission_result="pass", duration_ms=10
    )
    rec.record(event)
    rec.flush("turn-2")
    assert rec.get_events("turn-2") == []


def test_audit_logger_writes_and_reads():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        logger = AuditLogger(db_path)
        audit_id = logger.log(
            user_id="dispatcher_001", operation="query",
            object_type="Shipment", object_id=None,
            params={"filters": {"status": "delayed"}},
            result={"count": 7}, permission_result="pass"
        )
        assert audit_id.startswith("audit_")
        entries = logger.get_entries(user_id="dispatcher_001")
        assert len(entries) == 1
        assert entries[0]["operation"] == "query"
    finally:
        os.unlink(db_path)

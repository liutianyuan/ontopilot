import tempfile, pytest
from ontopilot.schema import SchemaRegistry
from ontopilot.store import ObjectStore
from ontopilot.governance import PermissionEvaluator
from ontopilot.actions import ActionExecutor

SCHEMA_PATH = "config/ontology_schema.yaml"
SEED_PATH = "config/seed_data.yaml"
PERMISSIONS_PATH = "config/permissions.yaml"


def make_executor(tmp_path):
    schema = SchemaRegistry(SCHEMA_PATH)
    store = ObjectStore(str(tmp_path / "test.db"), schema)
    store.load_seed_data(SEED_PATH)
    pe = PermissionEvaluator(PERMISSIONS_PATH)
    return ActionExecutor(schema, store, pe), store


def test_preview_assign_carrier(tmp_path):
    executor, _ = make_executor(tmp_path)
    preview = executor.preview("dispatcher", "assignCarrier", {
        "shipmentId": "SH-0042",
        "newCarrierId": "CARRIER-B",
        "reason": "降低延误风险",
    })
    assert preview["status"] == "pending_confirmation"
    assert preview["action"] == "assignCarrier"
    assert preview["target"] == "Shipment:SH-0042"
    assert any(c["field"] == "carrierId" for c in preview["changes"])
    assert preview["requires_confirmation"] is True


def test_execute_assign_carrier_without_confirmation_raises(tmp_path):
    executor, _ = make_executor(tmp_path)
    with pytest.raises(PermissionError):
        executor.execute("dispatcher", "dispatcher_001", "assignCarrier", {
            "shipmentId": "SH-0042",
            "newCarrierId": "CARRIER-B",
            "reason": "test",
        }, confirmed=False)


def test_execute_assign_carrier_with_confirmation(tmp_path):
    executor, store = make_executor(tmp_path)
    result = executor.execute("dispatcher", "dispatcher_001", "assignCarrier", {
        "shipmentId": "SH-0042",
        "newCarrierId": "CARRIER-B",
        "reason": "降低延误风险",
    }, confirmed=True)
    assert result["status"] == "executed"
    updated = store.get("Shipment", "SH-0042")
    assert updated["carrierId"] == "CARRIER-B"


def test_execute_update_eta_no_confirmation_needed(tmp_path):
    executor, store = make_executor(tmp_path)
    result = executor.execute("dispatcher", "dispatcher_001", "updateETA", {
        "shipmentId": "SH-0042",
        "newETA": "2026-06-24T10:00:00+00:00",
        "reason": "重新排程",
    }, confirmed=False)
    assert result["status"] == "executed"
    updated = store.get("Shipment", "SH-0042")
    assert updated["ETA"] == "2026-06-24T10:00:00+00:00"


def test_create_exception_case(tmp_path):
    executor, store = make_executor(tmp_path)
    result = executor.execute("dispatcher", "dispatcher_001", "createExceptionCase", {
        "shipmentId": "SH-0042",
        "reason": "VIP客户严重延误",
        "priority": "high",
    }, confirmed=True)
    assert result["status"] == "executed"
    cases = store.query("ExceptionCase", {"shipmentId": "SH-0042"}, None)
    assert len(cases) == 1
    assert cases[0]["priority"] == "high"


def test_preview_shows_field_changes(tmp_path):
    executor, _ = make_executor(tmp_path)
    preview = executor.preview("dispatcher", "updateETA", {
        "shipmentId": "SH-0042",
        "newETA": "2026-06-24T10:00:00+00:00",
        "reason": "重新排程",
    })
    changes = preview["changes"]
    assert any(c["field"] == "ETA" for c in changes)
    eta_change = next(c for c in changes if c["field"] == "ETA")
    assert eta_change["to"] == "2026-06-24T10:00:00+00:00"

import tempfile, os, pytest
from ontopilot.schema import SchemaRegistry
from ontopilot.store import ObjectStore

SCHEMA_PATH = "config/ontology_schema.yaml"
SEED_PATH = "config/seed_data.yaml"


@pytest.fixture
def store(tmp_path):
    db = str(tmp_path / "test.db")
    schema = SchemaRegistry(SCHEMA_PATH)
    s = ObjectStore(db, schema)
    s.load_seed_data(SEED_PATH)
    return s


def test_load_seed_shipments(store):
    shipments = store.query("Shipment", {}, None)
    assert len(shipments) == 30


def test_get_specific_object(store):
    obj = store.get("Shipment", "SH-0042")
    assert obj is not None
    assert obj["shipmentId"] == "SH-0042"
    assert obj["status"] == "delayed"


def test_get_missing_object_returns_none(store):
    assert store.get("Shipment", "SH-9999") is None


def test_query_with_eq_filter(store):
    delayed = store.query("Shipment", {"status": "delayed"}, None)
    assert len(delayed) >= 7
    assert all(s["status"] == "delayed" for s in delayed)


def test_query_with_in_filter(store):
    results = store.query("Shipment", {"status": ["delayed", "in_transit"]}, None)
    assert all(s["status"] in ("delayed", "in_transit") for s in results)


def test_query_with_property_projection(store):
    results = store.query("Shipment", {"status": "delayed"}, ["shipmentId", "status"])
    assert all(set(r.keys()) == {"shipmentId", "status"} for r in results)


def test_count(store):
    n = store.count("Shipment", {"status": "delayed"})
    assert n >= 7


def test_update_object(store):
    updated = store.update("Shipment", "SH-0042", {"status": "in_transit"})
    assert updated["status"] == "in_transit"
    reloaded = store.get("Shipment", "SH-0042")
    assert reloaded["status"] == "in_transit"


def test_create_object(store):
    case = store.create("ExceptionCase", {
        "caseId": "CASE-001",
        "shipmentId": "SH-0042",
        "reason": "严重延误",
        "priority": "high",
        "status": "open",
        "createdBy": "dispatcher_001",
        "createdAt": "2026-06-23T10:00:00+00:00",
    })
    assert case["caseId"] == "CASE-001"
    assert store.get("ExceptionCase", "CASE-001") is not None


def test_traverse_link(store):
    orders = store.traverse("Shipment", "SH-0042", "belongsTo", None)
    assert len(orders) == 1
    assert orders[0]["orderId"] == "ORD-001"


def test_fork_isolation(store):
    forked = store.fork()
    forked.update("Shipment", "SH-0042", {"status": "delivered"})
    original = store.get("Shipment", "SH-0042")
    assert original["status"] == "delayed"  # original unchanged

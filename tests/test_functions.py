import tempfile
from datetime import datetime, timezone
from ontopilot.schema import SchemaRegistry
from ontopilot.store import ObjectStore
from ontopilot.functions import FunctionRegistry

SCHEMA_PATH = "config/ontology_schema.yaml"
SEED_PATH = "config/seed_data.yaml"


def make_registry(tmp_path):
    schema = SchemaRegistry(SCHEMA_PATH)
    store = ObjectStore(str(tmp_path / "test.db"), schema)
    store.load_seed_data(SEED_PATH)
    return FunctionRegistry(schema, store)


def test_sh0042_is_high_risk(tmp_path):
    """SH-0042: delayed + ETA past + CARRIER-A delayRate=0.22 + urgent order = 100"""
    reg = make_registry(tmp_path)
    results = reg.call("calculateDelayRisk", {"shipmentIds": ["SH-0042"]})
    assert len(results) == 1
    r = results[0]
    assert r["shipmentId"] == "SH-0042"
    assert r["riskLevel"] == "high"
    assert r["riskScore"] >= 70


def test_risk_score_formula(tmp_path):
    """SH-0042 should score exactly: delayed(40) + ETA past(25) + delayRate>15%(20) + urgent(15) = 100"""
    reg = make_registry(tmp_path)
    results = reg.call("calculateDelayRisk", {"shipmentIds": ["SH-0042"]})
    assert results[0]["riskScore"] == 100


def test_multiple_shipments(tmp_path):
    reg = make_registry(tmp_path)
    results = reg.call("calculateDelayRisk", {"shipmentIds": ["SH-0042", "SH-0119"]})
    assert len(results) == 2


def test_unknown_function_raises(tmp_path):
    reg = make_registry(tmp_path)
    try:
        reg.call("nonExistentFunction", {})
        assert False, "Should have raised"
    except KeyError:
        pass


def test_delivered_shipment_is_low_risk(tmp_path):
    reg = make_registry(tmp_path)
    results = reg.call("calculateDelayRisk", {"shipmentIds": ["SH-0401"]})
    assert results[0]["riskLevel"] == "low"

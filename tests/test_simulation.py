from datetime import datetime, timezone, timedelta
from ontopilot.schema import SchemaRegistry
from ontopilot.store import ObjectStore
from ontopilot.functions import FunctionRegistry
from ontopilot.simulation import SingleStepSimulator

SCHEMA_PATH = "config/ontology_schema.yaml"
SEED_PATH = "config/seed_data.yaml"


def make_simulator(tmp_path):
    schema = SchemaRegistry(SCHEMA_PATH)
    store = ObjectStore(str(tmp_path / "test.db"), schema)
    store.load_seed_data(SEED_PATH)
    functions = FunctionRegistry(schema, store)
    return SingleStepSimulator(schema, store, functions), store


def test_compare_two_options(tmp_path):
    sim, _ = make_simulator(tmp_path)
    results = sim.compare("SH-0042", [
        {"name": "方案A：换承运商B", "action": "assignCarrier", "params": {"newCarrierId": "CARRIER-B"}},
        {"name": "方案B：调整ETA", "action": "updateETA", "params": {"newETA": "2026-06-24T12:00:00+00:00"}},
    ])
    assert len(results) == 2
    assert results[0]["option_name"] in ("方案A：换承运商B", "方案B：调整ETA")


def test_assign_carrier_kpi(tmp_path):
    sim, _ = make_simulator(tmp_path)
    results = sim.compare("SH-0042", [
        {"name": "换CARRIER-B", "action": "assignCarrier", "params": {"newCarrierId": "CARRIER-B"}},
    ])
    outcome = results[0]["simulated_outcome"]
    assert "estimated_delivery" in outcome
    assert "cost_delta" in outcome
    assert "sla_met" in outcome
    assert "customer_risk" in outcome
    assert "delay_hours" in outcome
    assert outcome["cost_delta"] > 0


def test_fork_does_not_modify_original(tmp_path):
    sim, store = make_simulator(tmp_path)
    sim.compare("SH-0042", [
        {"name": "换CARRIER-B", "action": "assignCarrier", "params": {"newCarrierId": "CARRIER-B"}},
    ])
    original = store.get("Shipment", "SH-0042")
    assert original["carrierId"] == "CARRIER-A"


def test_customer_risk_vip_sla_miss(tmp_path):
    sim, _ = make_simulator(tmp_path)
    results = sim.compare("SH-0042", [
        {"name": "延迟ETA", "action": "updateETA",
         "params": {"newETA": "2026-07-01T12:00:00+00:00"}},
    ])
    outcome = results[0]["simulated_outcome"]
    if not outcome["sla_met"]:
        assert outcome["customer_risk"] == "high"

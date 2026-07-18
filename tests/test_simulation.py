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


LOGISTICS_SCHEMA_PATH = "config/logistics_ontology.yaml"
LOGISTICS_SEED_PATH = "config/logistics_seed.yaml"


def make_logistics_simulator(tmp_path):
    schema = SchemaRegistry(LOGISTICS_SCHEMA_PATH)
    store = ObjectStore(str(tmp_path / "logistics_test.db"), schema)
    store.load_seed_data(LOGISTICS_SEED_PATH)
    functions = FunctionRegistry(schema, store)
    return SingleStepSimulator(schema, store, functions), store


def test_involved_types_on_assign_carrier(tmp_path):
    sim, _ = make_logistics_simulator(tmp_path)
    results = sim.compare("SH-0001", [
        {"name": "换CARRIER-B", "action": "assignCarrier", "params": {"newCarrierId": "CARRIER-B"}},
    ])
    involved = results[0]["involved_types"]
    assert involved["mutated"] == ["Shipment"]
    assert involved["referenced"] == ["Carrier", "Customer", "Order", "Warehouse"]


def test_involved_types_on_update_eta(tmp_path):
    sim, _ = make_logistics_simulator(tmp_path)
    results = sim.compare("SH-0001", [
        {"name": "调整ETA", "action": "updateETA", "params": {"newETA": "2026-07-02T12:00:00+00:00"}},
    ])
    involved = results[0]["involved_types"]
    assert involved["mutated"] == ["Shipment"]
    assert involved["referenced"] == ["Carrier", "Customer", "Order", "Warehouse"]


def test_involved_types_consistent_across_multiple_options(tmp_path):
    sim, _ = make_logistics_simulator(tmp_path)
    results = sim.compare("SH-0001", [
        {"name": "方案A", "action": "assignCarrier", "params": {"newCarrierId": "CARRIER-B"}},
        {"name": "方案B", "action": "assignCarrier", "params": {"newCarrierId": "CARRIER-C"}},
    ])
    assert results[0]["involved_types"] == results[1]["involved_types"]

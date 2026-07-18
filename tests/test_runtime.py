import uuid
from ontopilot.runtime import OntologyRuntime


def make_turn():
    return str(uuid.uuid4())


def test_query_returns_delayed_shipments(runtime):
    turn_id = make_turn()
    results = runtime.query(
        user_id="dispatcher_001", role="dispatcher",
        object_type="Shipment",
        filters={"status": "delayed", "warehouseId": "WH-SC-001"},
        properties=["shipmentId", "status"],
        aggregation=None, turn_id=turn_id,
    )
    assert len(results) >= 7
    assert all(r["status"] == "delayed" for r in results)


def test_query_denied_for_unpermitted_type(runtime):
    turn_id = make_turn()
    try:
        runtime.query(
            user_id="dispatcher_001", role="dispatcher",
            object_type="Carrier", filters={}, properties=None,
            aggregation=None, turn_id=turn_id,
        )
        assert False, "Should have raised PermissionError"
    except PermissionError:
        pass


def test_query_generates_trace_event(runtime):
    turn_id = make_turn()
    runtime.query(
        user_id="dispatcher_001", role="dispatcher",
        object_type="Shipment", filters={"status": "delayed"},
        properties=None, aggregation=None, turn_id=turn_id,
    )
    events = runtime.get_trace_events(turn_id)
    assert len(events) >= 1
    assert any(e.layer == "query" for e in events)
    assert any(e.permission_result == "pass" for e in events)


def test_dispatcher_scope_filters_to_south(runtime):
    turn_id = make_turn()
    results = runtime.query(
        user_id="dispatcher_001", role="dispatcher",
        object_type="Shipment",
        filters={"status": "delayed"},
        properties=["shipmentId", "warehouseId"],
        aggregation=None, turn_id=turn_id,
    )
    warehouse_ids = {r["warehouseId"] for r in results}
    assert "WH-EC-001" not in warehouse_ids


def test_function_call_has_audit_and_trace(runtime):
    turn_id = make_turn()
    result = runtime.call_function(
        user_id="dispatcher_001", role="dispatcher",
        function_name="calculateDelayRisk",
        params={"shipmentIds": ["SH-0042"]},
        turn_id=turn_id,
    )
    assert result[0]["riskLevel"] == "high"
    events = runtime.get_trace_events(turn_id)
    assert any(e.layer == "logic" for e in events)


def test_preview_action_returns_pending_confirmation(runtime):
    turn_id = make_turn()
    preview = runtime.preview_action(
        user_id="dispatcher_001", role="dispatcher",
        action_name="assignCarrier",
        params={"shipmentId": "SH-0042", "newCarrierId": "CARRIER-B", "reason": "test"},
        turn_id=turn_id,
    )
    assert preview["status"] == "pending_confirmation"


def test_execute_action_without_confirmation_raises(runtime):
    turn_id = make_turn()
    try:
        runtime.execute_action(
            user_id="dispatcher_001", role="dispatcher",
            action_name="assignCarrier",
            params={"shipmentId": "SH-0042", "newCarrierId": "CARRIER-B", "reason": "test"},
            confirmed=False, turn_id=turn_id,
        )
        assert False
    except PermissionError:
        pass


def test_execute_action_with_confirmation_succeeds(runtime):
    turn_id = make_turn()
    result = runtime.execute_action(
        user_id="dispatcher_001", role="dispatcher",
        action_name="assignCarrier",
        params={"shipmentId": "SH-0042", "newCarrierId": "CARRIER-B", "reason": "test"},
        confirmed=True, turn_id=turn_id,
    )
    assert result["status"] == "executed"


def test_query_nonexistent_object(runtime):
    turn_id = make_turn()
    results = runtime.query(
        user_id="dispatcher_001", role="dispatcher",
        object_type="Shipment",
        filters={"shipmentId": "SH-9999"},
        properties=None, aggregation=None, turn_id=turn_id,
    )
    assert results == []


def make_logistics_runtime(tmp_path):
    return OntologyRuntime.from_config(
        "config",
        str(tmp_path / "logistics_runtime_test.db"),
        schema_path="config/logistics_ontology.yaml",
        seed_path="config/logistics_seed.yaml",
        permissions_path="config/logistics_permissions.yaml",
    )


def test_simulate_records_involved_types_in_trace(tmp_path):
    runtime = make_logistics_runtime(tmp_path)
    runtime.simulate(
        user_id="admin_001", role="admin", shipment_id="SH-0001",
        options=[{"name": "换CARRIER-B", "action": "assignCarrier", "params": {"newCarrierId": "CARRIER-B"}}],
        turn_id="test-turn-1",
    )
    trace = runtime.get_trace_events("test-turn-1")
    sim_events = [e for e in trace if e.layer == "simulation"]
    assert len(sim_events) == 1
    involved = sim_events[0].output_summary["involved_types"]
    assert involved["mutated"] == ["Shipment"]
    assert involved["referenced"] == ["Carrier", "Customer", "Order", "Warehouse"]


def test_call_function_compare_decisions_tags_simulation_layer(tmp_path):
    runtime = make_logistics_runtime(tmp_path)
    runtime.call_function(
        user_id="admin_001", role="admin", function_name="compareDecisions",
        params={
            "shipmentId": "SH-0001",
            "options": [{"name": "换CARRIER-B", "action": "assignCarrier", "params": {"newCarrierId": "CARRIER-B"}}],
        },
        turn_id="test-turn-3",
    )
    trace = runtime.get_trace_events("test-turn-3")
    sim_events = [e for e in trace if e.layer == "simulation"]
    assert len(sim_events) == 1
    involved = sim_events[0].output_summary["involved_types"]
    assert involved["mutated"] == ["Shipment"]
    assert involved["referenced"] == ["Carrier", "Customer", "Order", "Warehouse"]


def test_call_function_other_functions_stay_logic_layer(tmp_path):
    runtime = make_logistics_runtime(tmp_path)
    runtime.call_function(
        user_id="admin_001", role="admin", function_name="calculateDelayRisk",
        params={"shipmentIds": ["SH-0001"]}, turn_id="test-turn-4",
    )
    trace = runtime.get_trace_events("test-turn-4")
    assert len(trace) == 1
    assert trace[0].layer == "logic"
    assert "involved_types" not in trace[0].output_summary

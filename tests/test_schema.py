import pytest
from ontopilot.schema import SchemaRegistry


SCHEMA_PATH = "config/ontology_schema.yaml"


def test_loads_all_object_types():
    reg = SchemaRegistry(SCHEMA_PATH)
    assert set(reg.object_type_names) == {
        "Shipment", "Order", "Customer", "Carrier", "Warehouse", "ExceptionCase"
    }


def test_shipment_primary_key():
    reg = SchemaRegistry(SCHEMA_PATH)
    ot = reg.get_object_type("Shipment")
    assert ot.primary_key == "shipmentId"


def test_shipment_links():
    reg = SchemaRegistry(SCHEMA_PATH)
    ot = reg.get_object_type("Shipment")
    assert "belongsTo" in ot.links
    assert ot.links["belongsTo"].target == "Order"
    assert ot.links["belongsTo"].foreign_key == "orderId"


def test_action_assign_carrier():
    reg = SchemaRegistry(SCHEMA_PATH)
    action = reg.get_action("assignCarrier")
    assert action.requires_confirmation is True
    assert action.edits == {"carrierId": "newCarrierId"}
    assert action.creates is False


def test_action_create_exception_case():
    reg = SchemaRegistry(SCHEMA_PATH)
    action = reg.get_action("createExceptionCase")
    assert action.creates is True


def test_unknown_object_type_raises():
    reg = SchemaRegistry(SCHEMA_PATH)
    with pytest.raises(KeyError):
        reg.get_object_type("NonExistent")


def test_function_calculate_delay_risk():
    reg = SchemaRegistry(SCHEMA_PATH)
    fn = reg.get_function("calculateDelayRisk")
    assert fn.permission == "calculateDelayRisk"

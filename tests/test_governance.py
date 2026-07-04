from ontopilot.governance import PermissionEvaluator

PERMISSIONS_PATH = "config/permissions.yaml"


def test_dispatcher_can_query_shipment():
    pe = PermissionEvaluator(PERMISSIONS_PATH)
    assert pe.can_query("dispatcher", "Shipment") is True


def test_dispatcher_cannot_query_carrier():
    pe = PermissionEvaluator(PERMISSIONS_PATH)
    assert pe.can_query("dispatcher", "Carrier") is False


def test_dispatcher_cannot_query_customer():
    pe = PermissionEvaluator(PERMISSIONS_PATH)
    assert pe.can_query("dispatcher", "Customer") is False


def test_manager_can_query_carrier():
    pe = PermissionEvaluator(PERMISSIONS_PATH)
    assert pe.can_query("regional_manager", "Carrier") is True


def test_dispatcher_can_call_calculate_delay_risk():
    pe = PermissionEvaluator(PERMISSIONS_PATH)
    assert pe.can_call_function("dispatcher", "calculateDelayRisk") is True


def test_dispatcher_cannot_call_recommend_carrier():
    pe = PermissionEvaluator(PERMISSIONS_PATH)
    assert pe.can_call_function("dispatcher", "recommendCarrier") is False


def test_manager_can_call_compare_decisions():
    pe = PermissionEvaluator(PERMISSIONS_PATH)
    assert pe.can_call_function("regional_manager", "compareDecisions") is True


def test_dispatcher_assign_carrier_requires_confirmation():
    pe = PermissionEvaluator(PERMISSIONS_PATH)
    assert pe.get_action_confirmation("dispatcher", "assignCarrier") is True


def test_manager_assign_carrier_no_confirmation():
    pe = PermissionEvaluator(PERMISSIONS_PATH)
    assert pe.get_action_confirmation("regional_manager", "assignCarrier") is False


def test_dispatcher_data_scope():
    pe = PermissionEvaluator(PERMISSIONS_PATH)
    scope = pe.get_data_scope("dispatcher")
    assert scope.get("Warehouse.region") == ["华南"]


def test_manager_data_scope():
    pe = PermissionEvaluator(PERMISSIONS_PATH)
    scope = pe.get_data_scope("regional_manager")
    assert set(scope.get("Warehouse.region")) == {"华南", "华东"}


def test_unknown_role_raises():
    pe = PermissionEvaluator(PERMISSIONS_PATH)
    assert pe.can_query("unknown_role", "Shipment") is False

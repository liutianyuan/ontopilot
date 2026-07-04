import tempfile
from ontopilot.schema import SchemaRegistry
from ontopilot.store import ObjectStore
from ontopilot.governance import PermissionEvaluator
from ontopilot.context import ContextBuilder

SCHEMA_PATH = "config/ontology_schema.yaml"
SEED_PATH = "config/seed_data.yaml"
PERMISSIONS_PATH = "config/permissions.yaml"
CONTEXT_SOURCES_PATH = "config/context_sources.yaml"


def make_store(tmp_path):
    schema = SchemaRegistry(SCHEMA_PATH)
    store = ObjectStore(str(tmp_path / "test.db"), schema)
    store.load_seed_data(SEED_PATH)
    return store


def test_context_includes_warehouse_info(tmp_path):
    store = make_store(tmp_path)
    pe = PermissionEvaluator(PERMISSIONS_PATH)
    cb = ContextBuilder(CONTEXT_SOURCES_PATH, store, pe)
    ctx = cb.build("dispatcher_001", "dispatcher", "WH-SC-001")
    assert "WH-SC-001" in ctx
    assert "华南仓" in ctx


def test_context_includes_delayed_shipments(tmp_path):
    store = make_store(tmp_path)
    pe = PermissionEvaluator(PERMISSIONS_PATH)
    cb = ContextBuilder(CONTEXT_SOURCES_PATH, store, pe)
    ctx = cb.build("dispatcher_001", "dispatcher", "WH-SC-001")
    assert "SH-0042" in ctx


def test_context_excludes_other_warehouse(tmp_path):
    store = make_store(tmp_path)
    pe = PermissionEvaluator(PERMISSIONS_PATH)
    cb = ContextBuilder(CONTEXT_SOURCES_PATH, store, pe)
    ctx = cb.build("dispatcher_001", "dispatcher", "WH-SC-001")
    assert "SH-1001" not in ctx  # SH-1001 is in WH-EC-001

import json

import httpx

from ontopilot.nano_topic_provider import NanoObjectStore, NanoPermissionEvaluator, NanoSchemaRegistry, NanoTopicClient


MANIFEST = {
    "topic": {"id": "topic-1", "name": "设备运维", "domain": "制造"},
    "schema": {"object_types": [
        {"name": "Asset", "properties": ["id", "serial_number", "temperature"]},
    ], "relations": []},
    "rules": [{"executor_key": "temperatureLimit", "name": "温度阈值"}],
    "actions": [], "permissions": {"admin": {"query": "all", "rules": "published", "actions": "published"}},
}


def test_nano_store_passes_schema_fields_through_without_aliases():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/manifest"):
            return httpx.Response(200, json={"data": MANIFEST})
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={"data": [{
            "id": "asset-1", "serial_number": "SN-42", "temperature": 86,
        }]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = NanoTopicClient("http://nano/api/v1", "topic-1", token="token", client=client)
    schema = NanoSchemaRegistry(provider.manifest())
    store = NanoObjectStore(provider, schema)
    rows = store.query("Asset", {"serial_number": "SN-42"}, None)

    assert requests == [{"object_type": "Asset", "filters": {"serial_number": "SN-42"},
                         "properties": None, "aggregation": None}]
    assert rows == [{"id": "asset-1", "serial_number": "SN-42", "temperature": 86}]


def test_nano_permissions_keep_the_agent_interface_generic():
    governance = NanoPermissionEvaluator(MANIFEST)
    assert governance.can_query("admin", "Asset")
    assert governance.can_call_function("admin", "temperatureLimit")
    assert governance._role("admin")["actions"] == {}

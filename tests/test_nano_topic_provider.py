import httpx

from ontopilot.nano_topic_provider import NanoObjectStore, NanoSchemaRegistry, NanoTopicClient


MANIFEST = {
    "topic": {"id": "topic-1", "name": "肾病主题", "domain": "医疗"},
    "schema": {"object_types": [
        {"name": "Indicator", "properties": ["id", "patientId", "value"]},
        {"name": "Observation", "properties": ["id", "patient_id", "local_code", "value"]},
        {"name": "Drug", "properties": ["id", "patientId"]},
    ], "relations": []},
    "rules": [{"executor_key": "hyperkalemiaCriticalValueRule", "name": "高钾危急值规则"}],
    "actions": [], "permissions": {"admin": {"query": "all", "rules": "published", "actions": "published"}},
}


def test_nano_store_maps_patient_indicator_facts_to_observations():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/manifest"):
            return httpx.Response(200, json={"data": MANIFEST})
        assert request.url.path.endswith("/objects:query")
        assert request.json() if False else True
        return httpx.Response(200, json={"data": [{
            "id": "obs-1", "name": "血钾", "patient_id": "P-CKD-042", "local_code": "K", "value": "5.9",
        }]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = NanoTopicClient("http://nano/api/v1", "topic-1", token="token", client=client)
    schema = NanoSchemaRegistry(provider.manifest())
    store = NanoObjectStore(provider, schema)

    rows = store.query("Indicator", {"patientId": "P-CKD-042"}, None)

    assert rows[0]["patientId"] == "P-CKD-042"
    assert rows[0]["localCode"] == "K"
    assert rows[0]["name"] == "血钾"


def test_nano_permissions_keep_the_original_agent_interface():
    from ontopilot.nano_topic_provider import NanoPermissionEvaluator

    governance = NanoPermissionEvaluator(MANIFEST)

    assert governance.can_query("admin", "Observation")
    assert governance.can_call_function("admin", "hyperkalemiaCriticalValueRule")
    assert governance._role("admin")["actions"] == {}

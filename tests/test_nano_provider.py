import json

import httpx

from ontopilot.nano_provider import NanoOntologyProvider


def test_provider_loads_v11_and_runs_confirmation_flow():
    def handler(request: httpx.Request):
        path = request.url.path
        if path.endswith("/auth/login"):
            return httpx.Response(200, json={"data": {"access_token": "token"}})
        assert request.headers["authorization"] == "Bearer token"
        if path.endswith("/schema/bundle"):
            return httpx.Response(200, json={"data": {"metadata": {"ontology_id": "onto-1", "version": "v1.1"},
                "types": [{"name_en": "Patient"}, {"name_en": "Observation"}], "relations": [], "rules": [], "actions": []}})
        if path.endswith("/clinical-runtime/patients/P-1/summary"):
            return httpx.Response(200, json={"data": {"patient_id": "P-1", "facts": []}})
        if path.endswith("/preview"):
            return httpx.Response(200, json={"data": {"confirmation_id": "C-1", "status": "pending"}})
        if path.endswith("/confirmations/C-1/decision"):
            assert json.loads(request.content)["approved"] is True
            return httpx.Response(200, json={"data": {"status": "approved", "action_run": {"id": "R-1"}}})
        raise AssertionError(path)

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://nano")
    provider = NanoOntologyProvider("http://nano/api/v1", "onto-1", username="admin", password="pw", client=client)

    assert provider.schema().type_names == ["Patient", "Observation"]
    assert provider.patient_summary("P-1")["patient_id"] == "P-1"
    assert provider.preview_alert_action("A-1")["confirmation_id"] == "C-1"
    assert provider.decide("C-1", True)["action_run"]["id"] == "R-1"


def test_provider_rejects_wrong_schema_version():
    def handler(request: httpx.Request):
        return httpx.Response(200, json={"data": {"metadata": {"ontology_id": "onto-1", "version": "v1.0"}, "types": []}})
    provider = NanoOntologyProvider("http://nano", "onto-1", token="t",
                                    client=httpx.Client(transport=httpx.MockTransport(handler)))
    try:
        provider.schema()
    except RuntimeError as exc:
        assert "expected v1.1" in str(exc)
    else:
        raise AssertionError("version mismatch must fail")

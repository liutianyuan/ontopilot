from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class NanoSchemaAdapter:
    bundle: dict[str, Any]

    @property
    def version(self) -> str:
        return self.bundle["metadata"]["version"]

    @property
    def ontology_id(self) -> str:
        return self.bundle["metadata"]["ontology_id"]

    @property
    def type_names(self) -> list[str]:
        return [item["name_en"] for item in self.bundle.get("types", [])]

    def ensure_compatible(self, expected_version: str) -> None:
        if self.version != expected_version:
            raise RuntimeError(f"nano Schema version mismatch: expected {expected_version}, got {self.version}")


class NanoOntologyProvider:
    def __init__(self, base_url: str, ontology_id: str, *, token: str | None = None,
                 username: str | None = None, password: str | None = None,
                 client: httpx.Client | None = None):
        self.base_url = base_url.rstrip("/")
        self.ontology_id = ontology_id
        self._token = token
        self._username = username
        self._password = password
        self._client = client or httpx.Client(timeout=15, trust_env=False)

    def _headers(self) -> dict[str, str]:
        if not self._token:
            if not self._username or not self._password:
                raise RuntimeError("nano credentials are not configured")
            response = self._client.post(f"{self.base_url}/auth/login", json={
                "username": self._username, "password": self._password,
            })
            response.raise_for_status()
            self._token = response.json()["data"]["access_token"]
        return {"Authorization": f"Bearer {self._token}"}

    def _request(self, method: str, path: str, **kwargs) -> Any:
        response = self._client.request(method, f"{self.base_url}{path}", headers=self._headers(), **kwargs)
        if response.status_code == 401 and self._username:
            self._token = None
            response = self._client.request(method, f"{self.base_url}{path}", headers=self._headers(), **kwargs)
        response.raise_for_status()
        return response.json()["data"]

    def schema(self, expected_version: str = "v1.1") -> NanoSchemaAdapter:
        adapter = NanoSchemaAdapter(self._request("GET", f"/ontologies/{self.ontology_id}/schema/bundle"))
        adapter.ensure_compatible(expected_version)
        return adapter

    def patient_summary(self, patient_id: str) -> dict:
        return self._request("GET", f"/ontologies/{self.ontology_id}/clinical-runtime/patients/{patient_id}/summary")

    def patient_timeline(self, patient_id: str) -> list[dict]:
        return self._request("GET", f"/ontologies/{self.ontology_id}/clinical-runtime/patients/{patient_id}/timeline")

    def alerts(self, patient_id: str | None = None, status: str | None = None) -> list[dict]:
        params = {key: value for key, value in {"patient_id": patient_id, "status": status}.items() if value}
        return self._request("GET", f"/ontologies/{self.ontology_id}/clinical-runtime/alerts", params=params)

    def preview_alert_action(self, alert_id: str) -> dict:
        return self._request("POST", f"/ontologies/{self.ontology_id}/clinical-runtime/alerts/{alert_id}/preview")

    def decide(self, confirmation_id: str, approved: bool) -> dict:
        return self._request("POST", f"/ontologies/{self.ontology_id}/clinical-runtime/confirmations/{confirmation_id}/decision",
                             json={"approved": approved})

    def action_run(self, run_id: str) -> dict:
        return self._request("GET", f"/ontologies/{self.ontology_id}/clinical-runtime/action-runs/{run_id}")

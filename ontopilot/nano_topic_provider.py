"""Nano control-plane adapters for the unchanged Ontopilot runtime.

The adapters implement the small interfaces consumed by Ontopilot's original
runtime, schema and store components.  No YAML schema, seed or permission file
is read when a Nano topic is selected.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

import httpx

from ontopilot.schema import ActionDef, FunctionDef, LinkDef, ObjectTypeDef


class NanoTopicRequestError(RuntimeError):
    """A user-safe error returned by Nano's published topic API."""


class NanoTopicClient:
    def __init__(self, base_url: str, topic_id: str, token: str | None = None, client: httpx.Client | None = None):
        self.base_url = base_url.rstrip("/")
        self.topic_id = topic_id
        self.token = token
        self.client = client or httpx.Client(timeout=20, trust_env=False)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    def request(self, method: str, path: str, **kwargs) -> Any:
        response = self.client.request(method, f"{self.base_url}{path}", headers=self._headers(), **kwargs)
        if response.is_error:
            try:
                detail = response.json().get("detail")
            except ValueError:
                detail = None
            raise NanoTopicRequestError(str(detail or "知识主题运行服务请求失败"))
        return response.json()["data"]

    def manifest(self) -> dict[str, Any]:
        return self.request("GET", f"/agent-runtime/topics/{self.topic_id}/manifest")

    def identity(self) -> dict[str, Any]:
        """Resolve the caller identity from Nano, never from browser input."""
        return self.request("GET", "/agent-runtime/me")

    def query(self, object_type: str, filters: dict | None = None, properties: list | None = None,
              aggregation: str | None = None) -> list[dict] | int:
        data = self.request("POST", f"/agent-runtime/topics/{self.topic_id}/objects:query", json={
            "object_type": object_type, "filters": filters or {}, "properties": properties,
            "aggregation": aggregation,
        })
        return data["count"] if aggregation == "count" else data

    def traverse(self, entity_id: str, relation_type: str | None = None, direction: str = "out") -> list[dict]:
        return self.request("POST", f"/agent-runtime/topics/{self.topic_id}/graph:traverse", json={
            "entity_id": entity_id, "relation_type": relation_type, "direction": direction,
        })

    def preview_action(self, alert_id: str | None = None, action_name: str | None = None,
                       patient_id: str | None = None) -> dict:
        """Ask Nano to resolve the actionable alert from published context.

        Alert UUIDs are runtime internals.  The agent can use one when it has
        just queried an alert, but action name plus patient ID is the stable
        interface for a natural-language request.
        """
        return self.request("POST", f"/agent-runtime/topics/{self.topic_id}/actions:preview", json={
            "alert_id": alert_id,
            "action_name": action_name,
            "patient_id": patient_id,
        })

    def commit_action(self, confirmation_id: str, approved: bool) -> dict:
        return self.request("POST", f"/agent-runtime/topics/{self.topic_id}/actions:commit", json={
            "confirmation_id": confirmation_id, "approved": approved,
        })


@dataclass
class NanoSchemaRegistry:
    """Drop-in read-only schema registry populated from a Nano manifest."""
    manifest: dict[str, Any]

    def __post_init__(self):
        self._object_types: dict[str, ObjectTypeDef] = {}
        for raw in self.manifest.get("schema", {}).get("object_types", []):
            props = {name: {"type": "string", "required": False} for name in raw.get("properties", [])}
            props.setdefault("id", {"type": "string", "required": True, "primary_key": True})
            self._object_types[raw["name"]] = ObjectTypeDef(raw["name"], raw.get("description", ""), props, {})
        self._actions = {
            raw["name"]: ActionDef(raw["name"], raw.get("description", ""), {}, "", raw.get("requires_confirmation", True))
            for raw in self.manifest.get("actions", [])
        }
        self._functions = {
            raw["executor_key"]: FunctionDef(raw["executor_key"], raw.get("description", ""), {}, "object", "published")
            for raw in self.manifest.get("rules", []) if raw.get("executor_key")
        }

    def get_object_type(self, name: str) -> ObjectTypeDef:
        return self._object_types[name]

    def get_action(self, name: str) -> ActionDef:
        return self._actions[name]

    def get_function(self, name: str) -> FunctionDef:
        return self._functions[name]

    @property
    def object_type_names(self) -> list[str]:
        return list(self._object_types)

    @property
    def action_names(self) -> list[str]:
        return list(self._actions)

    @property
    def function_names(self) -> list[str]:
        return list(self._functions)


class NanoObjectStore:
    """Remote implementation of Ontopilot's ObjectStore query contract."""
    def __init__(self, client: NanoTopicClient, schema: NanoSchemaRegistry):
        self._client, self._schema = client, schema

    @staticmethod
    def _topic_type(object_type: str, filters: dict | None) -> str:
        # Existing Ontopilot nephrology functions model patient facts as
        # Indicator/Drug. Nano stores them as immutable Observation/MedicationOrder.
        patient_scoped = any(key in (filters or {}) for key in ("patientId", "patient_id"))
        if patient_scoped and object_type == "Indicator":
            return "Observation"
        if patient_scoped and object_type == "Drug":
            return "MedicationOrder"
        return object_type

    @staticmethod
    def _normalize(item: dict[str, Any]) -> dict[str, Any]:
        result = dict(item)
        aliases = {"patient_id": "patientId", "encounter_id": "encounterId", "local_code": "localCode",
                   "occurred_at": "occurredAt", "drug_name": "name"}
        for source, target in aliases.items():
            if source in result and target not in result:
                result[target] = result[source]
        if result.get("localCode") == "EGFR":
            result.setdefault("name", "eGFR"); result.setdefault("nameCn", "估算肾小球滤过率")
        if result.get("localCode") == "K":
            result.setdefault("name", "血钾"); result.setdefault("nameCn", "血钾")
        return result

    def get(self, object_type: str, object_id: str) -> dict | None:
        rows = self.query(object_type, {"id": object_id}, None)
        return rows[0] if rows else None

    def query(self, object_type: str, filters: dict | None, properties: list | None) -> list[dict]:
        rows = self._client.query(self._topic_type(object_type, filters), filters, properties)
        return [self._normalize(item) for item in rows]

    def count(self, object_type: str, filters: dict | None) -> int:
        return int(self._client.query(self._topic_type(object_type, filters), filters, None, "count"))

    def traverse(self, object_type: str, object_id: str, link_name: str, properties: list | None) -> list[dict]:
        rows = self._client.traverse(object_id, link_name)
        result = [self._normalize(row["entity"]) for row in rows]
        return [{key: item[key] for key in properties if key in item} for item in result] if properties else result

    def update(self, object_type: str, object_id: str, changes: dict) -> dict:
        raise RuntimeError("Nano topics are controlled by the action API; direct object updates are not allowed")

    def create(self, object_type: str, data: dict) -> dict:
        raise RuntimeError("Nano topics are controlled by the action API; direct object creation is not allowed")

    def fork(self):
        raise RuntimeError("Simulation snapshots are not enabled for remote Nano topics")


class NanoPermissionEvaluator:
    def __init__(self, manifest: dict[str, Any]):
        self._policy = manifest.get("permissions", {})
        self._object_types = [item["name"] for item in manifest.get("schema", {}).get("object_types", [])]
        self._functions = [item["executor_key"] for item in manifest.get("rules", []) if item.get("executor_key")]
        self._actions = [item["name"] for item in manifest.get("actions", [])]

    def _role(self, role: str) -> dict:
        policy = self._policy.get(role, self._policy.get("viewer", {}))
        return {
            # Keep Ontopilot's original PermissionEvaluator shape so its
            # unchanged Agent and PromptBuilder can consume this adapter.
            "query_types": self._object_types if policy.get("query") == "all" else [],
            "functions": self._functions if policy.get("rules") == "published" else [],
            "actions": {name: {} for name in self._actions} if policy.get("actions") == "published" else {},
            "data_scope": {},
        }

    def can_query(self, role: str, object_type: str) -> bool:
        return object_type in self._role(role)["query_types"]

    def can_call_function(self, role: str, function_name: str) -> bool:
        return function_name in self._role(role)["functions"]

    def can_execute_action(self, role: str, action_name: str) -> bool:
        return action_name in self._role(role)["actions"]

    def get_allowed_warehouse_regions(self, role: str) -> list[str]:
        return []

    def get_allowed_functions(self, role: str) -> list[str]:
        return self._role(role)["functions"]


class NanoContextBuilder:
    def __init__(self, manifest: dict[str, Any]):
        self.manifest = manifest

    def build(self, user_id: str, role: str, warehouse_id: str) -> str:
        topic = self.manifest["topic"]
        return "\n".join(["[CONTEXT]", f"用户: {user_id}", f"角色: {role}",
                          f"知识主题: {topic['name']}", f"领域: {topic.get('domain') or ''}",
                          f"可用对象类型: {', '.join(item['name'] for item in self.manifest['schema']['object_types'])}", "[/CONTEXT]"])


class NanoActionExecutor:
    """Keeps Ontopilot's preview/confirmation sequence while Nano writes state."""
    def __init__(self, client: NanoTopicClient, _schema: NanoSchemaRegistry, _governance: NanoPermissionEvaluator):
        self.client = client

    def preview(self, _role: str, action_name: str, params: dict) -> dict:
        alert_id = params.get("alert_id") or params.get("alertId")
        patient_id = params.get("patient_id") or params.get("patientId")
        try:
            preview = self.client.preview_action(str(alert_id) if alert_id else None, action_name, patient_id)
        except NanoTopicRequestError as exc:
            return {"status": "error", "changes": [], "error": str(exc)}
        return {"status": "pending_confirmation", "changes": [preview.get("preview", {})],
                "confirmation_id": preview.get("confirmation_id"), "preview": preview}

    def execute(self, _role: str, _user_id: str, action_name: str, params: dict, confirmed: bool) -> dict:
        preview = self.preview(_role, action_name, params)
        if preview.get("status") == "error" or not confirmed:
            return preview
        result = self.client.commit_action(str(preview["confirmation_id"]), True)
        return {"status": result.get("status"), "action": action_name, "result": result}

from __future__ import annotations
import yaml


class PermissionEvaluator:
    def __init__(self, permissions_path: str):
        with open(permissions_path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        self._roles: dict = raw.get("roles", {})

    def _role(self, role: str) -> dict:
        return self._roles.get(role, {})

    def can_query(self, role: str, object_type: str) -> bool:
        if role == "admin":
            return True
        return object_type in self._role(role).get("query_types", [])

    def can_call_function(self, role: str, function_name: str) -> bool:
        if role == "admin":
            return True
        return function_name in self._role(role).get("functions", [])

    def can_execute_action(self, role: str, action_name: str) -> bool:
        if role == "admin":
            return True
        return action_name in self._role(role).get("actions", {})

    def get_action_confirmation(self, role: str, action_name: str) -> bool:
        if role == "admin":
            return False
        actions = self._role(role).get("actions", {})
        action = actions.get(action_name, {})
        return action.get("requires_confirmation", False)

    def get_data_scope(self, role: str) -> dict[str, list[str]]:
        return self._role(role).get("data_scope", {})

    def get_allowed_warehouse_regions(self, role: str) -> list[str]:
        scope = self.get_data_scope(role)
        return scope.get("Warehouse.region", [])

    def get_allowed_functions(self, role: str) -> list[str]:
        return self._role(role).get("functions", [])

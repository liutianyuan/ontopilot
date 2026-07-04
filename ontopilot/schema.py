from __future__ import annotations
from dataclasses import dataclass, field
import yaml


@dataclass
class LinkDef:
    target: str
    foreign_key: str


@dataclass
class ObjectTypeDef:
    name: str
    description: str
    properties: dict[str, dict]
    links: dict[str, LinkDef]

    @property
    def primary_key(self) -> str:
        for prop_name, prop_def in self.properties.items():
            if prop_def.get("primary_key"):
                return prop_name
        raise ValueError(f"No primary key defined on {self.name}")


@dataclass
class ActionDef:
    name: str
    description: str
    params: dict[str, dict]
    target_type: str
    requires_confirmation: bool
    edits: dict[str, str] = field(default_factory=dict)
    creates: bool = False


@dataclass
class FunctionDef:
    name: str
    description: str
    params: dict[str, dict]
    returns: str
    permission: str


class SchemaRegistry:
    def __init__(self, schema_path: str):
        with open(schema_path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        self._object_types = self._parse_object_types(raw.get("object_types", {}))
        self._actions = self._parse_actions(raw.get("actions", {}))
        self._functions = self._parse_functions(raw.get("functions", {}))

    def _parse_object_types(self, raw: dict) -> dict[str, ObjectTypeDef]:
        result = {}
        for name, defn in raw.items():
            links = {}
            for link_name, link_def in defn.get("links", {}).items():
                links[link_name] = LinkDef(
                    target=link_def["target"],
                    foreign_key=link_def["foreign_key"],
                )
            result[name] = ObjectTypeDef(
                name=name,
                description=defn.get("description", ""),
                properties=defn.get("properties", {}),
                links=links,
            )
        return result

    def _parse_actions(self, raw: dict) -> dict[str, ActionDef]:
        result = {}
        for name, defn in raw.items():
            result[name] = ActionDef(
                name=name,
                description=defn.get("description", ""),
                params=defn.get("params", {}),
                target_type=defn.get("target_type", ""),
                requires_confirmation=defn.get("requires_confirmation", False),
                edits=defn.get("edits", {}),
                creates=defn.get("creates", False),
            )
        return result

    def _parse_functions(self, raw: dict) -> dict[str, FunctionDef]:
        result = {}
        for name, defn in raw.items():
            result[name] = FunctionDef(
                name=name,
                description=defn.get("description", ""),
                params=defn.get("params", {}),
                returns=defn.get("returns", ""),
                permission=defn.get("permission", ""),
            )
        return result

    def get_object_type(self, name: str) -> ObjectTypeDef:
        if name not in self._object_types:
            raise KeyError(f"Unknown object type: {name}")
        return self._object_types[name]

    def get_action(self, name: str) -> ActionDef:
        if name not in self._actions:
            raise KeyError(f"Unknown action: {name}")
        return self._actions[name]

    def get_function(self, name: str) -> FunctionDef:
        if name not in self._functions:
            raise KeyError(f"Unknown function: {name}")
        return self._functions[name]

    @property
    def object_type_names(self) -> list[str]:
        return list(self._object_types.keys())

    @property
    def action_names(self) -> list[str]:
        return list(self._actions.keys())

    @property
    def function_names(self) -> list[str]:
        return list(self._functions.keys())

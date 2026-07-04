from __future__ import annotations
import yaml
from ontopilot.store import ObjectStore
from ontopilot.governance import PermissionEvaluator


class ContextBuilder:
    def __init__(
        self,
        context_sources_path: str,
        store: ObjectStore,
        permission_evaluator: PermissionEvaluator,
    ):
        with open(context_sources_path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        self._sources = raw.get("context_sources", [])
        self._store = store
        self._pe = permission_evaluator

    def build(self, user_id: str, role: str, warehouse_id: str) -> str:
        lines = [
            "[CONTEXT]",
            f"用户: {user_id}",
            f"角色: {role}",
            f"绑定仓库: {warehouse_id}",
        ]
        for source in self._sources:
            src_type = source["type"]
            object_type = source["object_type"]

            if src_type == "fixed_objects":
                obj = self._store.get(object_type, warehouse_id)
                if obj:
                    props = source.get("properties")
                    if props:
                        obj = {k: obj[k] for k in props if k in obj}
                    lines.append(f"\n<{object_type}>")
                    for k, v in obj.items():
                        lines.append(f"  {k}: {v}")
                    lines.append(f"</{object_type}>")

            elif src_type == "scoped_query":
                filters = {}
                for k, v in source.get("filters", {}).items():
                    resolved = v
                    if isinstance(v, str) and "${session.bound_warehouse_id}" in v:
                        resolved = warehouse_id
                    filters[k] = resolved
                max_objects = source.get("max_objects", 20)
                props = source.get("properties")
                results = self._store.query(object_type, filters, props)[:max_objects]
                lines.append(f"\n<{object_type}List count={len(results)}>")
                for obj in results:
                    lines.append(f"  - {obj}")
                lines.append(f"</{object_type}List>")

        lines.append("[/CONTEXT]")
        return "\n".join(lines)

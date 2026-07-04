from __future__ import annotations
import copy
import json
import sqlite3
from typing import Any
import yaml
from ontopilot.schema import SchemaRegistry


class ObjectStore:
    def __init__(self, db_path: str, schema: SchemaRegistry, _data: dict | None = None):
        self._schema = schema
        self._db_path = db_path
        self._in_memory: dict[str, dict[str, dict]] | None = _data
        if self._in_memory is None:
            self._init_db()

    def clear_all(self) -> None:
        if self._in_memory is not None:
            self._in_memory.clear()
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("DELETE FROM objects")

    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS objects (
                    object_type TEXT NOT NULL,
                    object_id TEXT NOT NULL,
                    data TEXT NOT NULL,
                    PRIMARY KEY (object_type, object_id)
                )
            """)

    # ── seed loading ─────────────────────────────────────────────────────────

    def load_seed_data(self, seed_path: str) -> None:
        with open(seed_path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        for object_type, objects in raw.items():
            if not objects:
                continue
            for obj in objects:
                pk_field = self._schema.get_object_type(object_type).primary_key
                object_id = obj[pk_field]
                self._write(object_type, object_id, obj)

    # ── CRUD ─────────────────────────────────────────────────────────────────

    def get(self, object_type: str, object_id: str) -> dict | None:
        if self._in_memory is not None:
            return copy.deepcopy(
                self._in_memory.get(object_type, {}).get(object_id)
            )
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT data FROM objects WHERE object_type=? AND object_id=?",
                (object_type, object_id),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def query(
        self,
        object_type: str,
        filters: dict | None,
        properties: list[str] | None,
    ) -> list[dict]:
        all_objects = self._all_objects(object_type)
        result = []
        for obj in all_objects:
            if self._matches(obj, filters or {}):
                if properties:
                    obj = {k: obj[k] for k in properties if k in obj}
                result.append(obj)
        return result

    def count(self, object_type: str, filters: dict | None) -> int:
        return len(self.query(object_type, filters, None))

    def update(self, object_type: str, object_id: str, changes: dict) -> dict:
        existing = self.get(object_type, object_id)
        if existing is None:
            raise KeyError(f"{object_type}:{object_id} not found")
        existing.update(changes)
        self._write(object_type, object_id, existing)
        return copy.deepcopy(existing)

    def create(self, object_type: str, data: dict) -> dict:
        pk_field = self._schema.get_object_type(object_type).primary_key
        object_id = data[pk_field]
        self._write(object_type, object_id, data)
        return copy.deepcopy(data)

    # ── link traversal ────────────────────────────────────────────────────────

    def traverse(
        self,
        object_type: str,
        object_id: str,
        link_name: str,
        properties: list[str] | None,
    ) -> list[dict]:
        ot = self._schema.get_object_type(object_type)
        if link_name not in ot.links:
            raise KeyError(f"No link '{link_name}' on {object_type}")
        link = ot.links[link_name]
        source = self.get(object_type, object_id)
        if source is None:
            return []
        fk_value = source.get(link.foreign_key)
        if fk_value is None:
            return []
        target_pk = self._schema.get_object_type(link.target).primary_key
        results = self.query(link.target, {target_pk: fk_value}, properties)
        return results

    # ── fork (for simulation) ─────────────────────────────────────────────────

    def fork(self) -> ObjectStore:
        data: dict[str, dict[str, dict]] = {}
        for object_type in self._schema.object_type_names:
            objs = self._all_objects(object_type)
            data[object_type] = {
                obj[self._schema.get_object_type(object_type).primary_key]: copy.deepcopy(obj)
                for obj in objs
            }
        forked = ObjectStore.__new__(ObjectStore)
        forked._schema = self._schema
        forked._db_path = self._db_path
        forked._in_memory = data
        return forked

    # ── internal ──────────────────────────────────────────────────────────────

    def _all_objects(self, object_type: str) -> list[dict]:
        if self._in_memory is not None:
            return [copy.deepcopy(v) for v in self._in_memory.get(object_type, {}).values()]
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute(
                "SELECT data FROM objects WHERE object_type=?", (object_type,)
            ).fetchall()
        return [json.loads(r[0]) for r in rows]

    def _write(self, object_type: str, object_id: str, data: dict) -> None:
        if self._in_memory is not None:
            self._in_memory.setdefault(object_type, {})[object_id] = copy.deepcopy(data)
            return
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO objects VALUES (?,?,?)",
                (object_type, object_id, json.dumps(data, ensure_ascii=False)),
            )

    def _matches(self, obj: dict, filters: dict) -> bool:
        for key, value in filters.items():
            obj_val = obj.get(key)
            if isinstance(value, list):
                if obj_val not in value:
                    return False
            else:
                if obj_val != value:
                    return False
        return True

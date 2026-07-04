from __future__ import annotations
import os
import time
import uuid
from datetime import datetime, timezone

from ontopilot.actions import ActionExecutor
from ontopilot.audit import AuditLogger
from ontopilot.context import ContextBuilder
from ontopilot.functions import FunctionRegistry
from ontopilot.governance import PermissionEvaluator
from ontopilot.schema import SchemaRegistry
from ontopilot.simulation import SingleStepSimulator
from ontopilot.store import ObjectStore
from ontopilot.trace import TraceEvent, TraceRecorder


class OntologyRuntime:
    def __init__(
        self,
        schema: SchemaRegistry,
        store: ObjectStore,
        governance: PermissionEvaluator,
        context_builder: ContextBuilder,
        functions: FunctionRegistry,
        actions: ActionExecutor,
        audit: AuditLogger,
        simulator: SingleStepSimulator | None = None,
    ):
        self._schema = schema
        self._store = store
        self._governance = governance
        self._context_builder = context_builder
        self._functions = functions
        self._actions = actions
        self._audit = audit
        self._simulator = simulator
        self._tracer = TraceRecorder(conversation_id=str(uuid.uuid4()))
        self._event_callback = None

    # Sentinel to distinguish "use default" from "skip seed loading"
    _SKIP_SEED = object()

    @classmethod
    def from_config(
        cls,
        config_dir: str = "config",
        db_path: str = ".ontopilot.db",
        schema_path: str | None = None,
        seed_path: str | None = None,
        permissions_path: str | None = None,
        context_path: str | None = None,
    ) -> "OntologyRuntime":
        schema = SchemaRegistry(schema_path or os.path.join(config_dir, "ontology_schema.yaml"))
        store = ObjectStore(db_path, schema)
        if seed_path is cls._SKIP_SEED:
            store.clear_all()
        else:
            store.load_seed_data(seed_path or os.path.join(config_dir, "seed_data.yaml"))
        governance = PermissionEvaluator(permissions_path or os.path.join(config_dir, "permissions.yaml"))
        context_builder = ContextBuilder(
            context_path or os.path.join(config_dir, "context_sources.yaml"), store, governance
        )
        functions = FunctionRegistry(schema, store)
        actions = ActionExecutor(schema, store, governance)
        audit = AuditLogger(db_path)
        simulator = SingleStepSimulator(schema, store, functions)
        return cls(schema, store, governance, context_builder, functions, actions, audit, simulator)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _record(self, turn_id: str, layer: str, name: str, status: str,
                input_summary: dict, output_summary: dict,
                permission_result: str, duration_ms: int,
                audit_id: str | None = None, error: str | None = None) -> None:
        event = TraceEvent(
            id=str(uuid.uuid4()),
            conversation_id=self._tracer.conversation_id,
            turn_id=turn_id,
            timestamp=datetime.now(timezone.utc),
            layer=layer, name=name, status=status,
            input_summary=input_summary, output_summary=output_summary,
            permission_result=permission_result, duration_ms=duration_ms,
            audit_id=audit_id, error=error,
        )
        self._tracer.record(event)
        if self._event_callback:
            try:
                self._event_callback(event.to_dict())
            except Exception:
                pass

    def _apply_data_scope(self, role: str, object_type: str, filters: dict) -> dict:
        allowed_regions = self._governance.get_allowed_warehouse_regions(role)
        if not allowed_regions:
            return filters
        new_filters = dict(filters)
        if object_type == "Warehouse":
            new_filters["region"] = allowed_regions if len(allowed_regions) > 1 else allowed_regions[0]
        elif object_type == "Shipment":
            allowed_wh = [
                w["warehouseId"]
                for w in self._store.query("Warehouse", {"region": allowed_regions}, ["warehouseId"])
            ]
            if "warehouseId" not in new_filters:
                new_filters["warehouseId"] = allowed_wh
        return new_filters

    def get_trace_events(self, turn_id: str) -> list[TraceEvent]:
        return self._tracer.get_events(turn_id)

    # ── build_context ─────────────────────────────────────────────────────────

    def build_context(self, user_id: str, role: str, warehouse_id: str,
                      turn_id: str | None = None) -> str:
        t0 = time.monotonic()
        turn_id = turn_id or str(uuid.uuid4())
        ctx = self._context_builder.build(user_id, role, warehouse_id)
        ms = int((time.monotonic() - t0) * 1000)
        self._record(turn_id, "context", "context_builder", "success",
                     {"warehouse_id": warehouse_id}, {"length": len(ctx)}, "pass", ms)
        return ctx

    # ── query ─────────────────────────────────────────────────────────────────

    def _normalize_type(self, raw: str) -> str:
        """Resolve a type name, handling case mismatches and Chinese descriptions."""
        raw_stripped = raw.strip()
        type_names = self._schema.object_type_names
        # Exact match
        if raw_stripped in type_names:
            return raw_stripped
        # Case-insensitive match
        lower = raw_stripped.lower()
        for name in type_names:
            if name.lower() == lower:
                return name
        # Match against description (Chinese)
        for name in type_names:
            obj = self._schema.get_object_type(name)
            desc = obj.description if hasattr(obj, 'description') else ""
            if desc and (raw_stripped in desc or any(c in desc for c in raw_stripped if len(raw_stripped) > 1)):
                return name
        return raw_stripped

    def query(self, user_id: str, role: str, object_type: str,
              filters: dict | None = None, properties: list[str] | None = None,
              aggregation: str | None = None,
              turn_id: str | None = None) -> list[dict] | int:
        turn_id = turn_id or str(uuid.uuid4())
        t0 = time.monotonic()
        object_type = self._normalize_type(object_type)

        # If the type doesn't exist in the schema at all, return empty gracefully
        if object_type not in self._schema.object_type_names:
            ms = int((time.monotonic() - t0) * 1000)
            self._record(turn_id, "query", f"object_query:{object_type}", "empty",
                         {"object_type": object_type}, {"result_count": 0}, "pass", ms)
            return []

        if not self._governance.can_query(role, object_type):
            ms = int((time.monotonic() - t0) * 1000)
            self._record(turn_id, "query", f"object_query:{object_type}", "denied",
                         {"object_type": object_type}, {}, "deny", ms)
            raise PermissionError(f"Role '{role}' cannot query {object_type}")

        scoped_filters = self._apply_data_scope(role, object_type, filters or {})

        if aggregation == "count":
            result = self._store.count(object_type, scoped_filters)
            out = {"count": result}
        else:
            result = self._store.query(object_type, scoped_filters, properties)
            out = {"result_count": len(result), "properties": properties}

        ms = int((time.monotonic() - t0) * 1000)
        audit_id = self._audit.log(user_id, "query", object_type, None,
                                   {"filters": scoped_filters}, {"count": len(result) if isinstance(result, list) else result}, "pass")
        self._record(turn_id, "query", f"object_query:{object_type}", "success",
                     {"object_type": object_type, "filters": scoped_filters},
                     out, "pass", ms, audit_id=audit_id)
        return result

    # ── traverse ──────────────────────────────────────────────────────────────

    def traverse(self, user_id: str, role: str, object_type: str,
                 object_id: str, link_name: str,
                 properties: list[str] | None = None,
                 turn_id: str | None = None) -> list[dict]:
        turn_id = turn_id or str(uuid.uuid4())
        t0 = time.monotonic()

        if not self._governance.can_query(role, object_type):
            raise PermissionError(f"Role '{role}' cannot query {object_type}")

        results = self._store.traverse(object_type, object_id, link_name, properties)
        ms = int((time.monotonic() - t0) * 1000)
        self._record(turn_id, "query", f"traverse:{object_type}.{link_name}", "success",
                     {"object_type": object_type, "object_id": object_id, "link": link_name},
                     {"result_count": len(results)}, "pass", ms)
        return results

    # ── call_function ─────────────────────────────────────────────────────────

    def call_function(self, user_id: str, role: str, function_name: str,
                      params: dict, turn_id: str | None = None) -> list | dict:
        turn_id = turn_id or str(uuid.uuid4())
        t0 = time.monotonic()

        if not self._governance.can_call_function(role, function_name):
            ms = int((time.monotonic() - t0) * 1000)
            self._record(turn_id, "logic", f"function:{function_name}", "denied",
                         {"function": function_name}, {}, "deny", ms)
            raise PermissionError(f"Role '{role}' cannot call function {function_name}")

        result = self._functions.call(function_name, params)
        ms = int((time.monotonic() - t0) * 1000)
        out_summary = {"result_count": len(result)} if isinstance(result, list) else {"result": str(result)[:200]}
        audit_id = self._audit.log(user_id, "function", None, None,
                                   {"function": function_name, "params": params}, out_summary, "pass")
        self._record(turn_id, "logic", f"function:{function_name}", "success",
                     {"function": function_name, "params": params},
                     out_summary, "pass", ms, audit_id=audit_id)
        return result

    # ── preview_action ────────────────────────────────────────────────────────

    def preview_action(self, user_id: str, role: str, action_name: str,
                       params: dict, turn_id: str | None = None) -> dict:
        turn_id = turn_id or str(uuid.uuid4())
        t0 = time.monotonic()

        if not self._governance.can_execute_action(role, action_name):
            raise PermissionError(f"Role '{role}' cannot execute action {action_name}")

        preview = self._actions.preview(role, action_name, params)
        ms = int((time.monotonic() - t0) * 1000)
        self._record(turn_id, "action", f"preview_action:{action_name}",
                     preview["status"],
                     {"action": action_name, "params": params},
                     {"changes": preview["changes"]}, "pass", ms)
        return preview

    # ── execute_action ────────────────────────────────────────────────────────

    def execute_action(self, user_id: str, role: str, action_name: str,
                       params: dict, confirmed: bool = False,
                       turn_id: str | None = None) -> dict:
        turn_id = turn_id or str(uuid.uuid4())
        t0 = time.monotonic()

        if not self._governance.can_execute_action(role, action_name):
            raise PermissionError(f"Role '{role}' cannot execute action {action_name}")

        result = self._actions.execute(role, user_id, action_name, params, confirmed)
        ms = int((time.monotonic() - t0) * 1000)
        audit_id = self._audit.log(user_id, "action", None, None,
                                   {"action": action_name, "params": params, "confirmed": confirmed},
                                   {"status": result["status"]}, "pass")
        self._record(turn_id, "action", f"execute_action:{action_name}", "success",
                     {"action": action_name, "confirmed": confirmed},
                     {"status": result["status"]}, "pass", ms, audit_id=audit_id)
        return result

    # ── simulate ──────────────────────────────────────────────────────────────

    def simulate(self, user_id: str, role: str, shipment_id: str,
                 options: list[dict], turn_id: str | None = None) -> list[dict]:
        turn_id = turn_id or str(uuid.uuid4())
        t0 = time.monotonic()

        if not self._governance.can_call_function(role, "compareDecisions"):
            raise PermissionError(f"Role '{role}' cannot run simulations")

        if self._simulator is None:
            raise RuntimeError("Simulator not initialized")

        result = self._simulator.compare(shipment_id, options)
        ms = int((time.monotonic() - t0) * 1000)
        audit_id = self._audit.log(user_id, "simulation", "Shipment", shipment_id,
                                   {"options": options}, {"result_count": len(result)}, "pass")
        self._record(turn_id, "simulation", "simulate_decisions", "success",
                     {"shipment_id": shipment_id, "options": [o["name"] for o in options]},
                     {"result_count": len(result)}, "pass", ms, audit_id=audit_id)
        return result

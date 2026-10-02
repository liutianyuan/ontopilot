from __future__ import annotations
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any

from ontopilot.audit import AuditLogger
from ontopilot.trace import TraceEvent, TraceRecorder


class OntologyRuntime:
    def __init__(
        self,
        schema: Any,
        store: Any,
        governance: Any,
        context_builder: Any,
        functions: Any,
        actions: Any,
        audit: AuditLogger,
    ):
        self._schema = schema
        self._store = store
        self._governance = governance
        self._context_builder = context_builder
        self._functions = functions
        self._actions = actions
        self._audit = audit
        self._tracer = TraceRecorder(conversation_id=str(uuid.uuid4()))
        self._event_callback = None
        self._query_cache: dict[tuple, list | int] = {}
        self._object_context_cache: dict[tuple[str, str], dict] = {}

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
        """Apply only schema-neutral filters supplied by the active adapter."""
        scope = self._governance.get_data_scope(role) if hasattr(self._governance, "get_data_scope") else {}
        return {**filters, **scope.get(object_type, {})}

    def get_trace_events(self, turn_id: str) -> list[TraceEvent]:
        return self._tracer.get_events(turn_id)

    # ── build_context ─────────────────────────────────────────────────────────

    def build_context(self, user_id: str, role: str, context_id: str,
                      turn_id: str | None = None) -> str:
        t0 = time.monotonic()
        turn_id = turn_id or str(uuid.uuid4())
        ctx = self._context_builder.build(user_id, role, context_id)
        ms = int((time.monotonic() - t0) * 1000)
        self._record(turn_id, "context", "context_builder", "success",
                     {"context_id": context_id}, {"length": len(ctx)}, "pass", ms)
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
        cache_key = (turn_id, object_type, repr(sorted(scoped_filters.items())),
                     tuple(properties or []), aggregation)
        if cache_key in self._query_cache:
            result = self._query_cache[cache_key]
            self._record(turn_id, "query", f"object_query:{object_type}", "cached",
                         {"object_type": object_type, "filters": scoped_filters},
                         {"result_count": len(result) if isinstance(result, list) else result}, "pass", 0)
            return result

        if aggregation == "count":
            result = self._store.count(object_type, scoped_filters)
            out = {"count": result}
        else:
            result = self._store.query(object_type, scoped_filters, properties)
            out = {"result_count": len(result), "properties": properties}
        self._query_cache[cache_key] = result

        ms = int((time.monotonic() - t0) * 1000)
        audit_id = self._audit.log(user_id, "query", object_type, None,
                                   {"filters": scoped_filters}, {"count": len(result) if isinstance(result, list) else result}, "pass")
        self._record(turn_id, "query", f"object_query:{object_type}", "success",
                     {"object_type": object_type, "filters": scoped_filters},
                     out, "pass", ms, audit_id=audit_id)
        return result

    def get_object_context(self, user_id: str, role: str, object_key: str,
                            turn_id: str | None = None) -> dict:
        """Fetch all available topic facts for one business identifier."""
        turn_id = turn_id or str(uuid.uuid4())
        cache_key = (turn_id, object_key)
        if cache_key in self._object_context_cache:
            return self._object_context_cache[cache_key]
        t0 = time.monotonic()
        result = self.topic_client.object_context(object_key)
        self._object_context_cache[cache_key] = result
        ms = int((time.monotonic() - t0) * 1000)
        audit_id = self._audit.log(user_id, "query", "ObjectContext", object_key,
                                   {"object_key": object_key},
                                   {"found": result.get("found"), "fact_count": len(result.get("facts", []))}, "pass")
        self._record(turn_id, "query", "object_context", "success" if result.get("found") else "empty",
                     {"object_key": object_key},
                     {"found": result.get("found"), "fact_count": len(result.get("facts", [])),
                      "relation_count": len(result.get("relations", []))}, "pass", ms, audit_id=audit_id)
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
        layer = "logic"

        # Extract involved_types from function result (dict or first list element)
        involved: dict | None = None
        if isinstance(result, list) and result:
            involved = result[0].get("involved_types") if isinstance(result[0], dict) else None
        elif isinstance(result, dict):
            involved = result.get("involved_types")

        if involved:
            out_summary["involved_types"] = involved
            if function_name == "compareDecisions":
                layer = "simulation"
            # Emit synthetic query-layer events so the ontology graph panel
            # highlights the object types and links touched by this function.
            all_involved = set(involved.get("mutated", []) + involved.get("referenced", []))
            for ot in all_involved:
                self._record(turn_id, "query", f"object_query:{ot}", "success",
                             {"object_type": ot}, {"result_count": 1}, "pass", 0)
            # Emit traverse events for links between involved types
            for ot in all_involved:
                ot_def = self._schema.get_object_type(ot)
                for link_name, link_def in ot_def.links.items():
                    if link_def.target in all_involved:
                        self._record(turn_id, "query", f"traverse:{ot}.{link_name}", "success",
                                     {"object_type": ot, "link": link_name}, {"result_count": 1}, "pass", 0)
        elif function_name == "compareDecisions" and isinstance(result, list):
            out_summary["involved_types"] = result[0]["involved_types"] if result else {"mutated": [], "referenced": []}
            layer = "simulation"
        audit_id = self._audit.log(user_id, "function", None, None,
                                   {"function": function_name, "params": params}, out_summary, "pass")
        self._record(turn_id, layer, f"function:{function_name}", "success",
                     {"function": function_name, "params": params},
                     out_summary, "pass", ms, audit_id=audit_id)
        return result

    def evaluate_object_rules(self, user_id: str, role: str, object_id: str,
                               turn_id: str | None = None) -> list[dict]:
        """Evaluate every rule published by the selected topic for one object."""
        turn_id = turn_id or str(uuid.uuid4())
        context = self.get_object_context(user_id, role, object_id, turn_id)
        if not context.get("found"):
            self._record(turn_id, "logic", "evaluate_object_rules", "empty",
                         {"object_id": object_id},
                         {"reason": "object_not_found", "result_count": 0}, "pass", 0)
            return []
        function_names = self._governance.get_allowed_functions(role)
        if not function_names:
            return []

        def evaluate(function_name: str) -> dict:
            try:
                result = self.call_function(user_id, role, function_name,
                                            {"object_id": object_id}, turn_id)
                if isinstance(result, dict):
                    # The same object evidence can be repeated in every rule
                    # response. Conditions already contain the actual values
                    # used by the evaluator, so do not flood the model context
                    # with nine copies of the full graph records.
                    result = {key: value for key, value in result.items()
                              if key not in {"evidence", "formula"}}
                return result
            except (KeyError, PermissionError, RuntimeError) as exc:
                return {"function_name": function_name, "status": "error", "error": str(exc)}

        # Every request still goes through Nano's authenticated rule endpoint;
        # concurrency only prevents total latency from growing linearly with
        # the number of rules published by a topic.
        indexed_results: dict[str, dict] = {}
        with ThreadPoolExecutor(max_workers=min(8, len(function_names))) as pool:
            futures = {pool.submit(evaluate, name): name for name in function_names}
            for future in as_completed(futures):
                indexed_results[futures[future]] = future.result()
        return [indexed_results[name] for name in function_names]

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
                     {"changes": preview.get("changes", []),
                      "confirmation_id": preview.get("confirmation_id")}, "pass", ms)
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
        self._record(turn_id, "action", f"execute_action:{action_name}", result.get("status", "success"),
                     {"action": action_name, "confirmed": confirmed},
                     {"status": result["status"]}, "pass", ms, audit_id=audit_id)
        return result

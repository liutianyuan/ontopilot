from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from ontopilot.runtime import OntologyRuntime
from ontopilot.schema import SchemaRegistry
from ontopilot.governance import PermissionEvaluator


@dataclass
class CaseResult:
    case_id: str
    passed: bool
    checks: dict[str, bool]
    notes: str = ""


@dataclass
class EvaluationReport:
    case_results: list[CaseResult]
    metric_scores: dict[str, float] = field(default_factory=dict)

    @property
    def pass_rate(self) -> float:
        if not self.case_results:
            return 0.0
        return sum(1 for r in self.case_results if r.passed) / len(self.case_results)


class BaselineEvaluator:
    def __init__(self, runtime: OntologyRuntime, schema: SchemaRegistry,
                 governance: PermissionEvaluator):
        self._runtime = runtime
        self._schema = schema
        self._governance = governance

    def run_all_cases_no_llm(self) -> EvaluationReport:
        """Run deterministic checks (no LLM) for metrics."""
        case_results = [
            self._check_data_accuracy(),
            self._check_permission_compliance(),
            self._check_action_confirmation(),
            self._check_audit_coverage(),
            self._check_data_scope_enforcement(),
        ]

        metric_scores = {
            "data_accuracy": self._score_data_accuracy(),
            "permission_compliance": self._score_permission_compliance(),
            "action_confirmation_rate": self._score_action_confirmation(),
            "audit_coverage": self._score_audit_coverage(),
        }

        return EvaluationReport(case_results=case_results, metric_scores=metric_scores)

    # ── data accuracy ─────────────────────────────────────────────────────────

    def _check_data_accuracy(self) -> CaseResult:
        turn_id = str(uuid.uuid4())
        results = self._runtime.query(
            "dispatcher_001", "dispatcher", "Shipment",
            filters={"status": "delayed", "warehouseId": "WH-SC-001"},
            turn_id=turn_id,
        )
        all_exist = all(
            self._runtime._store.get("Shipment", r["shipmentId"]) is not None
            for r in results
        )
        return CaseResult(
            case_id="data_accuracy",
            passed=all_exist and len(results) >= 7,
            checks={"objects_exist_in_store": all_exist, "min_count_met": len(results) >= 7},
        )

    def _score_data_accuracy(self) -> float:
        result = self._check_data_accuracy()
        return 1.0 if result.passed else 0.0

    # ── permission compliance ─────────────────────────────────────────────────

    def _check_permission_compliance(self) -> CaseResult:
        checks = {}
        try:
            self._runtime.query("dispatcher_001", "dispatcher", "Carrier", turn_id=str(uuid.uuid4()))
            checks["dispatcher_cannot_query_carrier"] = False
        except PermissionError:
            checks["dispatcher_cannot_query_carrier"] = True

        try:
            self._runtime.call_function("dispatcher_001", "dispatcher", "recommendCarrier",
                                        {"shipmentId": "SH-0042"}, turn_id=str(uuid.uuid4()))
            checks["dispatcher_cannot_call_recommendCarrier"] = False
        except PermissionError:
            checks["dispatcher_cannot_call_recommendCarrier"] = True

        passed = all(checks.values())
        return CaseResult(case_id="permission_compliance", passed=passed, checks=checks)

    def _score_permission_compliance(self) -> float:
        result = self._check_permission_compliance()
        n = len(result.checks)
        ok = sum(1 for v in result.checks.values() if v)
        return ok / n if n > 0 else 0.0

    # ── action confirmation ───────────────────────────────────────────────────

    def _check_action_confirmation(self) -> CaseResult:
        turn_id = str(uuid.uuid4())
        preview = self._runtime.preview_action(
            "dispatcher_001", "dispatcher", "assignCarrier",
            {"shipmentId": "SH-0042", "newCarrierId": "CARRIER-B", "reason": "test"},
            turn_id=turn_id,
        )
        confirmation_required = preview["status"] == "pending_confirmation"

        blocked = False
        try:
            self._runtime.execute_action(
                "dispatcher_001", "dispatcher", "assignCarrier",
                {"shipmentId": "SH-0042", "newCarrierId": "CARRIER-B", "reason": "test"},
                confirmed=False, turn_id=str(uuid.uuid4()),
            )
        except PermissionError:
            blocked = True

        checks = {
            "preview_returns_pending_confirmation": confirmation_required,
            "execute_without_confirm_blocked": blocked,
        }
        return CaseResult(case_id="action_confirmation", passed=all(checks.values()), checks=checks)

    def _score_action_confirmation(self) -> float:
        result = self._check_action_confirmation()
        return 1.0 if result.passed else 0.0

    # ── audit coverage ────────────────────────────────────────────────────────

    def _check_audit_coverage(self) -> CaseResult:
        turn_id = str(uuid.uuid4())
        self._runtime.query(
            "dispatcher_001", "dispatcher", "Shipment",
            filters={"status": "delayed"},
            turn_id=turn_id,
        )
        events = self._runtime.get_trace_events(turn_id)
        has_query_event = any(e.layer == "query" for e in events)
        has_audit_id = any(e.audit_id is not None for e in events)
        checks = {
            "query_generates_trace": has_query_event,
            "trace_has_audit_id": has_audit_id,
        }
        return CaseResult(case_id="audit_coverage", passed=all(checks.values()), checks=checks)

    def _score_audit_coverage(self) -> float:
        result = self._check_audit_coverage()
        return 1.0 if result.passed else 0.0

    # ── data scope ────────────────────────────────────────────────────────────

    def _check_data_scope_enforcement(self) -> CaseResult:
        turn_id = str(uuid.uuid4())
        results = self._runtime.query(
            "dispatcher_001", "dispatcher", "Shipment",
            filters={"status": "delayed"},
            turn_id=turn_id,
        )
        ec_shipments = [r for r in results if r.get("warehouseId") == "WH-EC-001"]
        checks = {"dispatcher_cannot_see_east_china_shipments": len(ec_shipments) == 0}
        return CaseResult(
            case_id="data_scope_enforcement",
            passed=len(ec_shipments) == 0,
            checks=checks,
        )

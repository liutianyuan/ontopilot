from unittest.mock import Mock

from ontopilot.audit import AuditLogger
from ontopilot.runtime import OntologyRuntime


def test_missing_object_stops_before_rule_evaluation(tmp_path):
    governance = Mock()
    governance.get_allowed_functions.return_value = ["configuredRule"]
    functions = Mock()
    runtime = OntologyRuntime(
        Mock(), Mock(), governance, Mock(), functions, Mock(),
        AuditLogger(str(tmp_path / "audit.db")),
    )
    runtime.topic_client = Mock()
    runtime.topic_client.object_context.return_value = {"found": False, "facts": [], "relations": []}

    result = runtime.evaluate_object_rules("user", "admin", "missing-object", "turn")

    assert result == []
    functions.call.assert_not_called()
    assert any(event.status == "empty" and event.output_summary.get("reason") == "object_not_found"
               for event in runtime.get_trace_events("turn"))

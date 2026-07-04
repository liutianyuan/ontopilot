from ontopilot.evaluation import BaselineEvaluator, EvaluationReport
from ontopilot.schema import SchemaRegistry
from ontopilot.governance import PermissionEvaluator


def test_evaluation_report_has_required_fields(tmp_path):
    from ontopilot.runtime import OntologyRuntime
    runtime = OntologyRuntime.from_config("config", str(tmp_path / "test.db"))
    schema = SchemaRegistry("config/ontology_schema.yaml")
    governance = PermissionEvaluator("config/permissions.yaml")
    evaluator = BaselineEvaluator(runtime, schema, governance)
    report = evaluator.run_all_cases_no_llm()
    assert isinstance(report, EvaluationReport)
    assert 0.0 <= report.pass_rate <= 1.0
    assert "data_accuracy" in report.metric_scores
    assert "permission_compliance" in report.metric_scores
    assert "audit_coverage" in report.metric_scores
    assert len(report.case_results) > 0


def test_permission_compliance_check(tmp_path):
    from ontopilot.runtime import OntologyRuntime
    runtime = OntologyRuntime.from_config("config", str(tmp_path / "test.db"))
    schema = SchemaRegistry("config/ontology_schema.yaml")
    governance = PermissionEvaluator("config/permissions.yaml")
    evaluator = BaselineEvaluator(runtime, schema, governance)
    report = evaluator.run_all_cases_no_llm()
    assert report.metric_scores["permission_compliance"] == 1.0


def test_action_confirmation_check(tmp_path):
    from ontopilot.runtime import OntologyRuntime
    runtime = OntologyRuntime.from_config("config", str(tmp_path / "test.db"))
    schema = SchemaRegistry("config/ontology_schema.yaml")
    governance = PermissionEvaluator("config/permissions.yaml")
    evaluator = BaselineEvaluator(runtime, schema, governance)
    report = evaluator.run_all_cases_no_llm()
    assert report.metric_scores["action_confirmation_rate"] == 1.0

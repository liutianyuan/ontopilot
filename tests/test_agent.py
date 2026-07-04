from unittest.mock import MagicMock, patch
from langchain_core.messages import AIMessage, ToolMessage
from ontopilot.runtime import OntologyRuntime
from ontopilot.schema import SchemaRegistry
from ontopilot.governance import PermissionEvaluator


def test_agent_returns_response(tmp_path):
    """Agent with mocked LLM should return a text response."""
    runtime = OntologyRuntime.from_config("config", str(tmp_path / "test.db"))
    schema = SchemaRegistry("config/ontology_schema.yaml")
    governance = PermissionEvaluator("config/permissions.yaml")

    mock_llm = MagicMock()
    mock_llm.bind_tools.return_value = mock_llm
    mock_llm.invoke.return_value = AIMessage(content="华南仓当前有7个延误Shipment。")

    from ontopilot.agent import run_turn
    result = run_turn(
        runtime=runtime, llm=mock_llm, schema=schema, governance=governance,
        user_id="dispatcher_001", role="dispatcher",
        warehouse_id="WH-SC-001",
        user_message="华南仓今天有哪些延误订单？",
    )
    assert "response" in result
    assert len(result["response"]) > 0
    assert "trace_events" in result


def test_agent_returns_trace_events(tmp_path):
    runtime = OntologyRuntime.from_config("config", str(tmp_path / "test.db"))
    schema = SchemaRegistry("config/ontology_schema.yaml")
    governance = PermissionEvaluator("config/permissions.yaml")

    mock_llm = MagicMock()
    mock_llm.bind_tools.return_value = mock_llm
    mock_llm.invoke.return_value = AIMessage(content="回答内容")

    from ontopilot.agent import run_turn
    result = run_turn(
        runtime=runtime, llm=mock_llm, schema=schema, governance=governance,
        user_id="dispatcher_001", role="dispatcher",
        warehouse_id="WH-SC-001",
        user_message="测试消息",
    )
    assert len(result["trace_events"]) >= 1

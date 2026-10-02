from __future__ import annotations
from langchain_core.tools import tool
from ontopilot.runtime import OntologyRuntime


def create_tools(runtime: OntologyRuntime, user_id: str, role: str, turn_id: str):
    """Create LangGraph tool callables bound to this user's runtime context."""

    @tool
    def object_query(
        object_type: str,
        filters: dict = None,
        properties: list = None,
        aggregation: str = None,
    ) -> list | int:
        """Query Ontology objects. Supports equality/list filters, property projection, and count aggregation."""
        return runtime.query(user_id, role, object_type, filters, properties, aggregation, turn_id)

    fn_params_doc = "\n\n".join(
        f"{item['executor_key']} — {item.get('description') or item.get('name') or ''}\n"
        f"  Parameters: {item.get('params', {})}"
        for item in runtime.topic_manifest.get("rules", []) if item.get("executor_key")
    )

    @tool
    def call_function(function_name: str, params: dict) -> list | dict:
        """Evaluate one rule or function published by the selected knowledge topic."""
        try:
            return runtime.call_function(user_id, role, function_name, params, turn_id)
        except (KeyError, PermissionError) as e:
            return {"status": "error", "error": str(e), "function": function_name}

    # Patch the tool's description to include function-specific parameter docs.
    call_function.description = (
        "Evaluate one rule or function published by the selected knowledge topic.\n\n"
        "Available functions and their parameters:\n" + fn_params_doc
    )

    @tool
    def preview_action(action_name: str, params: dict) -> dict:
        """Preview a business action without modifying data. Always call this before execute_action."""
        try:
            return runtime.preview_action(user_id, role, action_name, params, turn_id)
        except (KeyError, PermissionError) as e:
            return {"status": "error", "error": str(e), "action": action_name}

    @tool
    def execute_action(action_name: str, params: dict, confirmed: bool = False) -> dict:
        """Execute a business action. Set confirmed=True only after user has seen and approved the preview."""
        try:
            return runtime.execute_action(user_id, role, action_name, params, confirmed, turn_id)
        except (KeyError, PermissionError) as e:
            return {"status": "error", "error": str(e), "action": action_name}

    tools = [object_query, call_function, preview_action, execute_action]
    @tool
    def get_object_context(object_key: str) -> dict:
        """Resolve a business object identifier and retrieve all of its facts and one-hop relations from the selected topic in one call. Use this first for questions about a specific object."""
        return runtime.get_object_context(user_id, role, object_key, turn_id)

    @tool
    def evaluate_object_rules(object_id: str) -> list:
        """Evaluate every published rule in the selected topic for an existing business object."""
        return runtime.evaluate_object_rules(user_id, role, object_id, turn_id)

    @tool
    def traverse_topic_graph(entity_id: str, relation_type: str = None, direction: str = "out") -> list:
        """Traverse the selected topic graph from an entity by relation type and direction."""
        return runtime.topic_client.traverse(entity_id, relation_type, direction)

    @tool
    def get_topic_action_run(run_id: str) -> dict:
        """Re-query a simulated or external topic action run by run ID."""
        return runtime.topic_client.action_run(run_id)

    tools.extend([get_object_context, evaluate_object_rules, traverse_topic_graph, get_topic_action_run])
    return tools

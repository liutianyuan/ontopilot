from __future__ import annotations
from langchain_core.tools import tool
from ontopilot.runtime import OntologyRuntime
from ontopilot.functions import FUNCTION_PARAMS


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
        f"{name} — {info['description']}\n  Required params: {info['required']}\n  Optional params: {info.get('optional', {})}"
        for name, info in FUNCTION_PARAMS.items()
    )

    @tool
    def call_function(function_name: str, params: dict) -> list | dict:
        """Call a registered business function. Use for risk scoring, carrier recommendation, decision comparison."""
        try:
            return runtime.call_function(user_id, role, function_name, params, turn_id)
        except (KeyError, PermissionError) as e:
            return {"status": "error", "error": str(e), "function": function_name}

    # Patch the tool's description to include function-specific parameter docs.
    # Patch the tool's description to include function-specific parameter docs.
    call_function.description = (
        "Call a registered business function. Use for risk scoring, carrier recommendation, decision comparison.\n\n"
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

    @tool
    def simulate_decisions(shipment_id: str, options: list) -> list:
        """Compare multiple decision options with single-step KPI simulation."""
        try:
            return runtime.simulate(user_id, role, shipment_id, options, turn_id)
        except (KeyError, PermissionError) as e:
            return [{"status": "error", "error": str(e), "shipment_id": shipment_id}]

    tools = [object_query, call_function, preview_action, execute_action, simulate_decisions]
    provider = getattr(runtime, "nano_provider", None)
    if provider is not None:
        @tool
        def get_nephrology_patient(patient_id: str) -> dict:
            """Query the live nephrology patient summary, facts, rule evaluations and alerts from nano-ontoprompt."""
            return provider.patient_summary(patient_id)

        @tool
        def get_nephrology_timeline(patient_id: str) -> list:
            """Query the source-event timeline for a nephrology patient from nano-ontoprompt."""
            return provider.patient_timeline(patient_id)

        @tool
        def list_nephrology_alerts(patient_id: str = None, status: str = None) -> list:
            """List live nephrology alerts, optionally filtered by patient and status."""
            return provider.alerts(patient_id, status)

        @tool
        def preview_nephrology_action(alert_id: str) -> dict:
            """Preview the recommended action for a nephrology alert and obtain a confirmation ID."""
            return provider.preview_alert_action(alert_id)

        @tool
        def decide_nephrology_action(confirmation_id: str, approved: bool) -> dict:
            """Approve or reject a previously previewed nephrology action."""
            return provider.decide(confirmation_id, approved)

        @tool
        def get_nephrology_action_run(run_id: str) -> dict:
            """Re-query a nephrology action run to verify the external writeback result."""
            return provider.action_run(run_id)

        tools.extend([get_nephrology_patient, get_nephrology_timeline, list_nephrology_alerts,
                      preview_nephrology_action, decide_nephrology_action, get_nephrology_action_run])
    return tools

from __future__ import annotations
import uuid
from typing import Annotated, Any
from typing_extensions import TypedDict

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.language_models import BaseChatModel
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from ontopilot.runtime import OntologyRuntime
from ontopilot.prompt import PromptBuilder
from ontopilot.tools import create_tools


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    user_id: str
    role: str
    warehouse_id: str
    turn_id: str
    awaiting_confirmation: bool
    pending_action: dict | None


def run_turn(
    runtime: OntologyRuntime,
    llm: BaseChatModel,
    schema,
    governance,
    user_id: str,
    role: str,
    warehouse_id: str,
    user_message: str,
    history: list[BaseMessage] | None = None,
    confirmed: bool = False,
    pending_action: dict | None = None,
) -> dict[str, Any]:
    """Run one conversation turn. Returns response text, trace events, and confirmation state."""
    turn_id = str(uuid.uuid4())
    tools = create_tools(runtime, user_id, role, turn_id)
    tool_node = ToolNode(tools)
    llm_with_tools = llm.bind_tools(tools)

    prompt_builder = PromptBuilder(schema, governance)
    available_functions = governance.get_allowed_functions(role) if hasattr(governance, "get_allowed_functions") else []
    allowed_actions = list(governance._role(role).get("actions", {}).keys())
    # Admin can execute all schema-registered actions even if not in permissions file
    if role == "admin":
        schema_actions = list(schema.action_names)
        available_actions = list(dict.fromkeys(allowed_actions + schema_actions))
    else:
        available_actions = allowed_actions
    context_str = runtime.build_context(user_id, role, warehouse_id, turn_id)
    system_prompt = prompt_builder.build_system_prompt(
        role, warehouse_id, context_str, available_functions, available_actions
    )

    if confirmed and pending_action:
        user_message = f"[用户已确认] {user_message}\n确认执行: {pending_action}"

    messages = [SystemMessage(content=system_prompt)]
    if history:
        messages.extend(history)
    messages.append(HumanMessage(content=user_message))

    def llm_node(state: AgentState) -> AgentState:
        response = llm_with_tools.invoke(state["messages"])
        return {"messages": [response]}

    def route_after_llm(state: AgentState) -> str:
        last = state["messages"][-1]
        if hasattr(last, "tool_calls") and last.tool_calls:
            return "tools"
        return "end"

    builder = StateGraph(AgentState)
    builder.add_node("llm_node", llm_node)
    builder.add_node("tool_node", tool_node)
    builder.set_entry_point("llm_node")
    builder.add_conditional_edges("llm_node", route_after_llm, {"tools": "tool_node", "end": END})
    builder.add_edge("tool_node", "llm_node")
    graph = builder.compile()

    initial_state: AgentState = {
        "messages": messages,
        "user_id": user_id,
        "role": role,
        "warehouse_id": warehouse_id,
        "turn_id": turn_id,
        "awaiting_confirmation": False,
        "pending_action": None,
    }

    final_state = graph.invoke(initial_state)
    last_message = final_state["messages"][-1]
    response_text = last_message.content if hasattr(last_message, "content") else str(last_message)

    trace_events = runtime.get_trace_events(turn_id)
    awaiting = any(e.status == "pending_confirmation" for e in trace_events)
    detected_pending = None
    if awaiting:
        for e in trace_events:
            if e.status == "pending_confirmation":
                detected_pending = e.input_summary
                break

    return {
        "response": response_text,
        "trace_events": [e.to_dict() for e in trace_events],
        "awaiting_confirmation": awaiting,
        "pending_action": detected_pending,
        "turn_id": turn_id,
    }

from __future__ import annotations
import json
import uuid
import re
from typing import Annotated, Any
from typing_extensions import TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
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
    context_id: str
    turn_id: str
    awaiting_confirmation: bool
    pending_action: dict | None


def _parse_text_tool_calls(content: Any) -> list[dict[str, Any]]:
    """Convert common model-emitted text tool syntax into native tool calls.

    Some OpenAI-compatible endpoints advertise tool calling but return an
    XML-like block in message content. Keeping this adapter at the protocol
    boundary avoids leaking that block to users and remains domain-neutral.
    """
    if not isinstance(content, str) or "<tool_call" not in content:
        return []

    calls: list[dict[str, Any]] = []
    for block in re.findall(r"<tool_call[^>]*>(.*?)</tool_call>", content, re.DOTALL | re.IGNORECASE):
        function_match = re.search(
            r"(?:<function(?:=|>\s*<name>)([^>\s<]+)>?|function\s*=\s*([^>\s<]+)>?)",
            block,
            re.IGNORECASE,
        )
        function_name = next(
            (group.strip() for group in function_match.groups() if group), ""
        ) if function_match else ""

        args: dict[str, Any] = {}
        for name, raw_value in re.findall(
            r"<parameter=([^>]+)>\s*(.*?)\s*</parameter>", block, re.DOTALL | re.IGNORECASE
        ):
            value = raw_value.strip()
            try:
                args[name.strip()] = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                args[name.strip()] = value

        # Also accept the widely used JSON form:
        # <tool_call>{"name":"object_query","arguments":{...}}</tool_call>
        if not function_name:
            try:
                payload = json.loads(block.strip())
            except (json.JSONDecodeError, TypeError):
                payload = None
            if isinstance(payload, dict):
                function_name = str(payload.get("name") or payload.get("function") or "")
                raw_args = payload.get("arguments") or payload.get("args") or {}
                if isinstance(raw_args, str):
                    try:
                        raw_args = json.loads(raw_args)
                    except json.JSONDecodeError:
                        raw_args = {}
                if isinstance(raw_args, dict):
                    args = raw_args

        if function_name:
            calls.append({
                "name": function_name,
                "args": args,
                "id": f"text-tool-{uuid.uuid4().hex}",
                "type": "tool_call",
            })
    return calls


def run_turn(
    runtime: OntologyRuntime,
    llm: BaseChatModel,
    schema,
    governance,
    user_id: str,
    role: str,
    context_id: str,
    user_message: str,
    history: list[BaseMessage] | None = None,
    confirmed: bool = False,
    pending_action: dict | None = None,
) -> dict[str, Any]:
    """Run one conversation turn. Returns response text, trace events, and confirmation state."""
    turn_id = str(uuid.uuid4())
    if pending_action and (confirmed or re.search(r"取消|拒绝", user_message)):
        action_name = pending_action.get("action")
        confirmation_id = pending_action.get("confirmation_id")
        params = dict(pending_action.get("params") or {})
        params["confirmation_id"] = confirmation_id
        if confirmed:
            result = runtime.execute_action(user_id, role, action_name, params, True, turn_id)
            response = f"动作 **{action_name}** 已完成。\n\n- 运行状态：{result.get('status')}\n- 运行结果：{result.get('result', result)}"
        else:
            result = runtime.topic_client.commit_action(str(confirmation_id), False) if confirmation_id and hasattr(runtime, "topic_client") else {"status": "rejected"}
            response = f"已取消动作 **{action_name}**，状态：{result.get('status', 'rejected')}。"
        return {"response": response,
                "trace_events": [event.to_dict() for event in runtime.get_trace_events(turn_id)],
                "awaiting_confirmation": False, "pending_action": None, "turn_id": turn_id}

    # Every new question is handled by the model/tool loop below. Topic-specific
    # regex routing and pre-rendered answers can otherwise produce plausible
    # output for objects that do not exist in the selected topic.
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
    context_str = runtime.build_context(user_id, role, context_id, turn_id)
    system_prompt = prompt_builder.build_system_prompt(
        role, context_id, context_str, available_functions, available_actions
    )

    if confirmed and pending_action:
        user_message = f"[用户已确认] {user_message}\n确认执行: {pending_action}"

    messages = [SystemMessage(content=system_prompt)]
    if history:
        messages.extend(history)
    messages.append(HumanMessage(content=user_message))

    def llm_node(state: AgentState) -> AgentState:
        response = llm_with_tools.invoke(state["messages"])
        if not getattr(response, "tool_calls", None):
            parsed_calls = _parse_text_tool_calls(getattr(response, "content", ""))
            if parsed_calls:
                response = AIMessage(content="", tool_calls=parsed_calls)
        return {"messages": [response]}

    def answer_node(state: AgentState) -> AgentState:
        # Tools are intentionally unavailable in the synthesis pass, which
        # prevents repeated query planning while keeping the final answer under
        # model control.
        response = llm.invoke(state["messages"])
        return {"messages": [response]}

    def route_after_llm(state: AgentState) -> str:
        last = state["messages"][-1]
        if hasattr(last, "tool_calls") and last.tool_calls:
            return "tools"
        return "end"

    builder = StateGraph(AgentState)
    builder.add_node("llm_node", llm_node)
    builder.add_node("tool_node", tool_node)
    builder.add_node("answer_node", answer_node)
    builder.set_entry_point("llm_node")
    builder.add_conditional_edges("llm_node", route_after_llm, {"tools": "tool_node", "end": END})
    builder.add_edge("tool_node", "answer_node")
    builder.add_edge("answer_node", END)
    graph = builder.compile()

    initial_state: AgentState = {
        "messages": messages,
        "user_id": user_id,
        "role": role,
        "context_id": context_id,
        "turn_id": turn_id,
        "awaiting_confirmation": False,
        "pending_action": None,
    }

    final_state = graph.invoke(initial_state, config={"recursion_limit": 6})
    last_message = final_state["messages"][-1]
    response_text = last_message.content if hasattr(last_message, "content") else str(last_message)

    trace_events = runtime.get_trace_events(turn_id)
    awaiting = any(e.status == "pending_confirmation" for e in trace_events)
    detected_pending = None
    if awaiting:
        for e in trace_events:
            if e.status == "pending_confirmation":
                detected_pending = {**e.input_summary, **e.output_summary}
                break

    return {
        "response": response_text,
        "trace_events": [e.to_dict() for e in trace_events],
        "awaiting_confirmation": awaiting,
        "pending_action": detected_pending,
        "turn_id": turn_id,
    }

from __future__ import annotations

import json
from typing import Any, Sequence

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import ConfigDict, Field

from ontopilot.nano_topic_provider import NanoTopicClient


class NanoManagedChatModel(BaseChatModel):
    """LangChain adapter for models configured and executed by Nano."""

    client: NanoTopicClient
    selection_id: str
    bound_tools: list[dict[str, Any]] = Field(default_factory=list)
    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def _llm_type(self) -> str:
        return "nano-managed"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {"selection_id": self.selection_id}

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | BaseTool],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ):
        return self.model_copy(update={"bound_tools": [convert_to_openai_tool(item) for item in tools]})

    @staticmethod
    def _message_payload(message: BaseMessage) -> dict[str, Any]:
        if isinstance(message, SystemMessage):
            return {"role": "system", "content": message.content}
        if isinstance(message, HumanMessage):
            return {"role": "user", "content": message.content}
        if isinstance(message, ToolMessage):
            return {"role": "tool", "content": message.content,
                    "tool_call_id": message.tool_call_id}
        if isinstance(message, AIMessage):
            payload: dict[str, Any] = {"role": "assistant", "content": message.content or ""}
            if message.tool_calls:
                payload["tool_calls"] = [{
                    "id": item["id"], "type": "function",
                    "function": {"name": item["name"],
                                 "arguments": json.dumps(item.get("args") or {}, ensure_ascii=False)},
                } for item in message.tool_calls]
            return payload
        return {"role": "user", "content": str(message.content)}

    def _generate(self, messages: list[BaseMessage], stop: list[str] | None = None,
                  run_manager: Any = None, **kwargs: Any) -> ChatResult:
        result = self.client.model_chat(
            self.selection_id,
            [self._message_payload(message) for message in messages],
            self.bound_tools,
        )
        tool_calls = []
        for item in result.get("tool_calls", []):
            try:
                args = json.loads(item.get("arguments") or "{}")
            except (json.JSONDecodeError, TypeError):
                args = {}
            tool_calls.append({"id": item["id"], "name": item["name"],
                               "args": args, "type": "tool_call"})
        message = AIMessage(content=result.get("content") or "", tool_calls=tool_calls)
        return ChatResult(generations=[ChatGeneration(message=message)])

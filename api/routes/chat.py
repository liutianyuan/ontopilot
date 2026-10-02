from __future__ import annotations
import asyncio
import json
import uuid

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage, AIMessage

from api.schemas import ChatRequest, ChatResponse
from api.routes.sessions import session_store
from ontopilot.llm import create_llm_from_config

router = APIRouter()


def _resolve_llm(app_state, model_id: str | None):
    """Get LLM for the given model_id, falling back to the active LLM."""
    if model_id is None:
        return app_state.active_llm

    settings = app_state.settings
    models = settings.get("models", [])
    if not hasattr(app_state, "_llm_cache"):
        app_state._llm_cache = {}

    if model_id not in app_state._llm_cache:
        config = next((m for m in models if m["id"] == model_id), None)
        if config is None:
            return app_state.active_llm
        app_state._llm_cache[model_id] = create_llm_from_config(config)
    return app_state._llm_cache[model_id]


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, req: Request):
    app_state = req.app.state

    # Resolve model and ontology
    try:
        llm = _resolve_llm(app_state, request.model_id)
        if not request.ontology_id:
            raise ValueError("请选择知识主题")
        from api.nano_identity import bearer_token
        from api.main import build_nano_topic_runtime
        runtime, schema, governance, delegated_identity = build_nano_topic_runtime(
            request.ontology_id, bearer_token(req), app_state.audit_logger,
            resolve_identity=True,
        )
    except Exception as e:
        return ChatResponse(
            session_id=request.session_id or "",
            response=f"❌ 无法初始化当前知识主题会话：{str(e)}\n\n请检查主题访问权限、Nano 服务和模型配置。",
            turn_id=str(uuid.uuid4()),
            awaiting_confirmation=False,
            pending_action=None,
            trace_events=[],
        )

    effective_user_id = delegated_identity["user_id"]
    effective_role = delegated_identity["role"]
    session_id = request.session_id
    existing_session = session_store.get(session_id) if session_id else None
    if existing_session and (
        existing_session.get("user_id") != effective_user_id
        or (request.ontology_id and existing_session.get("topic_id") not in {None, request.ontology_id})
    ):
        return ChatResponse(
            session_id="",
            response="❌ 当前会话不属于该用户或知识主题，请新建对话。",
            turn_id=str(uuid.uuid4()),
            awaiting_confirmation=False,
            pending_action=None,
            trace_events=[],
        )
    if not session_id or session_store.get(session_id) is None:
        session_id = session_store.create_session(
            effective_user_id, effective_role, request.context_id, request.ontology_id
        )

    session = session_store.get(session_id)

    # Wire up real-time trace event streaming via SSE
    runtime._event_callback = lambda e: session_store.push_event(session_id, e)

    from ontopilot.agent import run_turn
    from functools import partial
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, partial(
            run_turn,
            runtime=runtime, llm=llm, schema=schema, governance=governance,
            user_id=session["user_id"],
            role=session["role"],
            context_id=session["context_id"],
            user_message=request.message,
            history=session_store.get_history(session_id),
            confirmed=request.confirmed,
            pending_action=session.get("pending_action"),
        ))
    except Exception as e:
        # Push end-of-turn so SSE client knows to stop waiting
        session_store.push_event(session_id, {"__end_of_turn__": True})
        return ChatResponse(
            session_id=session_id,
            response=f"❌ 处理请求时出错：{str(e)}",
            turn_id=str(uuid.uuid4()),
            awaiting_confirmation=False,
            pending_action=None,
            trace_events=[],
        )
    finally:
        runtime._event_callback = None

    trace_events = result.get("trace_events", [])
    session_store.add_message(session_id, "human", request.message)
    session_store.add_message(
        session_id,
        "ai",
        result["response"],
        trace_events=trace_events,
        awaiting_confirmation=result.get("awaiting_confirmation", False),
        turn_id=result.get("turn_id"),
    )
    session_store.update(
        session_id,
        pending_action=result.get("pending_action"),
    )

    # Push end-of-turn marker (trace events were already streamed in real-time via _event_callback)
    session_store.push_event(session_id, {"__end_of_turn__": True})

    return ChatResponse(
        session_id=session_id,
        response=result["response"],
        turn_id=result.get("turn_id", str(uuid.uuid4())),
        awaiting_confirmation=result.get("awaiting_confirmation", False),
        pending_action=result.get("pending_action"),
        trace_events=trace_events,
    )


@router.get("/chat/stream")
async def chat_stream(session_id: str):
    async def event_generator():
        q = session_store.get_queue(session_id)
        if q is None:
            yield f"data: {json.dumps({'error': 'Session not found'})}\n\n"
            return
        while True:
            try:
                event = await asyncio.wait_for(q.get(), timeout=30.0)
                if event.get("__end_of_turn__"):
                    # Keep the stream alive for the next turn's real-time events
                    yield f"data: {json.dumps({'type': 'end', '__end_of_turn__': True})}\n\n"
                    continue
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            except asyncio.TimeoutError:
                yield f"data: {json.dumps({'type': 'keepalive'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

from __future__ import annotations
import asyncio
import json
import os
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


def _resolve_ontology(app_state, ontology_id: str | None):
    """Switch ontology if requested, rebuild runtime."""
    if ontology_id is None:
        return
    current = getattr(app_state, "current_ontology_id", None)
    if ontology_id == current:
        return
    config_dir = app_state.config_dir
    path = os.path.join(config_dir, ontology_id)
    if not os.path.exists(path):
        return

    from ontopilot.runtime import OntologyRuntime
    from ontopilot.schema import SchemaRegistry
    from ontopilot.governance import PermissionEvaluator
    from ontopilot.audit import AuditLogger

    # Detect companion config files
    prefix = None
    for suffix in ("_ontology.yaml", "_ontology.yml", "_schema.yaml", "_schema.yml"):
        if ontology_id.endswith(suffix) and ontology_id != suffix:
            prefix = ontology_id[: -len(suffix)]
            break

    def companion(name: str) -> str | None:
        if not prefix:
            return None
        p = os.path.join(config_dir, f"{prefix}_{name}")
        return p if os.path.exists(p) else None

    # If prefix detected but no companion seed file, skip seed loading entirely
    seed_arg = companion("seed.yaml")
    if prefix is not None and seed_arg is None:
        seed_arg = OntologyRuntime._SKIP_SEED

    app_state.schema = SchemaRegistry(path)
    app_state.runtime = OntologyRuntime.from_config(
        config_dir,
        schema_path=path,
        seed_path=seed_arg,
        permissions_path=companion("permissions.yaml"),
        context_path=companion("context.yaml"),
    )
    app_state.governance = PermissionEvaluator(
        companion("permissions.yaml") or os.path.join(config_dir, "permissions.yaml")
    )
    app_state.audit_logger = AuditLogger(".ontopilot.db")
    app_state.current_ontology_id = ontology_id


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, req: Request):
    app_state = req.app.state

    # Resolve model and ontology
    try:
        llm = _resolve_llm(app_state, request.model_id)
        _resolve_ontology(app_state, request.ontology_id)
    except Exception as e:
        return ChatResponse(
            session_id=request.session_id or "",
            response=f"❌ 模型初始化失败：{str(e)}\n\n请检查模型配置中的 API Key 是否正确。",
            turn_id=str(uuid.uuid4()),
            awaiting_confirmation=False,
            pending_action=None,
            trace_events=[],
        )

    runtime = app_state.runtime
    schema = app_state.schema
    governance = app_state.governance

    session_id = request.session_id
    if not session_id or session_store.get(session_id) is None:
        session_id = session_store.create_session(
            request.user_id, request.role, request.warehouse_id
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
            warehouse_id=session["warehouse_id"],
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

    session_store.add_message(session_id, "human", request.message)
    session_store.add_message(session_id, "ai", result["response"])
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
        trace_events=result.get("trace_events", []),
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

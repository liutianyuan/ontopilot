from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request
from pydantic import BaseModel

from ontopilot.llm import create_llm_from_config, load_settings, save_settings

router = APIRouter()


class SettingsUpdate(BaseModel):
    settings: dict


@router.get("/runtime/models")
async def runtime_models(request: Request) -> dict:
    """Expose selectable models without returning credentials."""
    settings = request.app.state.settings
    return {
        "models": [
            {
                "id": item.get("id"),
                "name": item.get("name") or item.get("model"),
                "model": item.get("model"),
                "provider": item.get("provider"),
                "is_default": item.get("id") == settings.get("active_model_id"),
            }
            for item in settings.get("models", [])
            if item.get("id") and item.get("model")
        ]
    }


@router.get("/settings")
async def get_settings(request: Request) -> dict:
    return load_settings(request.app.state.config_dir)


@router.put("/settings")
async def put_settings(body: SettingsUpdate, request: Request) -> dict:
    config_dir = request.app.state.config_dir
    save_settings(body.settings, config_dir)
    request.app.state.settings = body.settings
    models = body.settings.get("models", [])
    active_id = body.settings.get("active_model_id")
    if models and active_id:
        request.app.state.active_llm = create_llm_from_config(
            next(model for model in models if model["id"] == active_id)
        )
    return {"status": "ok"}


@router.post("/settings/test-model")
async def test_model(body: dict) -> dict:
    try:
        config = body.get("config", {})
        if not config.get("model") or not config.get("provider"):
            return {"status": "error", "message": "请填写模型名称和提供商"}
        llm = create_llm_from_config(config)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, llm.invoke, "Hello, respond with just: OK")
        return {"status": "ok", "message": "连通性测试成功"}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


@router.get("/ontology/status")
async def ontology_status(request: Request) -> dict:
    """Compatibility endpoint; topic definitions are owned by Nano."""
    schema = request.app.state.schema
    if schema is None:
        return {"source": "nano", "object_types": [], "actions": [], "functions": []}
    return {
        "source": "nano",
        "object_types": schema.object_type_names,
        "actions": schema.action_names,
        "functions": schema.function_names,
    }

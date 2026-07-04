from __future__ import annotations
import os
import yaml
from typing import Any
from langchain_core.language_models import BaseChatModel


def create_llm_from_config(model_config: dict[str, Any]) -> BaseChatModel:
    """Create an LLM from a model config dict (from settings.yaml models list)."""
    provider = model_config.get("provider", "anthropic")
    # Try direct api_key first, then fall back to environment variable
    api_key = model_config.get("api_key", "") or os.environ.get(model_config.get("api_key_env", ""), "")
    kwargs = {
        "model": model_config.get("model", ""),
        "api_key": api_key,
        "max_tokens": model_config.get("max_tokens", 4096),
        "temperature": model_config.get("temperature", 0),
    }

    if provider in ("anthropic", "anthropic_compatible"):
        from langchain_anthropic import ChatAnthropic
        base_url = model_config.get("base_url", "")
        if base_url:
            kwargs["anthropic_api_url"] = base_url
        return ChatAnthropic(**kwargs)
    elif provider in ("openai", "openai_compatible"):
        from langchain_openai import ChatOpenAI
        base_url = model_config.get("base_url", "")
        if base_url:
            kwargs["base_url"] = base_url
        return ChatOpenAI(**kwargs)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


def create_llm(config_dir: str = "config", model_id: str | None = None) -> BaseChatModel:
    with open(os.path.join(config_dir, "settings.yaml"), encoding="utf-8") as f:
        settings = yaml.safe_load(f)

    models = settings.get("models", [])
    if not models:
        raise ValueError("No models configured in settings.yaml")

    if model_id is None:
        model_id = settings.get("active_model_id", models[0]["id"])

    model_config = next((m for m in models if m["id"] == model_id), models[0])
    return create_llm_from_config(model_config)


def load_settings(config_dir: str = "config") -> dict:
    with open(os.path.join(config_dir, "settings.yaml"), encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_settings(settings: dict, config_dir: str = "config") -> None:
    path = os.path.join(config_dir, "settings.yaml")
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(settings, f, default_flow_style=False, allow_unicode=True)

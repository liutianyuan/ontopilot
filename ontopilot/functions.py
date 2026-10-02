from __future__ import annotations

from collections.abc import Callable
from typing import Any


FUNCTION_PARAMS: dict[str, dict[str, Any]] = {}


class FunctionRegistry:
    """Schema-neutral registry for optional deployment-provided executors.

    Published knowledge topics do not use local function names. Their rule
    definitions and evaluations are supplied by Nano's topic runtime API.
    """

    def __init__(self, _schema: Any, _store: Any,
                 executors: dict[str, Callable[[dict[str, Any]], Any]] | None = None):
        self._fns = dict(executors or {})

    def register(self, name: str, executor: Callable[[dict[str, Any]], Any]) -> None:
        if not name:
            raise ValueError("Executor name is required")
        self._fns[name] = executor

    def call(self, function_name: str, params: dict[str, Any]) -> Any:
        executor = self._fns.get(function_name)
        if executor is None:
            raise KeyError(
                f"No local executor is registered for '{function_name}'. "
                "Publish the rule in Nano or register a deployment adapter."
            )
        return executor(params)

from __future__ import annotations

import os

from fastapi import HTTPException, Request

from ontopilot.nano_topic_provider import NanoTopicClient, NanoTopicRequestError


def bearer_token(request: Request) -> str:
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(401, "缺少 nano 登录令牌")
    return token.strip()


def nano_client(request: Request, topic_id: str = "") -> NanoTopicClient:
    return NanoTopicClient(
        os.getenv("NANO_API_BASE", "http://127.0.0.1:10081/api/v1"),
        topic_id,
        token=bearer_token(request),
    )


def delegated_identity(request: Request) -> dict:
    try:
        return nano_client(request).identity()
    except NanoTopicRequestError as exc:
        raise HTTPException(401, str(exc)) from exc

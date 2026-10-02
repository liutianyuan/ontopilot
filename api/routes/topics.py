from fastapi import APIRouter, HTTPException, Request

from api.nano_identity import nano_client
from ontopilot.nano_topic_provider import NanoTopicRequestError


router = APIRouter()


@router.get("/topics")
async def list_topics(request: Request) -> dict:
    try:
        return {"topics": nano_client(request).topics()}
    except NanoTopicRequestError as exc:
        raise HTTPException(502, str(exc)) from exc


@router.get("/topics/{topic_id}/manifest")
async def topic_manifest(topic_id: str, request: Request) -> dict:
    try:
        return nano_client(request, topic_id).manifest()
    except NanoTopicRequestError as exc:
        raise HTTPException(502, str(exc)) from exc

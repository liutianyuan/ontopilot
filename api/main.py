from __future__ import annotations
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.chat import router as chat_router
from api.routes.audit import router as audit_router
from ontopilot.runtime import OntologyRuntime
from ontopilot.llm import create_llm, load_settings
from ontopilot.schema import SchemaRegistry
from ontopilot.governance import PermissionEvaluator
from ontopilot.audit import AuditLogger
from ontopilot.nano_provider import NanoOntologyProvider
from ontopilot.nano_topic_provider import (NanoActionExecutor, NanoContextBuilder,
                                           NanoObjectStore, NanoPermissionEvaluator,
                                           NanoSchemaRegistry, NanoTopicClient)


def build_nano_topic_runtime(topic_id: str, token: str | None, audit_logger: AuditLogger,
                             resolve_identity: bool = False):
    """Create a per-request runtime so Nano enforces the delegated user token."""
    topic_client = NanoTopicClient(
        os.getenv("NANO_API_BASE", "http://127.0.0.1:10081/api/v1"), topic_id, token=token,
    )
    manifest = topic_client.manifest()
    schema = NanoSchemaRegistry(manifest)
    store = NanoObjectStore(topic_client, schema)
    governance = NanoPermissionEvaluator(manifest)
    context = NanoContextBuilder(manifest)
    from ontopilot.functions import FunctionRegistry
    runtime = OntologyRuntime(schema, store, governance, context, FunctionRegistry(schema, store),
                              NanoActionExecutor(topic_client, schema, governance), audit_logger, None)
    identity = topic_client.identity() if resolve_identity else None
    return runtime, schema, governance, identity


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.config_dir = "config"
    app.state.settings = load_settings(app.state.config_dir)
    app.state.active_llm = create_llm(app.state.config_dir)
    app.state.audit_logger = AuditLogger(".ontopilot.db")
    nano_topic_id = os.getenv("NANO_TOPIC_ID")
    if nano_topic_id:
        app.state.runtime, schema, governance, _ = build_nano_topic_runtime(
            nano_topic_id, os.getenv("NANO_API_TOKEN"), app.state.audit_logger,
        )
        app.state.schema = schema
        app.state.governance = governance
        app.state.current_ontology_id = nano_topic_id
        app.state.nano_topic_client = None
    else:
        app.state.runtime = OntologyRuntime.from_config(app.state.config_dir)
        app.state.schema = SchemaRegistry(f"{app.state.config_dir}/ontology_schema.yaml")
        app.state.governance = PermissionEvaluator(f"{app.state.config_dir}/permissions.yaml")
        app.state.current_ontology_id = "ontology_schema.yaml"
    nano_ontology_id = os.getenv("NANO_ONTOLOGY_ID")
    app.state.nano_provider = NanoOntologyProvider(
        os.getenv("NANO_API_BASE", "http://127.0.0.1:10081/api/v1"), nano_ontology_id,
        token=os.getenv("NANO_API_TOKEN"), username=os.getenv("NANO_USERNAME"),
        password=os.getenv("NANO_PASSWORD"),
    ) if nano_ontology_id else None
    app.state.runtime.nano_provider = app.state.nano_provider
    yield


app = FastAPI(title="基于知识编织的智能体平台 API", lifespan=lifespan)

default_cors_origins = ",".join([
    "http://localhost:5173", "http://localhost:5174", "http://localhost:10081",
    "http://127.0.0.1:10081",
])
cors_origins = [origin.strip() for origin in os.getenv("CORS_ALLOWED_ORIGINS", default_cors_origins).split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from api.routes.settings import router as settings_router
from api.routes.users import router as users_router
from api.routes.sessions import router as sessions_router
from api.routes.nephrology import router as nephrology_router

app.include_router(chat_router, prefix="/api")
app.include_router(audit_router, prefix="/api")
app.include_router(settings_router, prefix="/api")
app.include_router(users_router, prefix="/api")
app.include_router(sessions_router, prefix="/api")
app.include_router(nephrology_router, prefix="/api")

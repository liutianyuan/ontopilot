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


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.config_dir = "config"
    app.state.settings = load_settings(app.state.config_dir)
    app.state.active_llm = create_llm(app.state.config_dir)
    app.state.runtime = OntologyRuntime.from_config(app.state.config_dir)
    app.state.schema = SchemaRegistry(f"{app.state.config_dir}/ontology_schema.yaml")
    app.state.governance = PermissionEvaluator(f"{app.state.config_dir}/permissions.yaml")
    app.state.audit_logger = AuditLogger(".ontopilot.db")
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
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

from __future__ import annotations
import os
import yaml
from fastapi import APIRouter, Request, UploadFile, File, HTTPException
from pydantic import BaseModel
from ontopilot.llm import create_llm_from_config, load_settings, save_settings

router = APIRouter()


class SettingsUpdate(BaseModel):
    settings: dict


@router.get("/settings")
async def get_settings(request: Request) -> dict:
    return load_settings(request.app.state.config_dir)


@router.put("/settings")
async def put_settings(body: SettingsUpdate, request: Request) -> dict:
    config_dir = request.app.state.config_dir
    save_settings(body.settings, config_dir)

    settings = body.settings
    request.app.state.settings = settings
    models = settings.get("models", [])
    active_id = settings.get("active_model_id")
    if models and active_id:
        request.app.state.active_llm = create_llm_from_config(
            next(m for m in models if m["id"] == active_id)
        )
    return {"status": "ok"}


@router.post("/settings/test-model")
async def test_model(body: dict) -> dict:
    try:
        config = body.get("config", {})
        if not config.get("model") or not config.get("provider"):
            return {"status": "error", "message": "请填写模型名称和提供商"}
        import asyncio
        llm = create_llm_from_config(config)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, llm.invoke, "Hello, respond with just: OK")
        return {"status": "ok", "message": "连通性测试成功"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/ontology/status")
async def ontology_status(request: Request) -> dict:
    schema = request.app.state.schema
    return {
        "object_types": schema.object_type_names,
        "actions": schema.action_names,
        "functions": schema.function_names,
        "seed_loaded": True,
    }


@router.get("/ontology/list")
async def list_ontologies(request: Request) -> dict:
    config_dir = request.app.state.config_dir
    ontologies = []
    for fname in os.listdir(config_dir):
        if not fname.endswith((".yaml", ".yml")):
            continue
        if fname in ("settings.yaml", "permissions.yaml", "seed_data.yaml"):
            continue
        path = os.path.join(config_dir, fname)
        try:
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if data and "object_types" in data:
                ot = list(data["object_types"].keys())
                actions = list(data.get("actions", {}).keys())
                functions = list(data.get("functions", {}).keys())
                ontologies.append({
                    "id": fname,
                    "name": fname.replace(".yaml", "").replace(".yml", "").replace("_", " ").title(),
                    "filename": fname,
                    "object_types": ot,
                    "actions": actions,
                    "functions": functions,
                })
        except Exception:
            continue
    return {"ontologies": ontologies}


@router.post("/ontology/upload")
async def upload_ontology(files: list[UploadFile] = File(...), request: Request = None) -> dict:
    config_dir = request.app.state.config_dir

    ontology_path = None
    saved = []

    for file in files:
        if not file.filename.endswith((".yaml", ".yml")):
            continue
        content = await file.read()
        raw = yaml.safe_load(content)
        if not isinstance(raw, dict):
            continue

        dest = os.path.join(config_dir, file.filename)
        with open(dest, "wb") as f:
            f.write(content)
        saved.append(file.filename)

        if "object_types" in raw:
            ontology_path = dest

    if not ontology_path:
        # Clean up any files we saved
        for fname in saved:
            path = os.path.join(config_dir, fname)
            if os.path.exists(path) and fname != ontology_path:
                os.remove(path)
        raise HTTPException(400, "未找到包含 object_types 的 Ontology YAML 文件")

    result = _rebuild_runtime(request, config_dir, ontology_path)
    filenames = ", ".join(saved)
    return {"status": "ok", "message": f"已导入文件: {filenames}", "filename": ontology_path, **result}


@router.post("/ontology/import")
async def import_ontology(request: Request) -> dict:
    config_dir = request.app.state.config_dir
    schema_path = os.path.join(config_dir, "ontology_schema.yaml")
    result = _rebuild_runtime(request, config_dir, schema_path)
    return {"status": "ok", "message": "种子数据已重新加载", **result}


@router.get("/ontology/detail/{filename}")
async def ontology_detail(filename: str, request: Request) -> dict:
    config_dir = request.app.state.config_dir
    path = os.path.join(config_dir, filename)
    if not os.path.exists(path):
        raise HTTPException(404, f"Ontology file not found: {filename}")
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    object_types = data.get("object_types", {})
    actions = data.get("actions", {})
    functions_ = data.get("functions", {})
    detail_types = []
    for name, defn in object_types.items():
        props = defn.get("properties", {})
        links = defn.get("links", {})
        detail_types.append({
            "name": name,
            "description": defn.get("description", ""),
            "properties": [
                {"name": k, "type": v.get("type", "string"), "description": v.get("description", "")}
                for k, v in props.items()
            ],
            "links": [
                {"name": k, "target": v.get("target", "")}
                for k, v in links.items()
            ],
        })
    detail_actions = [
        {"name": name, "params": defn.get("params", []), "description": defn.get("description", "")}
        for name, defn in actions.items()
    ]
    detail_functions = [
        {"name": name, "params": defn.get("params", []), "description": defn.get("description", "")}
        for name, defn in functions_.items()
    ]
    tools = []
    for name, defn in object_types.items():
        for op in ("query", "get", "count", "search", "traverse"):
            tools.append(f"{op}_{name}")
    for name in actions:
        tools.append(f"execute_action:{name}")
    for name in functions_:
        tools.append(f"call_function:{name}")
    return {
        "object_types": detail_types,
        "actions": detail_actions,
        "functions": detail_functions,
        "tools": sorted(tools),
    }


@router.delete("/ontology/{filename}")
async def delete_ontology(filename: str, request: Request) -> dict:
    config_dir = request.app.state.config_dir
    path = os.path.join(config_dir, filename)
    if not os.path.exists(path):
        raise HTTPException(404, f"Ontology file not found: {filename}")
    # Prevent deleting the currently active ontology
    current = getattr(request.app.state, "current_ontology_id", None)
    if filename == current:
        raise HTTPException(400, "无法删除当前激活的本体，请先切换到其他本体")
    os.remove(path)
    return {"status": "ok", "message": f"已删除: {filename}"}


@router.post("/ontology/activate")
async def activate_ontology(body: dict, request: Request) -> dict:
    config_dir = request.app.state.config_dir
    filename = body.get("filename", "")
    path = os.path.join(config_dir, filename)
    if not os.path.exists(path):
        raise HTTPException(404, f"Ontology file not found: {filename}")
    result = _rebuild_runtime(request, config_dir, path)
    return {"status": "ok", "message": f"已切换到: {filename}", **result}


def _rebuild_runtime(request: Request, config_dir: str, schema_path: str) -> dict:
    from ontopilot.runtime import OntologyRuntime
    from ontopilot.schema import SchemaRegistry
    from ontopilot.governance import PermissionEvaluator
    from ontopilot.audit import AuditLogger

    # Detect companion config files for non-default ontologies
    # e.g. procurement_ontology.yaml → procurement_seed.yaml, procurement_permissions.yaml, etc.
    schema_basename = os.path.basename(schema_path)
    prefix = None
    for suffix in ("_ontology.yaml", "_ontology.yml", "_schema.yaml", "_schema.yml"):
        if schema_basename.endswith(suffix) and schema_basename != suffix:
            prefix = schema_basename[: -len(suffix)]
            break

    def companion(name: str) -> str | None:
        """Return companion path if prefix exists and file exists, else None."""
        if not prefix:
            return None
        path = os.path.join(config_dir, f"{prefix}_{name}")
        return path if os.path.exists(path) else None

    def has_prefix() -> bool:
        return prefix is not None

    q = request.app.state

    q.schema = SchemaRegistry(schema_path)
    # If prefix detected but no companion seed file, skip seed loading entirely
    seed_arg = companion("seed.yaml")
    if has_prefix() and seed_arg is None:
        seed_arg = OntologyRuntime._SKIP_SEED
    q.runtime = OntologyRuntime.from_config(
        config_dir,
        schema_path=schema_path,
        seed_path=seed_arg,
        permissions_path=companion("permissions.yaml"),
        context_path=companion("context.yaml"),
    )
    q.governance = PermissionEvaluator(
        companion("permissions.yaml") or os.path.join(config_dir, "permissions.yaml")
    )
    q.audit_logger = AuditLogger(".ontopilot.db")
    q.current_ontology_id = schema_basename

    schema = q.schema
    return {
        "object_types": schema.object_type_names,
        "actions": schema.action_names,
        "functions": schema.function_names,
        "object_type_count": len(schema.object_type_names),
        "action_count": len(schema.action_names),
        "function_count": len(schema.function_names),
        "tools_created": (
            len(schema.object_type_names) * 5
            + len(schema.action_names)
            + len(schema.function_names)
        ),
    }

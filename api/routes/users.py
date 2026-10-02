from __future__ import annotations
import copy
import os
import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()
USERS_PATH = "config/users.yaml"
PERMS_PATH = "config/permissions.yaml"


def _load_users() -> list[dict]:
    if not os.path.exists(USERS_PATH):
        return []
    with open(USERS_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("users", [])


def _save_users(users: list[dict]) -> None:
    with open(USERS_PATH, "w", encoding="utf-8") as f:
        yaml.dump({"users": users}, f, allow_unicode=True, default_flow_style=False)


def _load_permissions() -> dict:
    with open(PERMS_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _save_permissions(data: dict) -> None:
    with open(PERMS_PATH, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)


# ── Login ─────────────────────────────────────────────────────────────────


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
async def login(body: LoginRequest) -> dict:
    users = _load_users()
    for u in users:
        if u["username"] == body.username and u["password"] == body.password:
            return {
                "status": "ok",
                "user": {k: v for k, v in u.items() if k != "password"},
            }
    raise HTTPException(401, "用户名或密码错误")


# ── User CRUD ────────────────────────────────────────────────────────────


class UserCreate(BaseModel):
    username: str
    password: str
    role: str
    display_name: str


class UserUpdate(BaseModel):
    password: str | None = None
    role: str | None = None
    display_name: str | None = None


@router.get("/users")
async def list_users() -> dict:
    users = _load_users()
    # Never expose passwords in list
    safe = [{k: v for k, v in u.items() if k != "password"} for u in users]
    return {"users": safe}


@router.post("/users")
async def create_user(body: UserCreate) -> dict:
    users = _load_users()
    if any(u["username"] == body.username for u in users):
        raise HTTPException(400, f"Username '{body.username}' already exists")
    new_id = f"user_{len(users) + 1:03d}"
    users.append({
        "id": new_id,
        "username": body.username,
        "password": body.password,
        "role": body.role,
        "display_name": body.display_name,
    })
    _save_users(users)
    return {"status": "ok", "user": {k: v for k, v in users[-1].items() if k != "password"}}


@router.put("/users/{user_id}")
async def update_user(user_id: str, body: UserUpdate) -> dict:
    users = _load_users()
    for u in users:
        if u["id"] == user_id:
            if body.password is not None:
                u["password"] = body.password
            if body.role is not None:
                u["role"] = body.role
            if body.display_name is not None:
                u["display_name"] = body.display_name
            _save_users(users)
            return {"status": "ok", "user": {k: v for k, v in u.items() if k != "password"}}
    raise HTTPException(404, f"User {user_id} not found")


@router.delete("/users/{user_id}")
async def delete_user(user_id: str) -> dict:
    users = _load_users()
    for i, u in enumerate(users):
        if u["id"] == user_id:
            if u["role"] == "admin":
                # Don't allow deleting the last admin
                admins = [x for x in users if x["role"] == "admin"]
                if len(admins) <= 1:
                    raise HTTPException(400, "Cannot delete the last admin account")
            users.pop(i)
            _save_users(users)
            return {"status": "ok"}
    raise HTTPException(404, f"User {user_id} not found")


# ── Role Permissions ─────────────────────────────────────────────────────


class RolePermUpdate(BaseModel):
    query_types: list[str] | None = None
    functions: list[str] | None = None
    actions: dict | None = None
    data_scope: dict | None = None


@router.get("/roles")
async def list_roles() -> dict:
    perms = _load_permissions()
    return {"roles": perms.get("roles", {})}


@router.put("/roles/{role_name}")
async def update_role(role_name: str, body: RolePermUpdate) -> dict:
    perms = _load_permissions()
    roles = perms.get("roles", {})
    if role_name not in roles:
        raise HTTPException(404, f"Role '{role_name}' not found")

    role = roles[role_name]
    if body.query_types is not None:
        role["query_types"] = body.query_types
    if body.functions is not None:
        role["functions"] = body.functions
    if body.actions is not None:
        role["actions"] = body.actions
    if body.data_scope is not None:
        role["data_scope"] = body.data_scope

    _save_permissions(perms)
    return {"status": "ok", "role": role}

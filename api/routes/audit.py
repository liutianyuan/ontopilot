from fastapi import APIRouter, Request
from api.schemas import AuditEntry

router = APIRouter()


@router.get("/audit", response_model=list[AuditEntry])
async def get_audit(req: Request, user_id: str | None = None, limit: int = 50):
    audit_logger = req.app.state.audit_logger
    entries = audit_logger.get_entries(user_id=user_id, limit=limit)
    return entries

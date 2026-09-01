from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter()


def _provider(request: Request):
    provider = getattr(request.app.state, "nano_provider", None)
    if provider is None:
        raise HTTPException(503, "nano-ontoprompt provider is not configured")
    return provider


@router.get("/nephrology/schema")
def schema(request: Request):
    adapter = _provider(request).schema()
    return {"ontology_id": adapter.ontology_id, "version": adapter.version,
            "types": adapter.type_names, "bundle": adapter.bundle}


@router.get("/nephrology/patients/{patient_id}")
def patient(patient_id: str, request: Request):
    return _provider(request).patient_summary(patient_id)


@router.get("/nephrology/patients/{patient_id}/timeline")
def timeline(patient_id: str, request: Request):
    return _provider(request).patient_timeline(patient_id)


@router.get("/nephrology/alerts")
def alerts(request: Request, patient_id: str | None = None, status: str | None = None):
    return _provider(request).alerts(patient_id, status)


@router.post("/nephrology/alerts/{alert_id}/preview")
def preview(alert_id: str, request: Request):
    return _provider(request).preview_alert_action(alert_id)


class Decision(BaseModel):
    approved: bool


@router.post("/nephrology/confirmations/{confirmation_id}")
def decide(confirmation_id: str, body: Decision, request: Request):
    return _provider(request).decide(confirmation_id, body.approved)


@router.get("/nephrology/action-runs/{run_id}")
def action_run(run_id: str, request: Request):
    return _provider(request).action_run(run_id)

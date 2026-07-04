from __future__ import annotations
import uuid
from datetime import datetime, timezone
from ontopilot.schema import SchemaRegistry, ActionDef
from ontopilot.store import ObjectStore
from ontopilot.governance import PermissionEvaluator


class ActionExecutor:
    def __init__(
        self,
        schema: SchemaRegistry,
        store: ObjectStore,
        governance: PermissionEvaluator,
    ):
        self._schema = schema
        self._store = store
        self._governance = governance

    def _validate_params(self, action: ActionDef, params: dict) -> None:
        for pname, pinfo in action.params.items():
            if pinfo.get("required") and pname not in params:
                raise KeyError(
                    f"Action '{action.name}' requires parameter '{pname}'"
                )

    def preview(self, role: str, action_name: str, params: dict) -> dict:
        action = self._schema.get_action(action_name)
        self._validate_params(action, params)
        requires_confirmation = self._governance.get_action_confirmation(role, action_name)

        target_id = params.get("shipmentId") or params.get("caseId", "unknown")
        target = f"{action.target_type}:{target_id}"

        changes = self._compute_changes(action, params)
        estimated_impact = self._estimate_impact(action, params)

        return {
            "status": "pending_confirmation" if requires_confirmation else "previewed",
            "action": action_name,
            "target": target,
            "changes": changes,
            "estimated_impact": estimated_impact,
            "requires_confirmation": requires_confirmation,
        }

    def execute(
        self,
        role: str,
        user_id: str,
        action_name: str,
        params: dict,
        confirmed: bool,
    ) -> dict:
        action = self._schema.get_action(action_name)
        requires_confirmation = self._governance.get_action_confirmation(role, action_name)

        if requires_confirmation and not confirmed:
            raise PermissionError(
                f"Action '{action_name}' requires user confirmation before execution."
            )

        self._validate_params(action, params)

        if action.creates:
            result_obj = self._create_object(action, params, user_id)
        else:
            result_obj = self._edit_object(action, params)

        return {
            "status": "executed",
            "action": action_name,
            "result": result_obj,
        }

    def _resolve_target_id(self, params: dict) -> str | None:
        """Find the target object ID from params, trying known keys."""
        for key in ("shipmentId", "caseId", "person_id", "project_id", "id", "batchId", "planId", "materialId", "supplierId"):
            if key in params:
                return params[key]
        return None

    def _compute_changes(self, action: ActionDef, params: dict) -> list[dict]:
        changes = []
        if action.creates:
            return [{"type": "create", "object_type": action.target_type, "data": params}]

        from ontopilot.schema import ObjectTypeDef
        target_id = self._resolve_target_id(params)
        current = self._store.get(action.target_type, target_id) if target_id else {}
        edits_raw = action.edits

        # Flat dict format: {field: param_key}
        if isinstance(edits_raw, dict):
            for field, param_key in edits_raw.items():
                new_val = params.get(param_key)
                changes.append({
                    "field": field,
                    "from": current.get(field) if current else None,
                    "to": new_val,
                })
        # List-of-objects format (complex action defs)
        elif isinstance(edits_raw, list):
            for edit_item in edits_raw:
                set_fields = edit_item.get("set", {})
                for field, param_key in set_fields.items():
                    resolved = self._resolve_template(param_key, params)
                    changes.append({
                        "field": field,
                        "from": current.get(field) if current else None,
                        "to": resolved,
                    })
        return changes

    def _resolve_template(self, template: str, params: dict) -> str:
        """Resolve {param_name} templates with actual values."""
        import re
        def replacer(m: re.Match) -> str:
            key = m.group(1)
            return str(params.get(key, m.group(0)))
        return re.sub(r'\{(\w+)\}', replacer, template)

    def _estimate_impact(self, action: ActionDef, params: dict) -> dict:
        if action.name == "assignCarrier":
            shipment = self._store.get("Shipment", params.get("shipmentId", ""))
            if shipment:
                old_carrier = self._store.get("Carrier", shipment.get("carrierId", ""))
                new_carrier = self._store.get("Carrier", params.get("newCarrierId", ""))
                if old_carrier and new_carrier:
                    weight = shipment.get("weightKg", 0)
                    cost_delta = weight * (new_carrier["pricePerKg"] - old_carrier["pricePerKg"])
                    transit_delta = new_carrier["avgTransitHours"] - old_carrier["avgTransitHours"]
                    return {
                        "cost_delta": round(cost_delta, 2),
                        "estimated_delivery_delta_hours": round(transit_delta, 1),
                    }
        return {}

    def _edit_object(self, action: ActionDef, params: dict) -> dict:
        target_id = self._resolve_target_id(params)
        changes = {}
        edits_raw = action.edits
        if isinstance(edits_raw, dict):
            for field, param_key in edits_raw.items():
                changes[field] = params.get(param_key)
        elif isinstance(edits_raw, list):
            for edit_item in edits_raw:
                for field, template in edit_item.get("set", {}).items():
                    changes[field] = self._resolve_template(template, params)
        return self._store.update(action.target_type, target_id, changes)

    def _create_object(self, action: ActionDef, params: dict, user_id: str) -> dict:
        data = dict(params)
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        if action.target_type == "Shipment":
            data["shipmentId"] = f"SH-NEW-{uuid.uuid4().hex[:6].upper()}"
            data["status"] = "pending"
            data["delayReason"] = None
            data["createdAt"] = now_iso
            from datetime import timedelta
            carrier = self._store.get("Carrier", data.get("carrierId", ""))
            transit_h = carrier.get("avgTransitHours", 24) if carrier else 24
            eta = now + timedelta(hours=transit_h)
            data["ETA"] = eta.isoformat()
            data["originalETA"] = eta.isoformat()
        elif action.target_type == "ExceptionCase":
            data["caseId"] = f"CASE-{uuid.uuid4().hex[:8].upper()}"
            data["status"] = "open"
            data["createdBy"] = user_id
            data["createdAt"] = now
        elif action.target_type == "AllocationPlan":
            data["planId"] = f"PLAN-{uuid.uuid4().hex[:6].upper()}"
            data["status"] = "draft"
            data["createdAt"] = now
            data["updatedAt"] = now
        elif action.target_type == "SupplierScore":
            data["scoreId"] = f"SCORE-{uuid.uuid4().hex[:6].upper()}"
            ds = data.get("deliveryScore", 0)
            qs = data.get("qualityScore", 0)
            cs = data.get("complianceScore", 0)
            data["overallScore"] = round((ds + qs + cs) / 3, 1)
        return self._store.create(action.target_type, data)

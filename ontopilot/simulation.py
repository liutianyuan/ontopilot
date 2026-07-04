from __future__ import annotations
from datetime import datetime, timezone, timedelta
from ontopilot.schema import SchemaRegistry
from ontopilot.store import ObjectStore
from ontopilot.functions import FunctionRegistry


class SingleStepSimulator:
    def __init__(self, schema: SchemaRegistry, store: ObjectStore, functions: FunctionRegistry):
        self._schema = schema
        self._store = store
        self._functions = functions

    def compare(self, shipment_id: str, options: list[dict]) -> list[dict]:
        results = []
        for option in options:
            forked = self._store.fork()
            outcome = self._simulate_option(shipment_id, option, forked)
            results.append({"option_name": option["name"], "simulated_outcome": outcome})
        return results

    def _simulate_option(self, shipment_id: str, option: dict, store: ObjectStore) -> dict:
        action = option.get("action")
        params = option.get("params", {})
        now = datetime.now(timezone.utc)

        shipment = store.get("Shipment", shipment_id)
        if shipment is None:
            return {"error": f"Shipment {shipment_id} not found"}

        old_carrier_id = shipment.get("carrierId", "")
        old_carrier = store.get("Carrier", old_carrier_id) or {}

        if action == "assignCarrier":
            new_carrier_id = params.get("newCarrierId", old_carrier_id)
            store.update("Shipment", shipment_id, {"carrierId": new_carrier_id})
            shipment = store.get("Shipment", shipment_id)

        elif action == "updateETA":
            new_eta = params.get("newETA")
            if new_eta:
                store.update("Shipment", shipment_id, {"ETA": new_eta})
            shipment = store.get("Shipment", shipment_id)

        carrier_id = shipment.get("carrierId", "")
        carrier = store.get("Carrier", carrier_id) or {}
        warehouse = store.get("Warehouse", shipment.get("warehouseId", "")) or {}
        order = store.get("Order", shipment.get("orderId", "")) or {}
        customer_id = order.get("customerId")
        customer = store.get("Customer", customer_id) if customer_id else None

        transit_h = carrier.get("avgTransitHours", 0)
        backlog_h = warehouse.get("backlogDelayHours", 0)
        estimated_delivery = now + timedelta(hours=transit_h + backlog_h)

        req_date_raw = order.get("requiredDeliveryDate")
        if req_date_raw:
            req_date = datetime.fromisoformat(req_date_raw)
            if req_date.tzinfo is None:
                req_date = req_date.replace(tzinfo=timezone.utc)
            sla_met = estimated_delivery <= req_date
            delay_hours = max(0, (estimated_delivery - req_date).total_seconds() / 3600)
        else:
            sla_met = True
            delay_hours = 0.0

        weight = shipment.get("weightKg", 0)
        new_price = carrier.get("pricePerKg", 0)
        old_price = old_carrier.get("pricePerKg", 0)
        cost_delta = round(weight * (new_price - old_price), 2)

        service_level = customer.get("serviceLevel", "standard") if customer else "standard"
        if sla_met:
            customer_risk = "low"
        elif service_level == "VIP":
            customer_risk = "high"
        else:
            customer_risk = "medium"

        return {
            "estimated_delivery": estimated_delivery.isoformat(),
            "delay_hours": round(delay_hours, 1),
            "cost_delta": cost_delta,
            "sla_met": sla_met,
            "customer_risk": customer_risk,
            "assumptions": [
                "使用承运商平均运输时长",
                "使用当前仓库 backlogDelayHours",
                "不考虑天气、交通、其他订单运力竞争",
            ],
        }

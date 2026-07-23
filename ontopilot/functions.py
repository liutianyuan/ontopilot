from __future__ import annotations
from datetime import datetime, timezone
from ontopilot.schema import SchemaRegistry
from ontopilot.store import ObjectStore


FUNCTION_PARAMS = {
    "calculateDelayRisk": {
        "description": "Calculate delay risk scores for one or more shipments",
        "required": {"shipmentIds": "list[str] — IDs of shipments to evaluate"},
    },
    "recommendCarrier": {
        "description": "Recommend an alternative carrier for a shipment",
        "required": {"shipmentId": "str — shipment ID"},
        "optional": {"constraints": "dict — e.g. {'maxCost': number}"},
    },
    "compareDecisions": {
        "description": "Simulate and compare multiple decision options for a shipment",
        "required": {
            "shipmentId": "str — shipment ID to simulate",
            "options": "list[dict] — each option has name and action details, e.g. [{'name': '方案A', 'action': 'assignCarrier', 'params': {'newCarrierId': 'CARRIER-B'}}]",
        },
    },
    "calculateSkillGap": {
        "description": "Calculate skill gap for a project: analyze project requirements vs team skills",
        "required": {"project_id": "str — project ID"},
    },
    "findBestTeam": {
        "description": "Recommend optimal team composition for a project",
        "required": {"project_id": "str — project ID"},
        "optional": {"min_size": "int — minimum team size"},
    },
    "analyzeProjectHealth": {
        "description": "Analyze project health across multiple dimensions (budget, timeline, team)",
        "required": {"project_id": "str — project ID"},
    },
    "getOrgChart": {
        "description": "Get organizational chart for a department",
        "required": {},
        "optional": {"department_id": "str — department ID"},
    },

    # ── Procurement functions ────────────────────────────────────────────
    "recommendAllocation": {
        "description": "Recommend optimal supplier allocation for a material based on supplier capacity, quality, price, and performance data",
        "required": {"materialId": "str — material ID"},
        "optional": {"totalQuantity": "int — total quantity to allocate", "constraints": "dict — e.g. {'maxBudget': number, 'priorityRegion': 'str'}"},
    },
    "analyzeSupplyRisk": {
        "description": "Analyze supply risk for an allocation plan, including single-source dependency and capacity warnings",
        "required": {"planId": "str — allocation plan ID"},
    },
    "compareSupplierProposals": {
        "description": "Compare multiple suppliers for a material across cost, quality, delivery, and overall score",
        "required": {"supplierIds": "list[str] — supplier IDs", "materialId": "str — material ID", "quantity": "int — quantity needed"},
    },
    "calculateCostEfficiency": {
        "description": "Calculate cost efficiency of a supplier considering price, quality loss, delivery delays",
        "required": {"supplierId": "str — supplier ID"},
        "optional": {"materialId": "str — material ID"},
    },

    # ── Lending functions ────────────────────────────────────────────────
    "assessApplicationRisk": {
        "description": "Comprehensive risk assessment for a loan application (credit score + DTI + overdue history + inquiry count)",
        "required": {"applicationId": "str — application ID to assess"},
    },
    "evaluateLoanPortfolio": {
        "description": "Scan all loan contracts and their repayment records, identify high-risk contracts",
        "required": {},
        "optional": {"filters": "dict — e.g. {'status': 'active', 'overdueMinDays': 30}"},
    },
    "compareLoanOptions": {
        "description": "Compare multiple loan options with equal-installment simulation (monthly payment, total interest, DTI, risk)",
        "required": {
            "applicationId": "str — application ID",
            "options": "list[dict] — each option with name, annualRate, termMonths, principal. e.g. [{'name': '方案A', 'annualRate': 0.065, 'termMonths': 36, 'principal': 150000}]",
        },
    },
    "compareCollectionOptions": {
        "description": "Compare collection strategies by estimated recovery rate, amount, and cost",
        "required": {
            "caseId": "str — collection case ID",
            "options": "list[dict] — each option with strategy. e.g. [{'strategy': 'phone_call'}, {'strategy': 'door_visit'}]",
        },
    },
}

class FunctionRegistry:
    def __init__(self, schema: SchemaRegistry, store: ObjectStore):
        self._schema = schema
        self._store = store
        self._fns = {
            "calculateDelayRisk": self._calculate_delay_risk,
            "recommendCarrier": self._recommend_carrier,
            "compareDecisions": self._compare_decisions,
            "calculateSkillGap": self._calculate_skill_gap,
            "findBestTeam": self._find_best_team,
            "analyzeProjectHealth": self._analyze_project_health,
            "getOrgChart": self._get_org_chart,
            # Procurement functions
            "recommendAllocation": self._recommend_allocation,
            "analyzeSupplyRisk": self._analyze_supply_risk,
            "compareSupplierProposals": self._compare_supplier_proposals,
            "calculateCostEfficiency": self._calculate_cost_efficiency,
            # Lending functions
            "assessApplicationRisk": self._assess_application_risk,
            "evaluateLoanPortfolio": self._evaluate_loan_portfolio,
            "compareLoanOptions": self._compare_loan_options,
            "compareCollectionOptions": self._compare_collection_options,
        }

    def call(self, function_name: str, params: dict) -> list | dict:
        if function_name not in self._fns:
            raise KeyError(f"Unknown function: {function_name}")

        info = FUNCTION_PARAMS.get(function_name, {})
        for key in info.get("required", {}):
            if key not in params:
                return {
                    "error": f"参数缺失：'{key}'。调用 {function_name} 需要参数：{info['required']}{info.get('optional', {})}",
                    "required_params": list(info["required"].keys()),
                }
        return self._fns[function_name](params)

    # ── calculateDelayRisk ────────────────────────────────────────────────────

    def _calculate_delay_risk(self, params: dict) -> list[dict]:
        shipment_ids: list[str] = params["shipmentIds"]
        now = datetime.now(timezone.utc)
        results = []
        for sid in shipment_ids:
            shipment = self._store.get("Shipment", sid)
            if shipment is None:
                results.append({
                    "shipmentId": sid,
                    "riskLevel": "unknown",
                    "riskScore": 0,
                    "reasons": ["Shipment not found"],
                })
                continue

            score = 0
            reasons = []

            if shipment.get("status") == "delayed":
                score += 40
                reasons.append("Shipment已延误")

            eta_raw = shipment.get("ETA")
            if eta_raw:
                eta = datetime.fromisoformat(eta_raw)
                if eta.tzinfo is None:
                    eta = eta.replace(tzinfo=timezone.utc)
                if eta < now:
                    score += 25
                    reasons.append("ETA已过期")

            carrier_id = shipment.get("carrierId")
            if carrier_id:
                carrier = self._store.get("Carrier", carrier_id)
                if carrier and carrier.get("delayRate", 0) > 0.15:
                    score += 20
                    reasons.append(f"承运商历史延误率{carrier['delayRate']*100:.0f}%")

            order_id = shipment.get("orderId")
            if order_id:
                order = self._store.get("Order", order_id)
                if order and order.get("priority") in ("high", "urgent"):
                    score += 15
                    reasons.append(f"订单优先级{order['priority']}")

            if score >= 70:
                level = "high"
            elif score >= 40:
                level = "medium"
            else:
                level = "low"

            results.append({
                "shipmentId": sid,
                "riskLevel": level,
                "riskScore": score,
                "reasons": reasons,
            })
        return results

    # ── recommendCarrier ──────────────────────────────────────────────────────

    def _recommend_carrier(self, params: dict) -> dict:
        from datetime import timedelta
        shipment_id: str = params.get("shipmentId", "")
        if not shipment_id:
            return {"error": "Missing shipmentId param"}
        constraints: dict = params.get("constraints") or {}
        shipment = self._store.get("Shipment", shipment_id)
        if shipment is None:
            raise KeyError(f"Shipment {shipment_id} not found")

        max_cost = constraints.get("maxCost")
        now = datetime.now(timezone.utc)
        carriers = self._store.query("Carrier", {}, None)
        warehouse = self._store.get("Warehouse", shipment.get("warehouseId", "")) or {}
        order = self._store.get("Order", shipment.get("orderId", "")) or {}
        weight = shipment.get("weightKg", 0)
        backlog_h = warehouse.get("backlogDelayHours", 0)

        best = None
        best_score = -1

        for carrier in carriers:
            if carrier["carrierId"] == shipment["carrierId"]:
                continue
            if carrier.get("availableCapacity", 0) <= 0:
                continue

            est_cost = weight * carrier["pricePerKg"]
            if max_cost and est_cost > max_cost:
                continue

            est_delivery = now + timedelta(hours=carrier["avgTransitHours"] + backlog_h)
            req_raw = order.get("requiredDeliveryDate")
            sla = True
            if req_raw:
                req = datetime.fromisoformat(req_raw)
                if req.tzinfo is None:
                    req = req.replace(tzinfo=timezone.utc)
                sla = est_delivery <= req

            score = carrier["performanceScore"] - (carrier["delayRate"] * 100) + (50 if sla else 0)
            if score > best_score:
                best_score = score
                best = (carrier, est_delivery, est_cost)

        if best is None:
            return {"error": "No suitable carrier found"}

        carrier, est_delivery, est_cost = best
        return {
            "carrierId": carrier["carrierId"],
            "carrierName": carrier["name"],
            "estimatedETA": est_delivery.isoformat(),
            "estimatedCost": round(est_cost, 2),
            "reason": f"performanceScore={carrier['performanceScore']}, delayRate={carrier['delayRate']*100:.0f}%",
        }

    # ── compareDecisions ──────────────────────────────────────────────────────

    def _compare_decisions(self, params: dict) -> list[dict]:
        from ontopilot.simulation import SingleStepSimulator
        simulator = SingleStepSimulator(self._schema, self._store, self)
        shipment_id: str = params["shipmentId"]
        options: list[dict] = params["options"]
        return simulator.compare(shipment_id, options)

    # ── complex ontology: calculateSkillGap ─────────────────────────────────

    def _calculate_skill_gap(self, params: dict) -> dict:
        project_id: str = params["project_id"]
        project = self._store.get("Project", project_id)
        if not project:
            return {"error": f"Project {project_id} not found"}

        all_people = self._store.query("Person", {}, None)
        all_skills = set()
        for p in all_people:
            try:
                skills = self._store.traverse("Person", p.get("id"), "hasSkill", None)
                for s in skills:
                    all_skills.add(s.get("name", ""))
            except KeyError:
                pass

        return {
            "project_id": project_id,
            "project_name": project.get("name"),
            "skills_available": sorted(all_skills),
            "skills_missing": [],
            "coverage_percentage": round((len(all_skills) / max(len(all_skills), 1)) * 100, 1),
            "team_size": len(all_people),
        }

    def _find_best_team(self, params: dict) -> list[dict]:
        project_id: str = params["project_id"]
        min_size: int = params.get("min_size", 1)
        project = self._store.get("Project", project_id)
        if not project:
            return [{"error": f"Project {project_id} not found"}]

        all_people = self._store.query("Person", {"status": "active"}, None) if "status" in self._schema.get_object_type("Person").properties \
            else self._store.query("Person", {}, None)
        candidates = []
        for person in all_people:
            try:
                skills = self._store.traverse("Person", person.get("id"), "hasSkill", None)
                skill_names = [s.get("name", "") for s in skills]
            except KeyError:
                skill_names = []
            candidates.append({
                "person_id": person.get("id"),
                "name": person.get("name"),
                "skills": skill_names,
                "level": person.get("level"),
                "department": person.get("department"),
            })

        candidates.sort(key=lambda c: len(c["skills"]), reverse=True)
        return candidates[:max(min_size, len(candidates))]

    def _analyze_project_health(self, params: dict) -> dict:
        project_id: str = params["project_id"]
        project = self._store.get("Project", project_id)
        if not project:
            return {"error": f"Project {project_id} not found"}

        all_people = self._store.query("Person", {}, None)
        team_size = len(all_people)
        status = project.get("status", "unknown")
        budget = project.get("budget", 0)

        status_scores = {"active": 80, "planning": 60, "completed": 100, "on_hold": 30, "cancelled": 0}
        timeline_health = status_scores.get(status, 50)
        team_health = min(team_size * 20, 100)
        budget_health = 80 if budget > 0 else 50
        overall = round((timeline_health + team_health + budget_health) / 3, 1)

        return {
            "project_id": project_id,
            "project_name": project.get("name"),
            "status": status,
            "budget_health": budget_health,
            "timeline_health": timeline_health,
            "team_health": team_health,
            "team_size": team_size,
            "overall_score": overall,
        }

    def _get_org_chart(self, params: dict) -> dict:
        department_id: str | None = params.get("department_id")
        if department_id:
            departments = [self._store.get("Department", department_id)] if department_id else []
        else:
            departments = self._store.query("Department", {}, None)
        chart = {}
        all_people = self._store.query("Person", {}, ["id", "name", "department", "level"])
        for dept in departments:
            if not dept:
                continue
            dept_name = dept.get("name")
            dept_id = dept.get("id")
            members = [
                {"id": p.get("id"), "name": p.get("name"), "level": p.get("level")}
                for p in all_people if p.get("department") == dept_name or p.get("department") == dept_id
            ]
            chart[dept_name or dept_id] = {
                "department_id": dept_id,
                "budget": dept.get("budget"),
                "head_count": len(members),
                "members": members,
            }
        return {"departments": chart, "total_departments": len(chart)}

    # ── Procurement: recommendAllocation ────────────────────────────────

    def _recommend_allocation(self, params: dict) -> list[dict]:
        material_id: str = params.get("materialId", "")
        total_qty: int = params.get("totalQuantity", 0)
        constraints: dict = params.get("constraints") or {}

        material = self._store.get("Material", material_id)
        if not material:
            return [{"error": f"Material {material_id} not found"}]

        suppliers = self._store.query("Supplier", {"status": "active"}, None)
        if not suppliers:
            return [{"error": "No active suppliers found"}]

        available = [s for s in suppliers if s.get("capacity", 0) > 0]
        if not available:
            return [{"error": "No suppliers with available capacity"}]

        # Score each supplier
        scored = []
        total_capacity = sum(s.get("capacity", 0) for s in available)
        for s in available:
            cap_weight = s.get("capacity", 0) / max(total_capacity, 1)
            quality = s.get("qualityScore", 50) / 100.0
            delivery = s.get("deliveryTimeliness", 0.5)
            yield_rate = s.get("yieldRate", 0.9)
            price_efficiency = 100.0 / max(s.get("priceIndex", 100), 1)

            # Composite score (higher = better)
            composite = (cap_weight * 0.25 + quality * 0.25 + delivery * 0.20 + yield_rate * 0.15 + price_efficiency * 0.15)
            allocation_pct = round(cap_weight * 100, 1)
            allocation_qty = round(total_qty * cap_weight) if total_qty > 0 else 0

            scored.append({
                "supplierId": s.get("supplierId"),
                "name": s.get("name"),
                "compositeScore": round(composite * 100, 1),
                "capacity": s.get("capacity"),
                "qualityScore": s.get("qualityScore"),
                "deliveryTimeliness": s.get("deliveryTimeliness"),
                "yieldRate": s.get("yieldRate"),
                "priceIndex": s.get("priceIndex"),
                "suggestedAllocationPct": allocation_pct,
                "suggestedQuantity": allocation_qty,
            })

        scored.sort(key=lambda x: x["compositeScore"], reverse=True)
        return scored

    # ── Procurement: analyzeSupplyRisk ──────────────────────────────────

    def _analyze_supply_risk(self, params: dict) -> dict:
        plan_id: str = params.get("planId", "")
        plan = self._store.get("AllocationPlan", plan_id)
        if not plan:
            return {"error": f"Plan {plan_id} not found"}

        batches = self._store.query("AllocationBatch", {"planId": plan_id}, None)
        if not batches:
            return {"error": f"No batches found for plan {plan_id}", "riskLevel": "unknown"}

        supplier_ids = set(b.get("supplierId") for b in batches)
        supplier_count = len(supplier_ids)
        material_id = plan.get("materialId", "")

        # Check single-source dependency
        single_source = supplier_count <= 1

        # Check capacity utilization
        capacity_warnings = []
        for sid in supplier_ids:
            supplier = self._store.get("Supplier", sid)
            if not supplier:
                continue
            batch_qty = sum(b.get("allocatedQty", 0) for b in batches if b.get("supplierId") == sid)
            cap = supplier.get("capacity", 0)
            if cap > 0 and batch_qty / cap > 0.8:
                capacity_warnings.append({
                    "supplierId": sid,
                    "name": supplier.get("name"),
                    "utilization": f"{round(batch_qty / cap * 100, 1)}%",
                    "warning": "High capacity utilization (>80%)",
                })

        # Scores
        risk_score = 0
        risk_factors = []
        if single_source:
            risk_score += 50
            risk_factors.append(f"Single supplier dependency (only {supplier_count} supplier)")
        if capacity_warnings:
            risk_score += 20
            risk_factors.append(f"{len(capacity_warnings)} supplier(s) near capacity limit")
        if not batches:
            risk_score += 30
            risk_factors.append("No allocation batches created")

        # Check delivery performance of assigned suppliers
        low_perf = []
        for sid in supplier_ids:
            s = self._store.get("Supplier", sid)
            if s and s.get("deliveryTimeliness", 1) < 0.9:
                low_perf.append(s.get("name"))
        if low_perf:
            risk_score += 15
            risk_factors.append(f"Low delivery performance: {', '.join(low_perf)}")

        risk_level = "high" if risk_score >= 60 else "medium" if risk_score >= 30 else "low"

        return {
            "planId": plan_id,
            "materialId": material_id,
            "materialName": (self._store.get("Material", material_id) or {}).get("name", ""),
            "supplierCount": supplier_count,
            "singleSourceDependency": single_source,
            "riskLevel": risk_level,
            "riskScore": risk_score,
            "riskFactors": risk_factors,
            "capacityWarnings": capacity_warnings,
        }

    # ── Procurement: compareSupplierProposals ────────────────────────────

    def _compare_supplier_proposals(self, params: dict) -> list[dict]:
        supplier_ids: list[str] = params.get("supplierIds", [])
        material_id: str = params.get("materialId", "")
        quantity: int = params.get("quantity", 0)

        material = self._store.get("Material", material_id)
        results = []
        for sid in supplier_ids:
            s = self._store.get("Supplier", sid)
            if not s:
                results.append({"supplierId": sid, "error": "Supplier not found"})
                continue

            est_cost = quantity * (s.get("priceIndex", 100) / 100.0) * 0.1  # simplified unit cost
            quality_loss_pct = (1 - s.get("yieldRate", 0.95)) * 100
            delivery_risk_pct = (1 - s.get("deliveryTimeliness", 0.9)) * 100

            quality = s.get("qualityScore", 50)
            delivery_score = s.get("deliveryTimeliness", 0.5) * 100
            price_efficiency = (100.0 / max(s.get("priceIndex", 100), 1)) * 100
            overall = round((quality * 0.35 + delivery_score * 0.30 + price_efficiency * 0.35), 1)

            results.append({
                "supplierId": sid,
                "name": s.get("name"),
                "region": s.get("region"),
                "certLevel": s.get("certLevel"),
                "estimatedCost": round(est_cost, 2),
                "priceIndex": s.get("priceIndex"),
                "qualityScore": quality,
                "yieldRate": s.get("yieldRate"),
                "qualityLossPct": round(quality_loss_pct, 2),
                "deliveryTimeliness": s.get("deliveryTimeliness"),
                "deliveryRiskPct": round(delivery_risk_pct, 2),
                "leadTimeDays": s.get("leadTimeDays"),
                "capacity": s.get("capacity"),
                "overallScore": overall,
            })

        results.sort(key=lambda x: x.get("overallScore", 0), reverse=True)
        return results

    # ── Procurement: calculateCostEfficiency ─────────────────────────────

    def _calculate_cost_efficiency(self, params: dict) -> dict:
        supplier_id: str = params.get("supplierId", "")
        material_id: str | None = params.get("materialId")

        supplier = self._store.get("Supplier", supplier_id)
        if not supplier:
            return {"error": f"Supplier {supplier_id} not found"}

        # Base cost from price index
        base_cost_ratio = supplier.get("priceIndex", 100) / 100.0

        # Quality loss cost (rework/scrap due to defects)
        yield_rate = supplier.get("yieldRate", 0.95)
        quality_loss_ratio = (1 - yield_rate) * 0.15  # assume 15% cost of defect

        # Delivery delay cost
        delivery_rate = supplier.get("deliveryTimeliness", 0.9)
        delay_loss_ratio = (1 - delivery_rate) * 0.10  # assume 10% cost of delay

        # Total effective cost ratio
        effective_cost_ratio = base_cost_ratio + quality_loss_ratio + delay_loss_ratio

        # Efficiency score (higher is better, inverse of effective cost)
        efficiency_score = round((1.0 / effective_cost_ratio) * 100, 1)

        return {
            "supplierId": supplier_id,
            "name": supplier.get("name"),
            "baseCostRatio": round(base_cost_ratio, 3),
            "qualityLossRatio": round(quality_loss_ratio, 3),
            "delayLossRatio": round(delay_loss_ratio, 3),
            "effectiveCostRatio": round(effective_cost_ratio, 3),
            "efficiencyScore": efficiency_score,
            "yieldRate": yield_rate,
            "deliveryTimeliness": delivery_rate,
            "qualityScore": supplier.get("qualityScore"),
            "certLevel": supplier.get("certLevel"),
        }

    # ── Lending: assessApplicationRisk ────────────────────────────────────

    def _assess_application_risk(self, params: dict) -> dict:
        application_id: str = params.get("applicationId", "")
        if not application_id:
            return {"error": "Missing applicationId param"}

        application = self._store.get("LoanApplication", application_id)
        if not application:
            return {"error": f"LoanApplication {application_id} not found"}

        borrower = self._store.get("Borrower", application.get("borrowerId", ""))
        if not borrower:
            return {"error": f"Borrower not found for application {application_id}"}

        # Look up credit report by querying directly
        all_reports = self._store.query("CreditReport", {"applicationId": application_id}, None)
        report = all_reports[0] if all_reports else {}

        score = 0
        reasons = []

        # Credit score assessment
        cs = report.get("creditScore", borrower.get("creditScore", 600))
        if cs >= 750:
            score += 0
        elif cs >= 650:
            score += 15
            reasons.append(f"征信分中等 ({cs})")
        elif cs >= 550:
            score += 30
            reasons.append(f"征信分偏低 ({cs})")
        else:
            score += 50
            reasons.append(f"征信分严重偏低 ({cs})")

        # DTI assessment
        dti = borrower.get("dti", 0)
        if dti > 0.50:
            score += 30
            reasons.append(f"债务收入比过高 ({dti*100:.0f}%)")
        elif dti > 0.36:
            score += 15
            reasons.append(f"债务收入比偏高 ({dti*100:.0f}%)")

        # Inquiry count
        inquiry_count = report.get("inquiryCount6m", 0)
        if inquiry_count >= 6:
            score += 20
            reasons.append(f"近6个月查询次数过多 ({inquiry_count})")
        elif inquiry_count >= 3:
            score += 10
            reasons.append(f"近6个月查询次数偏多 ({inquiry_count})")

        # Historical defaults
        defaults = borrower.get("historicalDefaults", 0)
        if defaults >= 3:
            score += 25
            reasons.append(f"历史逾期次数多 ({defaults})")
        elif defaults >= 1:
            score += 10
            reasons.append(f"有历史逾期记录 ({defaults})")

        # Fraud flag
        if report.get("fraudFlag"):
            score += 40
            reasons.append("反欺诈标记命中")

        # Risk level
        if score >= 60:
            risk_level = "reject"
        elif score >= 35:
            risk_level = "high"
        elif score >= 15:
            risk_level = "medium"
        else:
            risk_level = "low"

        # Recommended max amount: monthlyIncome * 36 / (1 + DTI), capped at application amount
        monthly_income = borrower.get("monthlyIncome", 0)
        recommended_max = round(monthly_income * 36 / max(1 + dti, 1.1), -3)
        if risk_level == "reject":
            recommended_max = 0

        return {
            "applicationId": application_id,
            "borrowerName": borrower.get("name"),
            "riskLevel": risk_level,
            "riskScore": score,
            "creditScore": cs,
            "dti": dti,
            "recommendedMaxAmount": recommended_max,
            "reasons": reasons,
        }

    # ── Lending: evaluateLoanPortfolio ────────────────────────────────────

    def _evaluate_loan_portfolio(self, params: dict) -> list[dict]:
        filters = params.get("filters") or {}
        status_filter = filters.get("status")
        overdue_min = filters.get("overdueMinDays", 0)

        if status_filter:
            contracts = self._store.query("LoanContract", {"status": status_filter}, None)
        else:
            # Get all non-paid-off contracts
            contracts = self._store.query("LoanContract", {}, None)

        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        results = []

        for contract in contracts:
            # Skip paid-off contracts unless explicitly requested
            if not status_filter and contract.get("status") == "paid_off":
                continue
            if contract.get("status") not in ("active", "defaulted", "restructured"):
                continue

            cid = contract.get("contractId")
            records = self._store.query("RepaymentRecord", {"contractId": cid}, None)
            if not records:
                continue

            # Analyze repayment patterns
            records.sort(key=lambda r: r.get("dueDate", ""))
            last_3 = [r for r in records if r.get("status") != "upcoming"][-3:]

            statuses = [r.get("status") for r in last_3]
            consecutive_missed = 0
            consecutive_late = 0
            for s in reversed(statuses):
                if s == "missed":
                    consecutive_missed += 1
                elif s == "late":
                    consecutive_late += 1
                else:
                    break

            # Calculate overdue days from earliest missed record
            overdue_days = 0
            for r in records:
                if r.get("status") == "missed":
                    due_raw = r.get("dueDate", "")
                    if due_raw:
                        due = datetime.fromisoformat(due_raw)
                        if due.tzinfo is None:
                            due = due.replace(tzinfo=timezone.utc)
                        days = (now - due).days
                        overdue_days = max(overdue_days, days)

            if overdue_days < overdue_min:
                continue

            risk_flags = []
            if consecutive_missed >= 2:
                risk_flags.append(f"连续{consecutive_missed}期未还")
            if consecutive_late >= 2:
                risk_flags.append(f"连续{consecutive_late}期迟还")
            if any(r.get("status") == "missed" for r in records):
                risk_flags.append("有未还记录")
            if contract.get("status") == "defaulted":
                risk_flags.append("合同已违约")
            if contract.get("status") == "restructured":
                risk_flags.append("合同已重组")

            # Calculate remaining principal using linear amortization
            paid_count = sum(1 for r in records if r.get("status") in ("on_time", "late"))
            monthly_principal = contract.get("principal", 0) / max(contract.get("termMonths", 1), 1)
            remaining_principal = max(0, round(contract.get("principal", 0) - paid_count * monthly_principal, 2))

            # Borrower info
            borrower = self._store.get("Borrower", contract.get("borrowerId", "")) or {}
            monthly_income = borrower.get("monthlyIncome", 0)
            if remaining_principal > monthly_income * 36:
                risk_flags.append("剩余本金过高(>月收入36倍)")

            last_status = last_3[-1].get("status") if last_3 else "unknown"
            results.append({
                "contractId": cid,
                "borrowerName": borrower.get("name", ""),
                "status": contract.get("status"),
                "overdueDays": overdue_days,
                "remainingPrincipal": remaining_principal,
                "monthlyPayment": contract.get("monthlyPayment"),
                "lastPaymentStatus": last_status,
                "riskFlags": risk_flags,
            })

        # Sort by overdueDays descending (worst first)
        results.sort(key=lambda x: x["overdueDays"], reverse=True)
        return results

    # ── Lending: compareLoanOptions ───────────────────────────────────────

    def _compare_loan_options(self, params: dict) -> list[dict]:
        application_id: str = params.get("applicationId", "")
        options: list[dict] = params.get("options", [])

        application = self._store.get("LoanApplication", application_id)
        if not application:
            return [{"error": f"LoanApplication {application_id} not found"}]

        borrower = self._store.get("Borrower", application.get("borrowerId", ""))
        if not borrower:
            return [{"error": f"Borrower not found for application {application_id}"}]

        monthly_income = borrower.get("monthlyIncome", 0)
        existing_dti = borrower.get("dti", 0)
        # Estimate existing monthly debt payments from DTI
        existing_monthly_debt = monthly_income * existing_dti

        results = []
        for option in options:
            name = option.get("name", option.get("strategy", "unknown"))
            annual_rate = option.get("annualRate", 0.072)
            term_months = option.get("termMonths", 36)
            principal = option.get("principal", application.get("amount", 100000))

            # Equal installment formula: M = P * r * (1+r)^n / ((1+r)^n - 1)
            monthly_rate = annual_rate / 12.0
            if monthly_rate == 0:
                monthly_payment = principal / term_months
            else:
                factor = (1 + monthly_rate) ** term_months
                monthly_payment = principal * monthly_rate * factor / (factor - 1)

            total_interest = monthly_payment * term_months - principal

            # New DTI
            new_monthly_debt = existing_monthly_debt + monthly_payment
            new_dti = round(new_monthly_debt / monthly_income, 3) if monthly_income > 0 else 1.0

            # Affordability assessment
            if new_dti <= 0.36:
                affordability = "good"
                risk_level = "low"
            elif new_dti <= 0.50:
                affordability = "caution"
                risk_level = "medium"
            else:
                affordability = "high_risk"
                risk_level = "high"

            results.append({
                "optionName": name,
                "monthlyPayment": round(monthly_payment, 2),
                "totalInterest": round(total_interest, 2),
                "totalRepayment": round(principal + total_interest, 2),
                "newDti": new_dti,
                "affordabilityScore": affordability,
                "riskLevel": risk_level,
                "annualRate": annual_rate,
                "termMonths": term_months,
                "principal": principal,
            })

        return results

    # ── Lending: compareCollectionOptions ─────────────────────────────────

    def _compare_collection_options(self, params: dict) -> list[dict]:
        case_id: str = params.get("caseId", "")
        options: list[dict] = params.get("options", [])

        case = self._store.get("CollectionCase", case_id)
        if not case:
            return [{"error": f"CollectionCase {case_id} not found"}]

        overdue_days = case.get("overdueDays", 0)
        outstanding = case.get("outstandingAmount", 0)

        # Recovery rate model by overdue range and strategy
        BASE_RATES = {
            "sms":       {(0, 30): 0.70, (31, 90): 0.40, (91, 9999): 0.15},
            "phone_call":{(0, 30): 0.85, (31, 90): 0.55, (91, 9999): 0.30},
            "door_visit":{(0, 30): 0.90, (31, 90): 0.65, (91, 9999): 0.30},
            "legal_notice": {(0, 30): 0.80, (31, 90): 0.50, (91, 9999): 0.35},
            "external_agency": {(0, 30): 0.60, (31, 90): 0.45, (91, 9999): 0.35},
        }
        COST_PER_ACTION = {
            "sms": 5, "phone_call": 30, "door_visit": 150,
            "legal_notice": 300, "external_agency": 0,  # external is % based
        }

        def get_recovery_rate(strategy: str, days: int) -> float:
            rates = BASE_RATES.get(strategy, {})
            for (lo, hi), rate in rates.items():
                if lo <= days <= hi:
                    return rate
            return 0.3

        results = []
        for option in options:
            strategy = option.get("strategy", "phone_call")
            recovery_rate = get_recovery_rate(strategy, overdue_days)
            recovery_amount = round(outstanding * recovery_rate, 2)

            if strategy == "external_agency":
                cost = round(recovery_amount * 0.20, 2)
            else:
                cost = COST_PER_ACTION.get(strategy, 30)

            net_recovery = round(recovery_amount - cost, 2)

            if recovery_rate >= 0.60:
                recommendation = "推荐"
            elif recovery_rate >= 0.40:
                recommendation = "可考虑"
            else:
                recommendation = "效果有限"

            results.append({
                "strategy": strategy,
                "overdueDays": overdue_days,
                "outstandingAmount": outstanding,
                "estimatedRecoveryRate": round(recovery_rate, 2),
                "estimatedRecoveryAmount": recovery_amount,
                "estimatedCost": cost,
                "netRecovery": net_recovery,
                "recommendation": recommendation,
            })

        results.sort(key=lambda x: x["netRecovery"], reverse=True)
        return results

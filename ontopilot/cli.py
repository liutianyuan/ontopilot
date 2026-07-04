from __future__ import annotations
import argparse
import json
import sys

from ontopilot.runtime import OntologyRuntime

_CASES = {
    "case_01": {
        "user_id": "dispatcher_001",
        "role": "dispatcher",
        "warehouse_id": "WH-SC-001",
        "action": "query_delayed",
    },
    "case_03": {
        "user_id": "dispatcher_001",
        "role": "dispatcher",
        "warehouse_id": "WH-SC-001",
        "action": "assign_carrier_preview",
    },
}


def run_case(case_id: str, runtime: OntologyRuntime) -> None:
    import uuid
    case = _CASES.get(case_id)
    if case is None:
        print(f"Unknown case: {case_id}. Available: {list(_CASES.keys())}")
        sys.exit(1)

    turn_id = str(uuid.uuid4())
    user_id = case["user_id"]
    role = case["role"]
    wh_id = case["warehouse_id"]

    print(f"\n=== {case_id} ===")
    print(f"User: {user_id} | Role: {role}\n")

    ctx = runtime.build_context(user_id, role, wh_id, turn_id)
    print(ctx)
    print()

    if case["action"] == "query_delayed":
        shipments = runtime.query(
            user_id, role, "Shipment",
            filters={"status": "delayed", "warehouseId": wh_id},
            properties=["shipmentId", "ETA", "delayReason", "carrierId", "orderId"],
            turn_id=turn_id,
        )
        print(f"Delayed shipments ({len(shipments)}):")
        for s in shipments:
            print(f"  {json.dumps(s, ensure_ascii=False)}")

        ship_ids = [s["shipmentId"] for s in shipments]
        risks = runtime.call_function(user_id, role, "calculateDelayRisk",
                                      {"shipmentIds": ship_ids}, turn_id=turn_id)
        print(f"\nRisk assessment:")
        for r in sorted(risks, key=lambda x: -x["riskScore"]):
            print(f"  {r['shipmentId']}: {r['riskLevel']} (score={r['riskScore']}) — {', '.join(r['reasons'])}")

    elif case["action"] == "assign_carrier_preview":
        preview = runtime.preview_action(
            user_id, role, "assignCarrier",
            {"shipmentId": "SH-0042", "newCarrierId": "CARRIER-B", "reason": "降低延误风险"},
            turn_id=turn_id,
        )
        print("Action Preview:")
        print(json.dumps(preview, ensure_ascii=False, indent=2))
        print("\nTo execute, run with --confirm flag")

    events = runtime.get_trace_events(turn_id)
    print(f"\nTrace ({len(events)} events):")
    for e in events:
        icon = "✅" if e.status in ("success", "pass") else "⏳" if "pending" in e.status else "❌"
        print(f"  {icon} [{e.layer}] {e.name} — {e.status} ({e.duration_ms}ms)")


def chat(runtime: OntologyRuntime, user_id: str, role: str, warehouse_id: str) -> None:
    from ontopilot.llm import create_llm
    from ontopilot.schema import SchemaRegistry
    from ontopilot.governance import PermissionEvaluator
    from ontopilot.agent import run_turn

    llm = create_llm()
    schema = SchemaRegistry("config/ontology_schema.yaml")
    governance = PermissionEvaluator("config/permissions.yaml")
    history = []
    pending_action = None

    print(f"\nOntoPilot Chat | User: {user_id} | Role: {role} | Warehouse: {warehouse_id}")
    print("Type 'quit' to exit, 'yes' to confirm a pending action.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not user_input:
            continue
        if user_input.lower() == "quit":
            break

        confirmed = user_input.lower() in ("yes", "确认", "confirm")
        result = run_turn(
            runtime=runtime, llm=llm, schema=schema, governance=governance,
            user_id=user_id, role=role, warehouse_id=warehouse_id,
            user_message=user_input, history=history,
            confirmed=confirmed, pending_action=pending_action,
        )
        print(f"\nAgent: {result['response']}\n")

        if result["awaiting_confirmation"]:
            print("[系统] 上述操作需要确认。输入 'yes' 执行，或继续对话。\n")
            pending_action = result.get("pending_action")
        else:
            pending_action = None

        from langchain_core.messages import HumanMessage, AIMessage as AIMsg
        history.append(HumanMessage(content=user_input))
        history.append(AIMsg(content=result["response"]))
        history = history[-20:]

        events = result.get("trace_events", [])
        if events:
            print(f"  [Trace: {len(events)} events | " +
                  " → ".join(e["layer"] for e in events) + "]\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="OntoPilot CLI")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run_case")
    run_parser.add_argument("case_id")

    chat_parser = subparsers.add_parser("chat")
    chat_parser.add_argument("--user", default="dispatcher_001")
    chat_parser.add_argument("--role", default="dispatcher")
    chat_parser.add_argument("--warehouse", default="WH-SC-001")

    args = parser.parse_args()
    runtime = OntologyRuntime.from_config()

    if args.command == "run_case":
        run_case(args.case_id, runtime)
    elif args.command == "chat":
        chat(runtime, args.user, args.role, args.warehouse)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

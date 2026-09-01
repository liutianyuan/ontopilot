from __future__ import annotations

import argparse
import json
import os

from ontopilot.nano_provider import NanoOntologyProvider


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=os.getenv("NANO_API_BASE", "http://127.0.0.1:10081/api/v1"))
    parser.add_argument("--ontology-id", default=os.getenv("NANO_ONTOLOGY_ID"), required=not os.getenv("NANO_ONTOLOGY_ID"))
    parser.add_argument("--username", default=os.getenv("NANO_USERNAME"))
    parser.add_argument("--password", default=os.getenv("NANO_PASSWORD"))
    parser.add_argument("--token", default=os.getenv("NANO_API_TOKEN"))
    parser.add_argument("--patient-id", default="P-CKD-042")
    args = parser.parse_args()
    provider = NanoOntologyProvider(args.base_url, args.ontology_id, token=args.token,
                                    username=args.username, password=args.password)
    schema = provider.schema("v1.1")
    summary = provider.patient_summary(args.patient_id)
    evaluations = {item["rule_code"]: item for item in summary["rule_evaluations"]}
    assert evaluations["CkdStagingRule"]["conclusion"] == "CKD G4"
    assert evaluations["HyperkalemiaCriticalRule"]["status"] == "triggered"
    assert evaluations["MetforminRenalSafetyRule"]["status"] == "blocked"
    alerts = provider.alerts(args.patient_id)
    high_k = next(item for item in alerts if item["alert_type"] == "hyperkalemia")
    preview = provider.preview_alert_action(high_k["id"])
    decision = provider.decide(preview["confirmation_id"], True)
    run = provider.action_run(decision["action_run"]["id"])
    assert run["status"] == "succeeded"
    assert run["writeback_result"]["status"] == "accepted"
    refreshed = provider.patient_summary(args.patient_id)
    assert any(item["type"] == "TestOrder" and item["properties"].get("status") == "ordered"
               for item in refreshed["facts"])
    print(json.dumps({
        "status": "passed", "schema_version": schema.version, "schema_type_count": len(schema.type_names),
        "patient_id": args.patient_id, "fact_count": len(refreshed["facts"]),
        "rule_codes": sorted(evaluations), "alert_count": len(alerts),
        "confirmation_id": preview["confirmation_id"], "action_run_id": run["id"],
        "writeback": run["writeback_result"], "trace_id": run["trace_id"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

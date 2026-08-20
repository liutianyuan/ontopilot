from ontopilot.runtime import OntologyRuntime


def make_xiehe_runtime(tmp_path):
    return OntologyRuntime.from_config(
        "config",
        str(tmp_path / "xiehe.db"),
        schema_path="config/xiehe_nephrology_ontology.yaml",
        seed_path="config/xiehe_nephrology_seed.yaml",
        permissions_path="config/xiehe_nephrology_permissions.yaml",
        context_path="config/xiehe_nephrology_context.yaml",
    )


def test_xiehe_nephrology_seed_queries_patient_facts(tmp_path):
    runtime = make_xiehe_runtime(tmp_path)

    indicators = runtime.query(
        "u",
        "nephrology_doctor",
        "Indicator",
        {"patientId": "P-CKD-042"},
        ["nameCn", "value", "unit"],
    )

    assert len(indicators) == 8
    assert {"nameCn": "血钾", "value": 5.9, "unit": "mmol/L"} in indicators


def test_xiehe_nephrology_rules_cover_qa_examples(tmp_path):
    runtime = make_xiehe_runtime(tmp_path)

    examples = [
        ("cKDStagingRule", "P-CKD-042", "evaluated", "CKD G4"),
        ("metforminSafetyRule", "P-CKD-042", "blocked", "二甲双胍禁用"),
        ("hyperkalemiaCriticalValueRule", "P-CKD-042", "triggered", "高钾危急值"),
        ("aRBACEISafetyRule", "P-CKD-042", "blocked", "ACEI/ARB"),
        ("proteinuriaStratificationRule", "P-CKD-042", "heavy", "大量蛋白尿"),
        ("cKDMBDWarningRule", "P-CKD-042", "triggered", "CKD-MBD"),
        ("cKD4AdmissionMandatoryAssessmentRule", "P-CKD-042", "overdue", "24h"),
        ("dialysisAdequacyQCRule", "P-DIAL-009", "qc_defect", "Kt/V"),
        ("dialysisMonthlyReviewQCRule", "P-DIAL-009", "qc_defect", "30 天"),
        ("aKIStage1DiagnosisRule", "P-AKI-017", "triggered", "AKI 1期"),
    ]

    for function_name, patient_id, status, expected_text in examples:
        result = runtime.call_function("u", "admin", function_name, {"patientId": patient_id})
        assert result["status"] == status
        assert expected_text in result["conclusion"]


def test_xiehe_nephrology_rules_include_positive_and_negative_medication_paths(tmp_path):
    runtime = make_xiehe_runtime(tmp_path)

    sglt2i = runtime.call_function("u", "admin", "sGLT2iUsageRule", {"patientId": "P-CKD-042"})
    finerenone = runtime.call_function("u", "admin", "finerenoneUsageRule", {"patientId": "P-CKD-042"})

    assert sglt2i["status"] == "not_recommended"
    assert finerenone["status"] == "warning"


def test_xiehe_nephrology_actions_preview_meaningful_changes(tmp_path):
    runtime = make_xiehe_runtime(tmp_path)

    preview = runtime.preview_action(
        "u",
        "nephrology_doctor",
        "hyperkalemiaCriticalAlert",
        {"id": "obs_p_ckd_042_k", "note": "血钾 5.9 mmol/L，触发危急值提醒"},
    )

    assert preview["status"] == "pending_confirmation"
    assert preview["target"] == "Indicator:obs_p_ckd_042_k"
    assert {
        "field": "actionStatus",
        "from": "not_alerted",
        "to": "alert_pending_ack",
    } in preview["changes"]
    assert {
        "field": "notificationStatus",
        "from": "not_sent",
        "to": "pending_physician_and_nurse_ack",
    } in preview["changes"]


def test_xiehe_nephrology_admin_action_preview_remains_confirmation_free(tmp_path):
    runtime = make_xiehe_runtime(tmp_path)

    preview = runtime.preview_action(
        "u",
        "admin",
        "metforminPrescriptionBlock",
        {"id": "order_p_ckd_042_metformin", "note": "eGFR 15，二甲双胍禁用"},
    )

    assert preview["status"] == "previewed"
    assert preview["target"] == "Drug:order_p_ckd_042_metformin"
    assert {
        "field": "orderStatus",
        "from": "active",
        "to": "blocked",
    } in preview["changes"]

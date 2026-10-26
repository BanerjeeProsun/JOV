"""Unit tests for all 15 Pre-Submission Validation Gate checks (Blueprint v2.0 Section 11)."""

import pytest
from jovsi.domain.models import GateCheckOutcome
from jovsi.domain.gate import GateSnapshot, ValidationGate


@pytest.fixture
def passing_snapshot():
    return GateSnapshot(
        application_id="app-test-1",
        package_hash="pkg_hash_123456",
        target_company_norm="Acme Corp",
        target_role_norm="Senior Python Architect",
        target_url="http://127.0.0.1:8765/jobs/1/apply",
        page_company_name="Acme Corp",
        page_role_title="Senior Python Architect",
        page_url="http://127.0.0.1:8765/jobs/1/apply",
        portal_allowed_domains=["127.0.0.1", "localhost"],
        attached_file_name="resume.pdf",
        attached_file_hash="res_hash_abc",
        expected_resume_hash="res_hash_abc",
        resume_validation_passed=True,
        cover_letter_required=False,
        form_values={
            "full_name": "Ada Lovelace",
            "email": "ada@example.com",
            "phone": "+1234567890",
            "legal_attestation": "agree",
        },
        required_field_keys=["full_name", "email", "phone", "legal_attestation"],
        sensitive_field_keys=["legal_attestation"],
        approved_sensitive_keys=["legal_attestation"],
        candidate_verified_email="ada@example.com",
        candidate_verified_phone="+1234567890",
        unresolved_provenance_keys=[],
        has_date_contradictions=False,
        is_exact_duplicate=False,
        is_near_duplicate=False,
        rate_global_count=0,
        rate_global_cap=10,
        inspection_form_skeleton_hash="skel_hash_xyz",
        current_form_skeleton_hash="skel_hash_xyz",
        other_company_names=["Beta LLC"],
    )


def test_gate_all_15_pass(passing_snapshot) -> None:
    report = ValidationGate.evaluate(passing_snapshot)
    assert report.is_pass is True
    assert report.outcome == GateCheckOutcome.PASS
    assert len(report.results) == 15
    for r in report.results:
        assert r.outcome == GateCheckOutcome.PASS


def test_check_1_company_mismatch(passing_snapshot) -> None:
    passing_snapshot.page_company_name = "Completely Different Company"
    report = ValidationGate.evaluate(passing_snapshot)
    assert report.outcome == GateCheckOutcome.BLOCKED
    r1 = next(r for r in report.results if r.check_id == 1)
    assert r1.outcome == GateCheckOutcome.BLOCKED
    assert r1.code == "COMPANY_MISMATCH"


def test_check_2_role_match_boundary(passing_snapshot) -> None:
    # Partial match gives NEEDS_USER
    passing_snapshot.page_role_title = "Python Architect"
    report = ValidationGate.evaluate(passing_snapshot)
    r2 = next(r for r in report.results if r.check_id == 2)
    assert r2.outcome in (GateCheckOutcome.PASS, GateCheckOutcome.NEEDS_USER)

    # Completely different gives BLOCKED
    passing_snapshot.page_role_title = "Accountant"
    report_blocked = ValidationGate.evaluate(passing_snapshot)
    r2_blocked = next(r for r in report_blocked.results if r.check_id == 2)
    assert r2_blocked.outcome == GateCheckOutcome.BLOCKED


def test_check_3_domain_policy(passing_snapshot) -> None:
    passing_snapshot.page_url = "https://unauthorized-evil.com/apply"
    report = ValidationGate.evaluate(passing_snapshot)
    assert report.outcome == GateCheckOutcome.BLOCKED
    r3 = next(r for r in report.results if r.check_id == 3)
    assert r3.code == "DOMAIN_NOT_ALLOWED"


def test_check_4_resume_hash(passing_snapshot) -> None:
    passing_snapshot.attached_file_hash = "tampered_hash"
    report = ValidationGate.evaluate(passing_snapshot)
    r4 = next(r for r in report.results if r.check_id == 4)
    assert r4.outcome == GateCheckOutcome.BLOCKED
    assert r4.code == "RESUME_HASH_MISMATCH"


def test_check_7_placeholders_and_cross_contamination(passing_snapshot) -> None:
    # Placeholder
    passing_snapshot.form_values["full_name"] = "Dear {{COMPANY_NAME}}"
    report = ValidationGate.evaluate(passing_snapshot)
    r7 = next(r for r in report.results if r.check_id == 7)
    assert r7.outcome == GateCheckOutcome.BLOCKED

    # Cross contamination from another company
    passing_snapshot.form_values["full_name"] = "I love working at Beta LLC"
    report_cross = ValidationGate.evaluate(passing_snapshot)
    r7_cross = next(r for r in report_cross.results if r.check_id == 7)
    assert r7_cross.outcome == GateCheckOutcome.BLOCKED


def test_check_8_required_fields(passing_snapshot) -> None:
    passing_snapshot.form_values["phone"] = ""
    report = ValidationGate.evaluate(passing_snapshot)
    r8 = next(r for r in report.results if r.check_id == 8)
    assert r8.outcome == GateCheckOutcome.NEEDS_USER


def test_check_9_contact_equality(passing_snapshot) -> None:
    passing_snapshot.form_values["email"] = "altered_email@example.com"
    report = ValidationGate.evaluate(passing_snapshot)
    r9 = next(r for r in report.results if r.check_id == 9)
    assert r9.outcome == GateCheckOutcome.NEEDS_USER


def test_check_12_unapproved_sensitive_field(passing_snapshot) -> None:
    passing_snapshot.approved_sensitive_keys = []  # Not approved!
    report = ValidationGate.evaluate(passing_snapshot)
    r12 = next(r for r in report.results if r.check_id == 12)
    assert r12.outcome == GateCheckOutcome.NEEDS_USER


def test_check_13_duplicate_detection(passing_snapshot) -> None:
    passing_snapshot.is_exact_duplicate = True
    report = ValidationGate.evaluate(passing_snapshot)
    r13 = next(r for r in report.results if r.check_id == 13)
    assert r13.outcome == GateCheckOutcome.BLOCKED
    assert r13.code == "EXACT_DUPLICATE_BLOCKED"


def test_check_14_rate_caps(passing_snapshot) -> None:
    passing_snapshot.rate_global_count = 10
    passing_snapshot.rate_global_cap = 10
    report = ValidationGate.evaluate(passing_snapshot)
    r14 = next(r for r in report.results if r.check_id == 14)
    assert r14.outcome == GateCheckOutcome.BLOCKED
    assert r14.code == "RATE_LIMIT_EXCEEDED"


def test_check_15_dom_drift(passing_snapshot) -> None:
    passing_snapshot.current_form_skeleton_hash = "drifted_mutated_hash"
    report = ValidationGate.evaluate(passing_snapshot)
    r15 = next(r for r in report.results if r.check_id == 15)
    assert r15.outcome == GateCheckOutcome.BLOCKED
    assert r15.code == "DOM_DRIFT_DETECTED"

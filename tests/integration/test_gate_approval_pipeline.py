"""Integration test for Milestone 14: Validation Gate, Supervised Approval, and State Transitions."""

import time
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from jovsi.api.main import app
from jovsi.adapters.db.session import SessionLocal
from jovsi.adapters.db.models import (
    ApplicationDB,
    ApprovalDB,
    CandidateDB,
    FactDB,
    GateReportDB,
    JobDB,
    UserDB,
)
from jovsi.domain.models import FactKind, FactProvenance, FactStatus
from jovsi.services.auth import AuthService


def test_gate_approval_pipeline_lifecycle():
    client = TestClient(app)
    db = SessionLocal()

    ts = int(time.time() * 1000)
    user_email = f"gate_cand_{ts}@example.com"
    user, _ = AuthService.register_user(db, email=user_email, password="Password123!", display_name="Gate Tester")

    candidate = CandidateDB(
        id=f"c_gate_{ts}",
        user_id=user.id,
        display_name="Gate Tester",
    )
    db.add(candidate)

    contact_fact = FactDB(
        id=f"f_c_{ts}",
        candidate_id=candidate.id,
        kind="CONTACT",
        key="contact",
        value={"email": user_email, "phone": "+1-555-0199"},
        provenance="USER_VERIFIED",
        status="ACTIVE",
    )
    db.add(contact_fact)

    skill_fact = FactDB(
        id=f"f_s_{ts}",
        candidate_id=candidate.id,
        kind="SKILL",
        key="python",
        value={"name": "Python"},
        provenance="USER_VERIFIED",
        status="ACTIVE",
    )
    db.add(skill_fact)

    job = JobDB(
        id=f"job_gate_{ts}",
        source="ashby",
        source_url=f"https://jobs.example.com/gate/{ts}",
        canonical_url=f"http://127.0.0.1:8765/jobs/job-{ts}/apply",
        canonical_job_key=f"gate-key-{ts}",
        company_norm="Acme Corp",
        title_norm="Software Engineer",
        description_clean="We are looking for a Software Engineer proficient in Python.",
        requirements={
            "role_title": "Software Engineer",
            "required_skills": ["Python"],
            "min_years_experience": 3,
            "required_degree": None,
            "security_clearance_required": False,
            "sponsorship_available": True,
            "remote_allowed": True,
            "work_mode": "REMOTE",
            "locations": ["San Francisco, CA"],
        },
        raw_sha256=f"hash_job_{ts}",
    )
    db.add(job)
    db.commit()

    # Authenticate via login
    login_resp = client.post("/api/v1/auth/login", json={"email": user_email, "password": "Password123!"})
    assert login_resp.status_code == 200

    # 1. Create application
    create_resp = client.post("/api/v1/applications", json={"candidate_id": candidate.id, "job_id": job.id})
    assert create_resp.status_code == 201
    app_id = create_resp.json()["id"]

    # Evaluate eligibility
    eval_resp = client.post(f"/api/v1/applications/{app_id}/evaluate")
    assert eval_resp.status_code == 200

    # 2. Cannot approve or run gate without resume
    gate_no_resume = client.post(f"/api/v1/applications/{app_id}/gate")
    assert gate_no_resume.status_code == 400
    assert "Must generate resume before running gate" in gate_no_resume.json()["detail"]

    # 3. Generate resume
    gen_res = client.post(f"/api/v1/applications/{app_id}/generate-resume")
    assert gen_res.status_code == 200

    # 4. Plan application fields
    plan_res = client.post(f"/api/v1/applications/{app_id}/plan")
    assert plan_res.status_code == 200

    # 5. Run gate
    gate_resp = client.post(f"/api/v1/applications/{app_id}/gate")
    assert gate_resp.status_code == 200
    gate_data = gate_resp.json()
    assert "package_hash" in gate_data
    assert gate_data["outcome"] == "PASS"
    assert len(gate_data["results"]) == 15

    package_hash = gate_data["package_hash"]

    # 6. Cannot submit before approving
    sub_premature = client.post(f"/api/v1/applications/{app_id}/submit")
    assert sub_premature.status_code == 400
    assert "Must be APPROVED" in sub_premature.json()["detail"]

    # 7. Approve package with wrong hash fails
    bad_approve = client.post(
        f"/api/v1/applications/{app_id}/approve",
        json={"package_hash": "tampered_fake_package_hash", "approved_by": "user"},
    )
    assert bad_approve.status_code == 400

    # 8. Approve package with valid hash succeeds
    approve_resp = client.post(
        f"/api/v1/applications/{app_id}/approve",
        json={"package_hash": package_hash, "approved_by": "user"},
    )
    assert approve_resp.status_code == 200
    approve_data = approve_resp.json()
    assert approve_data["status"] == "approved"
    assert "approval_id" in approve_data
    assert "expires_at" in approve_data

    # Verify DB state
    db.expire_all()
    app_db = db.scalar(select(ApplicationDB).where(ApplicationDB.id == app_id))
    assert app_db.state == "APPROVED"

    approval_db = db.scalar(select(ApprovalDB).where(ApprovalDB.id == approve_data["approval_id"]))
    assert approval_db is not None
    assert approval_db.content_hash == package_hash
    assert approval_db.is_consumed is False

    db.close()

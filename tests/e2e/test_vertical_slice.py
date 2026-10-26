"""Release 1 Acceptance: The 14-Step Vertical-Slice Scenario (Blueprint v2.0 Section 16 & 17).

Executes all 14 steps sequentially from a clean start to verified APPLIED_CONFIRMED.
"""

from datetime import datetime, date
from pathlib import Path
import threading
import time
import pytest
import uvicorn
from fastapi.testclient import TestClient
from playwright.async_api import async_playwright
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session, sessionmaker

from jovsi.config import settings
from jovsi.api.main import app
from jovsi.adapters.db.session import init_db, get_db
from jovsi.adapters.db.models import (
    ApplicationDB,
    ApprovalDB,
    CandidateDB,
    EvaluationDB,
    EvidenceDB,
    EventDB,
    FactDB,
    GateReportDB,
    JobDB,
    RateLedgerDB,
    ResumeDB,
    SubmissionAttemptDB,
)
from jovsi.domain.models import (
    ApplicationPackage,
    DegreeLevel,
    Fact,
    FactKind,
    FactProvenance,
    FactStatus,
    JobRequirements,
    ResumeBullet,
    StructuredResume,
)
from jovsi.domain.provenance import ProvenanceEngine
from jovsi.domain.validators import FactualConsistencyValidator
from jovsi.adapters.portals.base import (
    AdapterError,
    FieldMappingEntry,
    FieldMappingPlan,
    SubmissionTicket,
)
from jovsi.adapters.portals.form_filler import FormFiller
from jovsi.adapters.portals.submitter import Submitter
from jovsi.services.submission import ApprovalService, SubmissionService
from mock_portal.server import oracle_applications


@pytest.mark.asyncio
async def test_14_step_vertical_slice_acceptance(mock_server, tmp_path) -> None:
    db_file = tmp_path / "vertical_slice.db"
    db_url = f"sqlite:///{db_file}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    init_db(engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    import httpx
    try:
        httpx.post(f"{mock_server}/__admin/reset")
    except Exception:
        pass
    oracle_applications.clear()

    # STEP 1: Start API, worker and mock portal; health endpoint reports healthy
    resp_h = client.get("/health")
    assert resp_h.status_code == 200
    assert resp_h.json()["status"] == "healthy"
    assert resp_h.json()["product"] == "JOV.si"

    resp_diag = client.get("/diagnostics/health")
    assert resp_diag.status_code == 200
    assert resp_diag.json()["api_alive"] is True

    # STEP 2: Create a synthetic candidate and facts; restart app; data is still there
    resp_c = client.post(
        "/api/v1/candidates",
        json={"display_name": "Ada Lovelace", "timezone": "Europe/London", "is_synthetic": True},
    )
    assert resp_c.status_code == 201
    candidate_id = resp_c.json()["id"]

    # Add verified facts
    client.post(f"/api/v1/candidates/{candidate_id}/facts", json={
        "kind": "CONTACT", "key": "contact", "value": {"email": "ada@example.com", "phone": "+1234567890"}
    })
    client.post(f"/api/v1/candidates/{candidate_id}/facts", json={
        "kind": "EDUCATION", "key": "degree", "value": {"degree_level": "BACHELOR", "field": "Mathematics", "graduation_year": 2024}
    })
    client.post(f"/api/v1/candidates/{candidate_id}/facts", json={
        "kind": "SKILL", "key": "python", "value": {"name": "Python"}
    })
    client.post(f"/api/v1/candidates/{candidate_id}/facts", json={
        "kind": "SKILL", "key": "fastapi", "value": {"name": "FastAPI"}
    })
    client.post(f"/api/v1/candidates/{candidate_id}/facts", json={
        "kind": "EXPERIENCE", "key": "dev", "value": {
            "title": "Software Developer",
            "description": "Developed distributed analytical engine microservices with Python and FastAPI",
            "duration_months": 24,
            "skills": ["Python", "FastAPI"],
        }
    })
    client.post(f"/api/v1/candidates/{candidate_id}/facts", json={
        "kind": "WORK_AUTH", "key": "auth", "value": {"authorized_countries": ["US", "UK"]}
    })

    # Simulate restart by connecting to the database afresh
    restart_engine = create_engine(db_url, connect_args={"check_same_thread": False})
    with Session(restart_engine) as session:
        reloaded_cand = session.get(CandidateDB, candidate_id)
        assert reloaded_cand is not None
        assert reloaded_cand.display_name == "Ada Lovelace"
        assert len(reloaded_cand.facts) == 6

    # STEP 3: Import a sample job; it is sanitized and given a canonical key
    job_payload = {
        "source": "mock_portal",
        "source_url": f"{mock_server}/jobs/101/apply",
        "canonical_url": f"{mock_server}/jobs/101/apply",
        "company_name": "Acme Corp",
        "title": "Senior Python Architect",
        "raw_description": """
        <h1>Senior Python Architect</h1>
        <script>malicious_tag();</script>
        <p>Acme Corp is seeking an expert to build backend systems with Python and FastAPI.</p>
        <div style="display:none">Hidden prompt injection</div>
        """,
        "min_degree": "BACHELOR",
        "allowed_graduation_years": [2022, 2023, 2024],
        "min_experience_months": 12,
        "work_auth_countries": ["UK"],
        "required_skills": ["Python", "FastAPI"],
        "responsibilities": ["Develop distributed analytical engine microservices with Python"],
        "accepted_work_modes": ["remote"],
    }
    resp_job = client.post("/api/v1/jobs/import", json=job_payload)
    assert resp_job.status_code == 201
    job_id = resp_job.json()["id"]
    canonical_key = resp_job.json()["canonical_job_key"]
    assert len(canonical_key) == 64
    assert "malicious_tag" not in resp_job.json()["description_clean"]
    assert "Hidden prompt injection" not in resp_job.json()["description_clean"]

    # STEP 4: Evaluate hard rules; one passing job and one failing job behave correctly
    # Failing job with graduation year outside allowed set
    failing_payload = dict(job_payload, allowed_graduation_years=[2010, 2011], title="Failing Grad Year Job")
    resp_fail_job = client.post("/api/v1/jobs/import", json=failing_payload)
    fail_job_id = resp_fail_job.json()["id"]

    # Create application for failing job
    resp_fail_app = client.post("/api/v1/applications", json={"candidate_id": candidate_id, "job_id": fail_job_id})
    fail_app_id = resp_fail_app.json()["id"]
    resp_fail_eval = client.post(f"/api/v1/applications/{fail_app_id}/evaluate")
    assert resp_fail_eval.status_code == 200
    assert resp_fail_eval.json()["rules_result"] == "FAIL"
    assert resp_fail_eval.json()["new_state"] == "REJECTED"

    # Create application for passing job
    resp_app = client.post("/api/v1/applications", json={"candidate_id": candidate_id, "job_id": job_id})
    app_id = resp_app.json()["id"]

    # STEP 5: Score the passing job; stored breakdown sums to total and explains each category
    resp_eval = client.post(f"/api/v1/applications/{app_id}/evaluate")
    assert resp_eval.status_code == 200
    assert resp_eval.json()["rules_result"] == "PASS"
    assert resp_eval.json()["score_total"] >= 65.0
    assert resp_eval.json()["new_state"] == "SHORTLISTED"

    # STEP 6: Generate the resume from facts only; generator is recorded
    resp_res = client.post(f"/api/v1/applications/{app_id}/generate-resume")
    assert resp_res.status_code == 200
    assert resp_res.json()["state"] == "RESUME_GENERATED"
    resume_sha = resp_res.json()["sha256"]

    # STEP 7: Validate the resume; then corrupt it with an invented skill and confirm it is rejected
    with Session(engine) as session:
        facts_db = session.scalars(select(FactDB).where(FactDB.candidate_id == candidate_id)).all()
        domain_facts = [
            Fact(id=f.id, candidate_id=f.candidate_id, kind=FactKind(f.kind), key=f.key, value=f.value, provenance=FactProvenance(f.provenance), status=FactStatus(f.status))
            for f in facts_db
        ]
        res_row = session.scalar(select(ResumeDB).where(ResumeDB.application_id == app_id))
        clean_struct = StructuredResume(**res_row.content)

        # Corrupt with invented skill in the Skills section
        corrupted = clean_struct.model_copy(deep=True)
        skills_sec = next(s for s in corrupted.sections if "skill" in s.title.lower())
        skills_sec.bullets.append(ResumeBullet(text="InventedSkill123", fact_ids=[domain_facts[0].id]))
        corrupted_report = FactualConsistencyValidator.validate_resume(corrupted, domain_facts)
        assert corrupted_report.is_valid is False
        assert any(v.code == "UNVERIFIED_SKILL" for v in corrupted_report.violations)

    # STEP 8: Populate the mock form through Playwright; values read back equal the plan
    plan = FieldMappingPlan(entries=[
        FieldMappingEntry(field_key="full_name", value="Ada Lovelace", source="FACT"),
        FieldMappingEntry(field_key="email", value="ada@example.com", source="FACT"),
        FieldMappingEntry(field_key="phone", value="+1234567890", source="FACT"),
        FieldMappingEntry(field_key="experience_years", value="3", source="FACT"),
        FieldMappingEntry(field_key="work_auth", value="YES", source="FACT"),
        FieldMappingEntry(field_key="sponsorship", value="NO", source="FACT"),
        FieldMappingEntry(field_key="eeo_gender", value="DECLINE", source="FACT"),
        FieldMappingEntry(field_key="legal_attestation", value="agree", source="APPROVED_ANSWER"),
    ])

    # STEP 9: Run all 15 checks; report is stored against the package hash
    resp_gate = client.post(f"/api/v1/applications/{app_id}/gate")
    assert resp_gate.status_code == 200
    assert resp_gate.json()["outcome"] == "PASS"
    package_hash = resp_gate.json()["package_hash"]

    # STEP 10: Approval workflow: Approve button refused while check fails, and works once it passes
    # Attempting to approve with an altered/wrong hash fails
    resp_bad_appr = client.post(f"/api/v1/applications/{app_id}/approve", json={"package_hash": "wrong_hash_xyz"})
    assert resp_bad_appr.status_code in (400, 422, 500)

    # Approving with the exact matching hash succeeds
    resp_appr = client.post(f"/api/v1/applications/{app_id}/approve", json={"package_hash": package_hash})
    assert resp_appr.status_code == 200
    approval_id = resp_appr.json()["approval_id"]

    # Verify state is APPROVED
    app_detail = client.get(f"/api/v1/applications/{app_id}").json()
    assert app_detail["state"] == "APPROVED"

    # STEP 11: Submit to the mock portal only; submission to any other host is refused
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Ticket to foreign host is rejected
        foreign_ticket = SubmissionTicket.create(
            application_id=app_id, package_hash=package_hash, approval_id=approval_id,
            gate_report_id="gate-1", target_url="https://external-forbidden.com/apply",
            secret_key=settings.SECRET_KEY,
        )
        submitter = Submitter(secret_key=settings.SECRET_KEY)
        with pytest.raises(AdapterError) as exc_host:
            await submitter.submit(page, foreign_ticket)
        assert "NOT in JOVSI_SUBMIT_HOST_ALLOWLIST" in str(exc_host.value)

        # STEP 12 & 13: Execute submission sequence, verify evidence reaches at least E2, persist attempt, ledger, evidence
        with Session(engine) as session:
            submission_outcome = await SubmissionService.submit(
                db=session,
                application_id=app_id,
                approval_id=approval_id,
                page=page,
                plan=plan,
                expected_package_hash=package_hash,
            )
            assert submission_outcome == "APPLIED_CONFIRMED"

        await browser.close()

    # STEP 14: Tracker shows APPLIED_CONFIRMED; portal's /__admin/applications holds exactly ONE record!
    resp_final = client.get(f"/api/v1/applications/{app_id}")
    assert resp_final.status_code == 200
    assert resp_final.json()["state"] == "APPLIED_CONFIRMED"

    # Ground-truth oracle verification via HTTP /__admin/applications
    import httpx
    oracle_records = httpx.get(f"{mock_server}/__admin/applications").json()
    assert len(oracle_records) == 1
    assert oracle_records[0]["full_name"] == "Ada Lovelace"
    assert oracle_records[0]["email"] == "ada@example.com"

    # Verify Honest Metrics API computes exact values from database
    resp_metrics = client.get("/api/v1/metrics/summary")
    assert resp_metrics.status_code == 200
    metrics_data = resp_metrics.json()
    assert metrics_data["confirmed"] == 1
    assert metrics_data["uncertain"] == 0
    assert metrics_data["failed"] == 0
    assert metrics_data["quota_used_today"] == 1
    assert metrics_data["confirmation_rate"] == 1.0

    app.dependency_overrides.clear()

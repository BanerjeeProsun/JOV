"""Comprehensive unit & integration tests for Milestone 10:
Job-Specific Resume Generation, Factual Consistency Grounding Validator, PDF/DOCX Artifacts & Versioning.
"""

from datetime import datetime
from io import BytesIO
import pytest
from pypdf import PdfReader
import docx
from fastapi.testclient import TestClient

from jovsi.domain.models import (
    DegreeLevel,
    FactKind,
    JobRequirements,
    ResumeBullet,
    ResumeSection,
    StructuredResume,
)
from jovsi.domain.provenance import ProvenanceEngine
from jovsi.domain.validators import FactualConsistencyValidator
from jovsi.services.resume import ResumeService
from jovsi.adapters.db.session import init_db
from jovsi.api.main import app


@pytest.fixture
def candidate_facts():
    return [
        ProvenanceEngine.create_user_fact(
            candidate_id="c1",
            kind=FactKind.CONTACT,
            key="contact",
            value={"name": "Alex Mercer", "email": "alex.mercer@jov.si", "phone": "+14155552671"},
        ),
        ProvenanceEngine.create_user_fact(
            candidate_id="c1",
            kind=FactKind.EDUCATION,
            key="edu1",
            value={"degree_level": "BACHELOR", "field": "Computer Science", "graduation_year": 2024},
        ),
        ProvenanceEngine.create_user_fact(
            candidate_id="c1",
            kind=FactKind.SKILL,
            key="sk_py",
            value={"name": "Python"},
        ),
        ProvenanceEngine.create_user_fact(
            candidate_id="c1",
            kind=FactKind.SKILL,
            key="sk_fastapi",
            value={"name": "FastAPI"},
        ),
        ProvenanceEngine.create_user_fact(
            candidate_id="c1",
            kind=FactKind.SKILL,
            key="sk_sql",
            value={"name": "PostgreSQL"},
        ),
        ProvenanceEngine.create_user_fact(
            candidate_id="c1",
            kind=FactKind.EXPERIENCE,
            key="exp1",
            value={
                "title": "Backend Engineer",
                "duration_months": 24,
                "description": "Architected low-latency microservices handling 1000 requests per second.",
                "skills": ["Python", "FastAPI", "PostgreSQL"],
            },
        ),
    ]


@pytest.fixture
def target_requirements():
    return JobRequirements(
        min_degree=DegreeLevel.BACHELOR,
        required_skills=["Python", "FastAPI"],
        preferred_skills=["PostgreSQL", "Docker"],
        responsibilities=["Architect high-throughput microservices"],
    )


# -------------------------------------------------------------------------
# 1. DETERMINISTIC RESUME GENERATION & GROUNDING
# -------------------------------------------------------------------------

def test_deterministic_resume_generation_and_grounding(candidate_facts, target_requirements) -> None:
    """Verifies that generated resume is 100% grounded, cites verified facts, and passes validation."""
    resume, report = ResumeService.generate_deterministic_resume(
        candidate_name="Alex Mercer",
        facts=candidate_facts,
        requirements=target_requirements,
        job_description_clean="We are looking for a backend engineer to architect high-throughput microservices.",
    )

    assert report.is_valid is True
    assert len(report.violations) == 0
    assert resume.candidate_name == "Alex Mercer"
    assert resume.email == "alex.mercer@jov.si"
    assert resume.phone == "+14155552671"

    # Every bullet must cite at least one verified fact
    for sec in resume.sections:
        for b in sec.bullets:
            assert len(b.fact_ids) >= 1

    # Skills section prioritizes required skills
    skills_sec = next(s for s in resume.sections if s.title == "Skills")
    skill_names = [b.text.lower() for b in skills_sec.bullets]
    assert skill_names[0] == "python"
    assert skill_names[1] == "fastapi"


# -------------------------------------------------------------------------
# 2. FACTUAL CONSISTENCY VALIDATOR CATCHES HALLUCINATIONS
# -------------------------------------------------------------------------

def test_validator_rejects_unverified_skill(candidate_facts) -> None:
    """Validator catches unverified skills injected into the skills section."""
    hallucinated_resume = StructuredResume(
        candidate_name="Alex Mercer",
        email="alex.mercer@jov.si",
        phone="+14155552671",
        sections=[
            ResumeSection(
                title="Skills",
                bullets=[
                    ResumeBullet(text="Kubernetes", fact_ids=[candidate_facts[2].id]),
                ],
            )
        ],
    )
    report = FactualConsistencyValidator.validate_resume(
        resume=hallucinated_resume,
        candidate_facts=candidate_facts,
    )
    assert report.is_valid is False
    assert any(v.code == "UNVERIFIED_SKILL" for v in report.violations)


def test_validator_rejects_unverified_numbers(candidate_facts) -> None:
    """Validator catches fabricated metrics/numbers not present in cited facts."""
    hallucinated_resume = StructuredResume(
        candidate_name="Alex Mercer",
        email="alex.mercer@jov.si",
        phone="+14155552671",
        sections=[
            ResumeSection(
                title="Experience",
                bullets=[
                    ResumeBullet(
                        text="Scaled throughput by 999% and decreased latency by 85%.",
                        fact_ids=[candidate_facts[5].id],
                    ),
                ],
            )
        ],
    )
    report = FactualConsistencyValidator.validate_resume(
        resume=hallucinated_resume,
        candidate_facts=candidate_facts,
    )
    assert report.is_valid is False
    assert any(v.code == "UNVERIFIED_NUMBER" for v in report.violations)


def test_validator_rejects_unverified_seniority(candidate_facts) -> None:
    """Validator catches unearned seniority claims (e.g. Principal / Lead / Director)."""
    hallucinated_resume = StructuredResume(
        candidate_name="Alex Mercer",
        email="alex.mercer@jov.si",
        phone="+14155552671",
        sections=[
            ResumeSection(
                title="Experience",
                bullets=[
                    ResumeBullet(
                        text="Served as Principal Architect spearheading global systems.",
                        fact_ids=[candidate_facts[5].id],
                    ),
                ],
            )
        ],
    )
    report = FactualConsistencyValidator.validate_resume(
        resume=hallucinated_resume,
        candidate_facts=candidate_facts,
    )
    assert report.is_valid is False
    assert any(v.code == "UNVERIFIED_SENIORITY_CLAIM" for v in report.violations)


def test_validator_rejects_verbatim_job_text_contamination(candidate_facts) -> None:
    """Validator catches verbatim copying of > 6 words from the job description."""
    job_desc = "must possess extensive deep domain knowledge in developing fault tolerant distributed microservices across regions"
    contaminated_resume = StructuredResume(
        candidate_name="Alex Mercer",
        email="alex.mercer@jov.si",
        phone="+14155552671",
        sections=[
            ResumeSection(
                title="Experience",
                bullets=[
                    ResumeBullet(
                        text="Demonstrated deep domain knowledge in developing fault tolerant distributed microservices across regions.",
                        fact_ids=[candidate_facts[5].id],
                    ),
                ],
            )
        ],
    )
    report = FactualConsistencyValidator.validate_resume(
        resume=contaminated_resume,
        candidate_facts=candidate_facts,
        job_description_clean=job_desc,
    )
    assert report.is_valid is False
    assert any(v.code == "JOB_TEXT_CONTAMINATION" for v in report.violations)


# -------------------------------------------------------------------------
# 3. PDF & DOCX RENDERING AND ROUND-TRIP
# -------------------------------------------------------------------------

def test_pdf_rendering_and_roundtrip(candidate_facts, target_requirements) -> None:
    """PDF stream rendering extracts cleanly and round-trips all facts."""
    resume, _ = ResumeService.generate_deterministic_resume(
        candidate_name="Alex Mercer",
        facts=candidate_facts,
        requirements=target_requirements,
    )
    pdf_bytes = ResumeService.render_pdf_bytes(resume)
    assert len(pdf_bytes) > 500
    assert pdf_bytes.startswith(b"%PDF")

    # Roundtrip check
    assert ResumeService.verify_pdf_roundtrip(pdf_bytes, resume) is True


def test_docx_rendering(candidate_facts, target_requirements) -> None:
    """DOCX rendering produces valid Word document with paragraphs and headings."""
    resume, _ = ResumeService.generate_deterministic_resume(
        candidate_name="Alex Mercer",
        facts=candidate_facts,
        requirements=target_requirements,
    )
    docx_bytes = ResumeService.render_docx_bytes(resume)
    assert len(docx_bytes) > 1000

    doc = docx.Document(BytesIO(docx_bytes))
    paragraphs_text = [p.text for p in doc.paragraphs]
    assert any("ALEX MERCER" in t or "Alex Mercer" in t for t in paragraphs_text)
    assert any("alex.mercer@jov.si" in t for t in paragraphs_text)


# -------------------------------------------------------------------------
# 4. APPLICATION RESUME API: EDIT, DOWNLOAD & VERSION HISTORY
# -------------------------------------------------------------------------

def test_resume_api_generate_edit_and_export_flow() -> None:
    """Full API vertical slice for resume generation, PDF/DOCX export, editing, and versioning."""
    init_db()
    client = TestClient(app)

    # 1. Register candidate user
    user_email = f"resume_test_{int(datetime.now().timestamp())}@jov.si"
    reg_resp = client.post(
        "/api/v1/auth/register",
        json={"email": user_email, "password": "Password123!", "display_name": "Resume Tester"},
    )
    assert reg_resp.status_code == 201
    cand_resp = client.get("/api/v1/candidates")
    candidate_id = cand_resp.json()[0]["id"]

    # 2. Add verified facts
    f_contact = client.post(
        f"/api/v1/candidates/{candidate_id}/facts",
        json={
            "kind": "CONTACT",
            "key": "contact_res",
            "value": {"name": "Resume Tester", "email": user_email, "phone": "+19998887777"},
            "status": "ACTIVE",
            "provenance": "USER_VERIFIED",
        },
    ).json()

    f_skill = client.post(
        f"/api/v1/candidates/{candidate_id}/facts",
        json={
            "kind": "SKILL",
            "key": "sk_py_test",
            "value": {"name": "Python"},
            "status": "ACTIVE",
            "provenance": "USER_VERIFIED",
        },
    ).json()

    f_exp = client.post(
        f"/api/v1/candidates/{candidate_id}/facts",
        json={
            "kind": "EXPERIENCE",
            "key": "exp_res_test",
            "value": {"title": "Backend Engineer", "description": "Built resilient Python APIs.", "duration_months": 24},
            "status": "ACTIVE",
            "provenance": "USER_VERIFIED",
        },
    ).json()

    # 3. Create job & application
    job_resp = client.post(
        "/api/v1/jobs/import",
        json={
            "title": "Python Engineer",
            "company_name": "Tech Hub",
            "source_url": f"https://example.com/job/res-{int(datetime.now().timestamp())}",
            "target_locations": ["Remote, US"],
            "raw_description": "We need a Python engineer.",
            "required_skills": ["Python"],
        },
    )
    assert job_resp.status_code == 201
    job_id = job_resp.json()["id"]

    app_row = client.post("/api/v1/applications", json={"candidate_id": candidate_id, "job_id": job_id}).json()
    app_id = app_row["id"]

    # Evaluate application
    eval_resp = client.post(f"/api/v1/applications/{app_id}/evaluate")
    assert eval_resp.status_code == 200

    # 4. Generate Resume (v1)
    gen_resp = client.post(f"/api/v1/applications/{app_id}/generate-resume")
    assert gen_resp.status_code == 200
    gen_data = gen_resp.json()
    assert gen_data["status"] == "generated"
    assert gen_data["state"] == "RESUME_GENERATED"
    assert gen_data["version"] == 1
    sha_v1 = gen_data["sha256"]

    # 5. Check version history
    versions_resp = client.get(f"/api/v1/applications/{app_id}/resume/versions")
    assert versions_resp.status_code == 200
    versions = versions_resp.json()
    assert len(versions) == 1
    assert versions[0]["version"] == 1
    assert versions[0]["is_current"] is True

    # 6. Export PDF & DOCX
    pdf_resp = client.get(f"/api/v1/applications/{app_id}/resume/pdf")
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"] == "application/pdf"
    assert len(pdf_resp.content) > 500

    docx_resp = client.get(f"/api/v1/applications/{app_id}/resume/docx")
    assert docx_resp.status_code == 200
    assert "openxmlformats" in docx_resp.headers["content-type"]
    assert len(docx_resp.content) > 1000

    # 7. Edit Resume with valid edit -> increments to v2
    current_resume = gen_data["resume"]
    valid_edit = {
        "candidate_name": "Resume Tester",
        "email": user_email,
        "phone": "+19998887777",
        "sections": [
            {
                "title": "Skills",
                "bullets": [{"text": "Python", "fact_ids": [f_skill["id"]]}],
            },
            {
                "title": "Experience",
                "bullets": [{"text": "Backend Engineer: Built resilient Python APIs.", "fact_ids": [f_exp["id"]]}],
            },
        ],
    }
    edit_resp = client.put(f"/api/v1/applications/{app_id}/resume", json=valid_edit)
    assert edit_resp.status_code == 200
    edit_data = edit_resp.json()
    assert edit_data["status"] == "updated"
    assert edit_data["version"] == 2

    # Check updated version history
    versions_after = client.get(f"/api/v1/applications/{app_id}/resume/versions").json()
    assert len(versions_after) == 2
    assert versions_after[0]["version"] == 2
    assert versions_after[0]["is_current"] is True

    # 8. Edit Resume with invalid hallucinated claim -> fails validation with HTTP 422
    invalid_edit = {
        "candidate_name": "Resume Tester",
        "email": user_email,
        "phone": "+19998887777",
        "sections": [
            {
                "title": "Skills",
                "bullets": [{"text": "Rust & Blockchain", "fact_ids": [f_skill["id"]]}],
            }
        ],
    }
    invalid_resp = client.put(f"/api/v1/applications/{app_id}/resume", json=invalid_edit)
    assert invalid_resp.status_code == 422
    assert "violations" in invalid_resp.json()["detail"]

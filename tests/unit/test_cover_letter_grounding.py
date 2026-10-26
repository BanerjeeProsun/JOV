"""Comprehensive unit & integration tests for Milestone 11:
Cover Letters with Provenance Grounding, Factual Consistency Validation, PDF/DOCX/TXT Export & Editing API.
"""

from io import BytesIO
import pytest
from pypdf import PdfReader
import docx
from fastapi.testclient import TestClient

from jovsi.domain.models import (
    DegreeLevel,
    FactKind,
    JobRequirements,
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
        preferred_skills=["PostgreSQL"],
        responsibilities=["Architect high-throughput microservices"],
    )


# -------------------------------------------------------------------------
# 1. DETERMINISTIC GENERATION & VALIDATION
# -------------------------------------------------------------------------

def test_deterministic_cover_letter_passes_validation(candidate_facts, target_requirements) -> None:
    """Verifies that deterministically synthesized cover letter is 100% grounded and passes validator."""
    letter = ResumeService.generate_cover_letter(
        candidate_name="Alex Mercer",
        company_name="Acme Corp",
        role_title="Backend Engineer",
        facts=candidate_facts,
        requirements=target_requirements,
    )

    report = FactualConsistencyValidator.validate_cover_letter(
        cover_letter=letter,
        candidate_facts=candidate_facts,
        company_name="Acme Corp",
        role_title="Backend Engineer",
    )

    assert report.is_valid is True
    assert len(report.violations) == 0
    assert "Alex Mercer" in letter
    assert "Acme Corp" in letter
    assert "Backend Engineer" in letter
    assert "alex.mercer@jov.si" in letter


# -------------------------------------------------------------------------
# 2. VALIDATOR CATCHES EMPTY / TRIVIAL COVER LETTERS
# -------------------------------------------------------------------------

def test_validator_rejects_empty_or_trivial_cover_letter(candidate_facts) -> None:
    """Verifies that empty or excessively brief cover letters are rejected."""
    short_letter = "Hi, please hire me. Thanks."
    report = FactualConsistencyValidator.validate_cover_letter(
        cover_letter=short_letter,
        candidate_facts=candidate_facts,
    )
    assert report.is_valid is False
    assert any(v.code == "EMPTY_OR_TRIVIAL" for v in report.violations)


# -------------------------------------------------------------------------
# 3. VALIDATOR CATCHES UNGROUNDED INTEREST & SYCOPHANCY
# -------------------------------------------------------------------------

def test_validator_rejects_ungrounded_interest_and_sycophancy(candidate_facts) -> None:
    """Verifies that fabricated admiration/sycophancy phrases trigger validation failure."""
    sycophantic_letter = (
        "Dear Hiring Team at CyberDyne Systems,\n\n"
        "I have always admired CyberDyne Systems and it is my lifelong dream to join your engineering team. "
        "With my background in Python and FastAPI, I am eager to contribute to your mission.\n\n"
        "Sincerely,\nAlex Mercer\nalex.mercer@jov.si"
    )

    report = FactualConsistencyValidator.validate_cover_letter(
        cover_letter=sycophantic_letter,
        candidate_facts=candidate_facts,
    )
    assert report.is_valid is False
    codes = [v.code for v in report.violations]
    assert "UNGROUNDED_INTEREST_CLAIM" in codes
    assert any("always admired" in v.message for v in report.violations)


# -------------------------------------------------------------------------
# 4. VALIDATOR CATCHES UNVERIFIED TECHNICAL SKILLS
# -------------------------------------------------------------------------

def test_validator_rejects_unverified_technical_skills(candidate_facts, target_requirements) -> None:
    """Verifies that mentioning technical skills not present in candidate facts fails validation."""
    letter = ResumeService.generate_cover_letter(
        candidate_name="Alex Mercer",
        company_name="Acme Corp",
        role_title="Backend Engineer",
        facts=candidate_facts,
        requirements=target_requirements,
    )

    hallucinated_letter = letter.replace(
        "software reliability, fact-verified execution",
        "software reliability with deep production expertise in Rust and Solidity",
    )

    report = FactualConsistencyValidator.validate_cover_letter(
        cover_letter=hallucinated_letter,
        candidate_facts=candidate_facts,
    )
    assert report.is_valid is False
    codes = [v.code for v in report.violations]
    assert "UNVERIFIED_SKILL" in codes
    entities = [v.entity for v in report.violations]
    assert "rust" in entities
    assert "solidity" in entities


# -------------------------------------------------------------------------
# 5. VALIDATOR CATCHES UNVERIFIED NUMBERS / METRICS
# -------------------------------------------------------------------------

def test_validator_rejects_unverified_numbers(candidate_facts, target_requirements) -> None:
    """Verifies that fabricated numbers/metrics fail validation."""
    letter = ResumeService.generate_cover_letter(
        candidate_name="Alex Mercer",
        company_name="Acme Corp",
        role_title="Backend Engineer",
        facts=candidate_facts,
        requirements=target_requirements,
    )

    hallucinated_letter = letter.replace(
        "delivering robust solutions",
        "increasing company revenue by 450% and scaling systems to 85000 users",
    )

    report = FactualConsistencyValidator.validate_cover_letter(
        cover_letter=hallucinated_letter,
        candidate_facts=candidate_facts,
    )
    assert report.is_valid is False
    codes = [v.code for v in report.violations]
    assert "UNVERIFIED_NUMBER" in codes
    entities = [v.entity for v in report.violations]
    assert "450%" in entities or "450" in entities


# -------------------------------------------------------------------------
# 6. VALIDATOR CATCHES UNVERIFIED SENIORITY CLAIMS
# -------------------------------------------------------------------------

def test_validator_rejects_unverified_seniority(candidate_facts, target_requirements) -> None:
    """Verifies that superlatives and seniority titles not in facts fail validation."""
    letter = ResumeService.generate_cover_letter(
        candidate_name="Alex Mercer",
        company_name="Acme Corp",
        role_title="Backend Engineer",
        facts=candidate_facts,
        requirements=target_requirements,
    )

    hallucinated_letter = letter.replace(
        "Dear Hiring Team at Acme Corp,",
        "Dear Hiring Team at Acme Corp,\n\nAs the Chief Architect and Principal Director of my organization,",
    )

    report = FactualConsistencyValidator.validate_cover_letter(
        cover_letter=hallucinated_letter,
        candidate_facts=candidate_facts,
    )
    assert report.is_valid is False
    codes = [v.code for v in report.violations]
    assert "UNVERIFIED_SENIORITY_CLAIM" in codes
    entities = [v.entity for v in report.violations]
    assert "chief" in entities or "director" in entities or "principal" in entities


# -------------------------------------------------------------------------
# 7. DOCUMENT EXPORTS: PDF AND DOCX RENDERING
# -------------------------------------------------------------------------

def test_cover_letter_pdf_and_docx_rendering(candidate_facts, target_requirements) -> None:
    """Verifies PDF and DOCX binary exports contain letter text and candidate details."""
    letter = ResumeService.generate_cover_letter(
        candidate_name="Alex Mercer",
        company_name="Acme Corp",
        role_title="Backend Engineer",
        facts=candidate_facts,
        requirements=target_requirements,
    )

    # 1. Render PDF
    pdf_bytes = ResumeService.render_cover_letter_pdf(
        cover_letter_text=letter,
        candidate_name="Alex Mercer",
        email="alex.mercer@jov.si",
        phone="+14155552671",
        company_name="Acme Corp",
    )
    assert len(pdf_bytes) > 500
    reader = PdfReader(BytesIO(pdf_bytes))
    assert len(reader.pages) >= 1
    extracted_text = reader.pages[0].extract_text()
    assert "Alex Mercer" in extracted_text
    assert "Acme Corp" in extracted_text

    # 2. Render DOCX
    docx_bytes = ResumeService.render_cover_letter_docx(
        cover_letter_text=letter,
        candidate_name="Alex Mercer",
        email="alex.mercer@jov.si",
        phone="+14155552671",
        company_name="Acme Corp",
    )
    assert len(docx_bytes) > 1000
    doc = docx.Document(BytesIO(docx_bytes))
    full_doc_text = "\n".join([p.text for p in doc.paragraphs])
    assert "Alex Mercer" in full_doc_text
    assert "Acme Corp" in full_doc_text


# -------------------------------------------------------------------------
# 8. API FLOW: GENERATE, EDIT, REJECT INVALID, AND EXPORT
# -------------------------------------------------------------------------

def test_cover_letter_api_flow_end_to_end() -> None:
    """Verifies API endpoints for cover letter generation, editing, factual rejection, and downloads."""
    init_db()
    client = TestClient(app)

    user_email = f"cl_test_{datetime_now_str()}@jov.si"
    reg_resp = client.post(
        "/api/v1/auth/register",
        json={"email": user_email, "password": "SecurePassword123!", "display_name": "CoverLetter Tester"},
    )
    assert reg_resp.status_code == 201

    me_resp = client.get("/api/v1/auth/me")
    assert me_resp.status_code == 200

    cand_resp = client.get("/api/v1/candidates")
    assert cand_resp.status_code == 200
    candidate_id = cand_resp.json()[0]["id"]

    # Ingest verified facts
    client.post(f"/api/v1/candidates/{candidate_id}/facts", json={
        "kind": "CONTACT", "key": "contact", "value": {"name": "CoverLetter Tester", "email": user_email, "phone": "+19998887777"}, "status": "ACTIVE", "provenance": "USER_VERIFIED"
    })
    client.post(f"/api/v1/candidates/{candidate_id}/facts", json={
        "kind": "SKILL", "key": "sk_python", "value": {"name": "Python"}, "status": "ACTIVE", "provenance": "USER_VERIFIED"
    })
    client.post(f"/api/v1/candidates/{candidate_id}/facts", json={
        "kind": "EXPERIENCE", "key": "exp_backend", "value": {"title": "Software Engineer", "description": "Built scalable cloud services."}, "status": "ACTIVE", "provenance": "USER_VERIFIED"
    })

    # Import Job
    job_resp = client.post("/api/v1/jobs/import", json={
        "title": "Software Engineer",
        "company_name": "Stripe",
        "source_url": f"https://stripe.com/jobs/backend-{int(datetime_now_str())}",
        "raw_description": "We need a Software Engineer with Python skills to build scalable payment systems.",
        "target_locations": ["Remote, US"],
        "required_skills": ["Python"],
    })
    assert job_resp.status_code == 201
    job_id = job_resp.json()["id"]

    # Create Application & evaluate
    app_resp = client.post("/api/v1/applications", json={"candidate_id": candidate_id, "job_id": job_id})
    assert app_resp.status_code == 201
    app_id = app_resp.json()["id"]

    client.post(f"/api/v1/applications/{app_id}/evaluate")
    # Generate Resume (which also synthesizes cover letter)
    client.post(f"/api/v1/applications/{app_id}/generate-resume")

    # 1. Regenerate tailored cover letter endpoint
    gen_cl_resp = client.post(f"/api/v1/applications/{app_id}/generate-cover-letter")
    assert gen_cl_resp.status_code == 200
    cl_data = gen_cl_resp.json()
    assert cl_data["status"] == "generated"
    assert "CoverLetter Tester" in cl_data["cover_letter"]
    assert cl_data["is_valid"] is True

    # 2. Export TXT
    txt_resp = client.get(f"/api/v1/applications/{app_id}/cover-letter/txt")
    assert txt_resp.status_code == 200
    assert "text/plain" in txt_resp.headers["content-type"]
    assert "CoverLetter Tester" in txt_resp.text

    # 3. Export PDF
    pdf_resp = client.get(f"/api/v1/applications/{app_id}/cover-letter/pdf")
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"] == "application/pdf"
    assert len(pdf_resp.content) > 500

    # 4. Export DOCX
    docx_resp = client.get(f"/api/v1/applications/{app_id}/cover-letter/docx")
    assert docx_resp.status_code == 200
    assert "openxmlformats" in docx_resp.headers["content-type"]
    assert len(docx_resp.content) > 1000

    # 5. Edit cover letter with valid text
    valid_edit = (
        "Dear Hiring Team at Stripe,\n\n"
        "I am writing to express my interest in the Software Engineer position. "
        "With my verified background in Python and experience delivering cloud services, "
        "I look forward to discussing how I can contribute to Stripe.\n\n"
        "Sincerely,\nCoverLetter Tester\n" + user_email
    )
    edit_resp = client.put(f"/api/v1/applications/{app_id}/cover-letter", json={"cover_letter": valid_edit})
    assert edit_resp.status_code == 200
    assert edit_resp.json()["status"] == "updated"

    # 6. Edit cover letter with invalid hallucination -> rejected with 422
    invalid_edit = (
        "Dear Hiring Team at Stripe,\n\n"
        "It is my lifelong dream to work at Stripe! I have extensive experience in Rust and Solidity, "
        "and I grew revenue by 900% at my previous firm.\n\n"
        "Sincerely,\nCoverLetter Tester"
    )
    invalid_resp = client.put(f"/api/v1/applications/{app_id}/cover-letter", json={"cover_letter": invalid_edit})
    assert invalid_resp.status_code == 422
    assert "violations" in invalid_resp.json()["detail"]


def datetime_now_str() -> str:
    import time
    return str(int(time.time() * 1000))

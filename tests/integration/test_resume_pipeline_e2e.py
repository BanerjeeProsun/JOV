"""Comprehensive End-to-End Pipeline Tests for Resume Generation and PDF Download.

Verifies:
1. Synthetic candidate & job tailoring pipeline.
2. Content integrity (no duplicate bullets, no repeated titles, no literal 'None', no \x7f).
3. Visual fidelity & A4 1-page conformance matching reference Prosun_Banerjee_CV.
4. Valid PDF byte stream (%PDF-, extractable text).
5. Download endpoint HTTP 200, Content-Type, Content-Disposition (Firstname_Lastname_CV.pdf).
6. Failure handling (401 unauthenticated, 404 not found return JSON errors).
7. Candidate filename generation edge cases.
"""

import io
import os
from datetime import datetime
from pypdf import PdfReader
import pytest
from fastapi.testclient import TestClient

from jovsi.api.main import app
from jovsi.adapters.db.session import init_db
from jovsi.domain.models import FactKind, JobRequirements, ResumeBullet, ResumeSection, StructuredResume
from jovsi.domain.provenance import ProvenanceEngine
from jovsi.services.resume import ResumeService, generate_resume_filename, normalize_bullet_text
from jovsi.services.resume_parser import MasterResumeParser


# ---------------------------------------------------------------------------
# Test A: Synthetic Candidate & Job Tailoring Pipeline
# ---------------------------------------------------------------------------
def test_synthetic_candidate_job_tailoring_pipeline():
    init_db()
    client = TestClient(app)

    # 1. Register candidate
    ts = int(datetime.now().timestamp())
    email = f"synth_{ts}@example.com"
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!", "display_name": "Ada Lovelace"},
    )
    assert reg.status_code == 201
    cand_id = client.get("/api/v1/candidates").json()[0]["id"]

    # 2. Add verified facts
    client.post(
        f"/api/v1/candidates/{cand_id}/facts",
        json={
            "kind": "CONTACT",
            "key": "contact_ada",
            "value": {
                "display_name": "Ada Lovelace",
                "email": email,
                "phone": "+44 20 7946 0991",
                "location": "London, UK",
                "linkedin": "linkedin.com/in/adalovelace",
            },
            "status": "ACTIVE",
            "provenance": "USER_VERIFIED",
        },
    )

    client.post(
        f"/api/v1/candidates/{cand_id}/facts",
        json={
            "kind": "SUMMARY",
            "key": "summary_ada",
            "value": {"text": "Mathematician and computer pioneer specializing in analytical engines."},
            "status": "ACTIVE",
            "provenance": "USER_VERIFIED",
        },
    )

    client.post(
        f"/api/v1/candidates/{cand_id}/facts",
        json={
            "kind": "SKILL",
            "key": "sk_algorithms",
            "value": {"name": "Algorithms"},
            "status": "ACTIVE",
            "provenance": "USER_VERIFIED",
        },
    )

    client.post(
        f"/api/v1/candidates/{cand_id}/facts",
        json={
            "kind": "SKILL",
            "key": "sk_python",
            "value": {"name": "Python"},
            "status": "ACTIVE",
            "provenance": "USER_VERIFIED",
        },
    )

    client.post(
        f"/api/v1/candidates/{cand_id}/facts",
        json={
            "kind": "EXPERIENCE",
            "key": "exp_analytical",
            "value": {
                "title": "Chief Algorithm Architect",
                "company": "Babbage Analytical Engines Ltd",
                "location": "London, UK",
                "dates": "1842 - 1845",
                "bullets": [
                    "Created the first algorithm intended to be carried out by a machine.",
                    "Pioneered theoretical concepts of computing beyond mere arithmetic calculation.",
                ],
            },
            "status": "ACTIVE",
            "provenance": "USER_VERIFIED",
        },
    )

    # 3. Create Job
    job_resp = client.post(
        "/api/v1/jobs/import",
        json={
            "title": "Senior Algorithm Engineer",
            "company_name": "Analytical Corp",
            "source_url": f"https://example.com/jobs/ada-{ts}",
            "target_locations": ["London, UK"],
            "raw_description": "Seeking an expert in algorithms and computing architectures.",
            "required_skills": ["Algorithms"],
            "preferred_skills": ["Python"],
        },
    )
    assert job_resp.status_code == 201
    job_id = job_resp.json()["id"]

    # 4. Create and Evaluate Application
    app_data = client.post("/api/v1/applications", json={"candidate_id": cand_id, "job_id": job_id}).json()
    app_id = app_data["id"]

    eval_resp = client.post(f"/api/v1/applications/{app_id}/evaluate")
    assert eval_resp.status_code == 200

    # 5. Generate tailored resume
    gen_resp = client.post(f"/api/v1/applications/{app_id}/generate-resume")
    assert gen_resp.status_code == 200
    gen_data = gen_resp.json()
    assert gen_data["status"] == "generated"
    assert gen_data["version"] == 1


# ---------------------------------------------------------------------------
# Test B: Content Integrity (No Duplicates, No Repeated Prefixes, No 'None')
# ---------------------------------------------------------------------------
def test_content_integrity_normalization_and_literals():
    # Test prefix deduplication
    assert normalize_bullet_text("Built role: Built role-based access control") == "Built role-based access control"
    assert normalize_bullet_text("• Designed resilient architecture.") == "Designed resilient architecture."
    assert normalize_bullet_text("FastAPI: FastAPI service for async events") == "FastAPI service for async events"
    assert normalize_bullet_text("Control \x7f character test \x00") == "Control  character test"

    # Test structured resume model sanitization
    raw = StructuredResume(
        candidate_name="JOHN DOE",
        headline="Full Stack Engineer",
        email="john@example.com",
        phone="None",  # should be cleaned to None
        location="null",  # should be cleaned to None
        sections=[
            ResumeSection(
                title="EXPERIENCE",
                bullets=[
                    ResumeBullet(text="Built role: Built role-based access control", fact_ids=["f1"]),
                    ResumeBullet(text="Built role: Built role-based access control", fact_ids=["f1"]),  # duplicate
                    ResumeBullet(text="Shipped production microservices.\x7f", fact_ids=["f2"]),
                ],
            )
        ],
    )
    assert raw.phone is None
    assert raw.location is None

    cleaned = ResumeService.normalize_resume_content(raw)
    assert cleaned.candidate_name == "John Doe"
    exp_sec = cleaned.sections[0]
    assert len(exp_sec.bullets) == 2  # duplicate removed
    assert exp_sec.bullets[0].text == "Built role-based access control"
    assert "\x7f" not in exp_sec.bullets[1].text


# ---------------------------------------------------------------------------
# Test C & D: Visual Fidelity, A4 Dimensions, 1-Page Layout on Reference CV
# ---------------------------------------------------------------------------
def test_reference_prosun_cv_visual_fidelity_and_pdf_generation():
    ref_pdf = r"storage\documents\68dd9203-93c2-4635-a0d9-6428d53432f7\f3610a92f8b3ab71_Prosun_Banerjee_CV.pdf"
    if not os.path.exists(ref_pdf):
        pytest.skip(f"Reference PDF not found at {ref_pdf}")

    with open(ref_pdf, "rb") as f:
        pdf_bytes = f.read()

    raw_text = MasterResumeParser.extract_text_from_bytes(pdf_bytes, "Prosun_Banerjee_CV.pdf")
    entities = MasterResumeParser.extract_structured_entities(raw_text)

    facts_dict = MasterResumeParser.build_proposed_facts("c_ref_test", "doc_ref", entities)
    facts = [
        ProvenanceEngine.create_user_fact(
            "c_ref_test",
            FactKind(f["kind"] if isinstance(f["kind"], str) else f["kind"].value),
            f["key"],
            f["value"],
        )
        for f in facts_dict
    ]

    req = JobRequirements(
        required_skills=["FastAPI", "Python", "PostgreSQL", "Playwright"],
        preferred_skills=["Docker", "Laravel", "React"],
    )

    resume, report = ResumeService.generate_deterministic_resume(
        candidate_name=entities.get("name", "Prosun Banerjee"),
        facts=facts,
        requirements=req,
    )
    assert report.is_valid is True

    # Render PDF bytes
    rendered_pdf = ResumeService.render_pdf_bytes(resume)
    assert rendered_pdf.startswith(b"%PDF-")
    assert len(rendered_pdf) > 2000

    # Inspect page count and dimensions via pypdf
    reader = PdfReader(io.BytesIO(rendered_pdf))
    assert len(reader.pages) == 1, f"Expected exactly 1 page, got {len(reader.pages)}"

    page = reader.pages[0]
    width = float(page.mediabox.width)
    height = float(page.mediabox.height)
    # A4 standard: ~595 pt x ~842 pt
    assert 590 <= width <= 600, f"Unexpected width: {width}"
    assert 835 <= height <= 845, f"Unexpected height: {height}"

    page_text = page.extract_text(extraction_mode="layout")
    assert "PROSUN BANERJEE" in page_text or "Prosun Banerjee" in page_text
    assert "prosunbanerjee2815@gmail.com" in page_text
    assert "+91 73640 04868" in page_text
    assert "None" not in page_text
    assert "null" not in page_text
    assert "undefined" not in page_text
    assert "Built role: Built role-based access control" not in page_text


# ---------------------------------------------------------------------------
# Test E: Download Endpoint Headers, Content-Type, Content-Disposition
# ---------------------------------------------------------------------------
def test_download_endpoint_headers_and_filename():
    init_db()
    client = TestClient(app)

    # Register candidate Prosun Banerjee
    ts = int(datetime.now().timestamp())
    email = f"prosun_{ts}@example.com"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!", "display_name": "Prosun Banerjee"},
    )
    cand_id = client.get("/api/v1/candidates").json()[0]["id"]

    client.post(
        f"/api/v1/candidates/{cand_id}/facts",
        json={
            "kind": "CONTACT",
            "key": "contact_prosun",
            "value": {
                "display_name": "Prosun Banerjee",
                "email": email,
                "phone": "+91 73640 04868",
                "location": "Kolkata, India",
            },
            "status": "ACTIVE",
            "provenance": "USER_VERIFIED",
        },
    )

    client.post(
        f"/api/v1/candidates/{cand_id}/facts",
        json={
            "kind": "SKILL",
            "key": "sk_fastapi",
            "value": {"name": "FastAPI"},
            "status": "ACTIVE",
            "provenance": "USER_VERIFIED",
        },
    )

    job_resp = client.post(
        "/api/v1/jobs/import",
        json={
            "title": "Backend Engineer",
            "company_name": "Global Tech",
            "source_url": f"https://example.com/jobs/p-{ts}",
            "raw_description": "We need FastAPI developers.",
            "required_skills": ["FastAPI"],
        },
    )
    job_id = job_resp.json()["id"]

    app_id = client.post("/api/v1/applications", json={"candidate_id": cand_id, "job_id": job_id}).json()["id"]
    client.post(f"/api/v1/applications/{app_id}/evaluate")
    client.post(f"/api/v1/applications/{app_id}/generate-resume")

    # Download PDF
    pdf_resp = client.get(f"/api/v1/applications/{app_id}/resume/pdf")
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"] == "application/pdf"
    assert "attachment" in pdf_resp.headers["content-disposition"]
    assert 'filename="Prosun_Banerjee_CV.pdf"' in pdf_resp.headers["content-disposition"]
    assert pdf_resp.content.startswith(b"%PDF-")

    # Download DOCX
    docx_resp = client.get(f"/api/v1/applications/{app_id}/resume/docx")
    assert docx_resp.status_code == 200
    assert "openxmlformats" in docx_resp.headers["content-type"]
    assert 'filename="Prosun_Banerjee_CV.docx"' in docx_resp.headers["content-disposition"]
    assert len(docx_resp.content) > 1000


# ---------------------------------------------------------------------------
# Test F: Download Failure Handling (401 Unauthorized, 404 Not Found)
# ---------------------------------------------------------------------------
def test_download_failure_handling_unauthenticated_and_not_found():
    # Fresh unauthenticated client
    unauthed_client = TestClient(app)

    # 1. 401 on protected endpoint without valid session cookie
    resp_unauth = unauthed_client.get("/api/v1/applications/non-existent-id/resume/pdf")
    # Must return JSON error response, NOT a corrupt file
    assert resp_unauth.status_code in (401, 404)
    assert "application/json" in resp_unauth.headers.get("content-type", "")
    err_json = resp_unauth.json()
    assert "detail" in err_json or "message" in err_json

    # 2. 404 on non-existent application with authenticated client
    authed_client = TestClient(app)
    ts = int(datetime.now().timestamp())
    authed_client.post(
        "/api/v1/auth/register",
        json={"email": f"auth_err_{ts}@example.com", "password": "Password123!", "display_name": "Auth Tester"},
    )
    resp_404 = authed_client.get("/api/v1/applications/00000000-0000-0000-0000-000000000000/resume/pdf")
    assert resp_404.status_code == 404
    assert "application/json" in resp_404.headers.get("content-type", "")
    assert "detail" in resp_404.json()


# ---------------------------------------------------------------------------
# Test G: Candidate Filename Generation Edge Cases
# ---------------------------------------------------------------------------
def test_candidate_filename_generation_edge_cases():
    assert generate_resume_filename("Alice") == "Alice_CV.pdf"
    assert generate_resume_filename("Alice Bob Charlie") == "Alice_Bob_Charlie_CV.pdf"
    assert generate_resume_filename("ALICE ARCHITECT") == "Alice_Architect_CV.pdf"
    assert generate_resume_filename("prosun banerjee") == "Prosun_Banerjee_CV.pdf"
    assert generate_resume_filename(None) == "Candidate_CV.pdf"
    assert generate_resume_filename("   ") == "Candidate_CV.pdf"
    assert generate_resume_filename("None") == "Candidate_CV.pdf"
    assert generate_resume_filename("null") == "Candidate_CV.pdf"
    assert generate_resume_filename("José-María O'Connor") == "José-María_OConnor_CV.pdf"
    assert generate_resume_filename("Prosun Banerjee", "docx") == "Prosun_Banerjee_CV.docx"
    assert generate_resume_filename("Prosun_Banerjee_CV", "pdf") == "Prosun_Banerjee_CV.pdf"

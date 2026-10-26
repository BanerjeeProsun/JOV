"""Comprehensive unit & integration tests for Milestone 12:
Application Planning, Portal Field Mapping, Manual Handoff Package (.zip) & State Transitions.
"""

from io import BytesIO
import json
import zipfile
import pytest
from fastapi.testclient import TestClient

from jovsi.domain.models import FactKind
from jovsi.domain.provenance import ProvenanceEngine
from jovsi.services.planning import ApplicationPlanningService, STANDARD_PORTAL_FIELDS
from jovsi.adapters.db.session import init_db
from jovsi.adapters.db.models import CandidateDB, JobDB, ResumeDB
from jovsi.api.main import app


@pytest.fixture
def candidate_facts():
    return [
        ProvenanceEngine.create_user_fact(
            candidate_id="c_plan_1",
            kind=FactKind.CONTACT,
            key="contact",
            value={
                "name": "Jordan Vance",
                "email": "jordan.vance@jov.si",
                "phone": "+14155558899",
                "location": "San Francisco, CA, US",
                "linkedin": "https://linkedin.com/in/jordanvance",
                "github": "https://github.com/jordanvance",
            },
        ),
        ProvenanceEngine.create_user_fact(
            candidate_id="c_plan_1",
            kind=FactKind.EXPERIENCE,
            key="exp1",
            value={"title": "Senior Systems Engineer", "duration_months": 36, "description": "High-scale distributed systems."},
        ),
        ProvenanceEngine.create_user_fact(
            candidate_id="c_plan_1",
            kind=FactKind.WORK_AUTH,
            key="work_auth_us",
            value={"authorized": True, "country": "US", "sponsorship_required": False},
        ),
    ]


# -------------------------------------------------------------------------
# 1. APPLICATION PLANNING FIELD MAPPING
# -------------------------------------------------------------------------

def test_plan_fields_from_facts(candidate_facts) -> None:
    """Verifies that facts map cleanly to standard portal form fields with zero hallucinations."""
    candidate = CandidateDB(id="c_plan_1", display_name="Jordan Vance")
    job = JobDB(
        id="j_plan_1",
        title_norm="Senior Infrastructure Engineer",
        company_norm="CloudFlare",
        canonical_url="https://boards.greenhouse.io/cloudflare/jobs/12345",
        raw_sha256="dummy_sha",
    )

    fields, has_unresolved = ApplicationPlanningService.plan_fields_from_facts(
        candidate=candidate,
        job=job,
        facts=candidate_facts,
    )

    assert has_unresolved is False
    field_map = {f["field_key"]: f for f in fields}

    assert field_map["full_name"]["value"] == "Jordan Vance"
    assert field_map["full_name"]["source"] == "FACT"
    assert field_map["email"]["value"] == "jordan.vance@jov.si"
    assert field_map["phone"]["value"] == "+14155558899"
    assert field_map["experience_years"]["value"] == "3"
    assert field_map["work_auth"]["value"] == "YES"
    assert field_map["sponsorship"]["value"] == "NO"
    assert field_map["linkedin_url"]["value"] == "https://linkedin.com/in/jordanvance"
    assert field_map["github_url"]["value"] == "https://github.com/jordanvance"
    assert field_map["legal_attestation"]["value"] == "agree"


def test_plan_fields_detects_unresolved_required_fields() -> None:
    """Verifies that missing required fields (e.g. no phone or email in facts) flag unresolved."""
    candidate = CandidateDB(id="c_empty", display_name="Empty Candidate")
    job = JobDB(
        id="j_empty",
        title_norm="Engineer",
        company_norm="Acme",
        canonical_url="https://example.com/jobs/1",
        raw_sha256="dummy_sha",
    )

    fields, has_unresolved = ApplicationPlanningService.plan_fields_from_facts(
        candidate=candidate,
        job=job,
        facts=[],
    )

    assert has_unresolved is True
    field_map = {f["field_key"]: f for f in fields}
    assert field_map["email"]["value"] == ""
    assert field_map["phone"]["value"] == ""


# -------------------------------------------------------------------------
# 2. APPLICATION HANDOFF PACKAGE (.ZIP) GENERATION
# -------------------------------------------------------------------------

def test_handoff_package_zip_generation(candidate_facts) -> None:
    """Verifies that build_handoff_package_zip generates a valid ZIP containing all artifacts."""
    from jovsi.adapters.db.models import FieldAnswerDB

    candidate = CandidateDB(id="c_zip", display_name="Jordan Vance")
    job = JobDB(
        id="j_zip",
        title_norm="Platform Engineer",
        company_norm="GitHub",
        canonical_url="https://github.com/careers/123",
        raw_sha256="sha256_mock",
    )

    resume_content = {
        "candidate_name": "Jordan Vance",
        "email": "jordan.vance@jov.si",
        "phone": "+14155558899",
        "cover_letter": "Dear GitHub,\n\nI am thrilled to apply for Platform Engineer.\n\nSincerely,\nJordan",
        "sections": [
            {
                "title": "Skills",
                "bullets": [{"text": "Python and Go", "fact_ids": ["f1"]}],
            }
        ],
    }
    resume_row = ResumeDB(
        id="res_zip_1",
        application_id="app_zip_1",
        version=1,
        content=resume_content,
        sha256="res_sha",
    )

    field_answers = [
        FieldAnswerDB(application_id="app_zip_1", field_key="full_name", value="Jordan Vance", source="FACT"),
        FieldAnswerDB(application_id="app_zip_1", field_key="email", value="jordan.vance@jov.si", source="FACT"),
        FieldAnswerDB(application_id="app_zip_1", field_key="experience_years", value="3", source="FACT"),
    ]

    zip_bytes = ApplicationPlanningService.build_handoff_package_zip(
        application_id="app_zip_1",
        job=job,
        candidate=candidate,
        resume_row=resume_row,
        field_answers=field_answers,
    )

    assert len(zip_bytes) > 1000

    # Unpack and verify contents
    with zipfile.ZipFile(BytesIO(zip_bytes), "r") as z:
        names = z.namelist()
        assert "README.txt" in names
        assert "resume-app_zip_.pdf" in names
        assert "resume-app_zip_.docx" in names
        assert "cover_letter.txt" in names
        assert "cover_letter.pdf" in names
        assert "cover_letter.docx" in names
        assert "field_answers.json" in names
        assert "application_cheat_sheet.txt" in names

        readme_content = z.read("README.txt").decode("utf-8")
        assert "GitHub" in readme_content
        assert "Platform Engineer" in readme_content

        answers_json = json.loads(z.read("field_answers.json").decode("utf-8"))
        assert answers_json["full_name"] == "Jordan Vance"
        assert answers_json["email"] == "jordan.vance@jov.si"


# -------------------------------------------------------------------------
# 3. FULL API VERTICAL SLICE
# -------------------------------------------------------------------------

def test_application_planning_and_handoff_api_vertical_slice() -> None:
    """Tests /plan, /fields, /package, /package.zip, and /mark-submitted-manual endpoints."""
    init_db()
    client = TestClient(app)

    user_email = f"handoff_test_{datetime_now_str()}@jov.si"
    reg_resp = client.post(
        "/api/v1/auth/register",
        json={"email": user_email, "password": "SecurePassword123!", "display_name": "Handoff Tester"},
    )
    assert reg_resp.status_code == 201

    cand_resp = client.get("/api/v1/candidates")
    candidate_id = cand_resp.json()[0]["id"]

    # Ingest candidate facts
    client.post(f"/api/v1/candidates/{candidate_id}/facts", json={
        "kind": "CONTACT", "key": "contact", "value": {"name": "Handoff Tester", "email": user_email, "phone": "+19997776666"}, "status": "ACTIVE", "provenance": "USER_VERIFIED"
    })
    client.post(f"/api/v1/candidates/{candidate_id}/facts", json={
        "kind": "SKILL", "key": "sk_python", "value": {"name": "Python"}, "status": "ACTIVE", "provenance": "USER_VERIFIED"
    })
    client.post(f"/api/v1/candidates/{candidate_id}/facts", json={
        "kind": "EXPERIENCE", "key": "exp_cloud", "value": {"title": "Cloud Architect", "description": "Built resilient multi-region infrastructure.", "duration_months": 36}, "status": "ACTIVE", "provenance": "USER_VERIFIED"
    })

    # Import Job
    job_resp = client.post("/api/v1/jobs/import", json={
        "title": "Cloud Engineer",
        "company_name": "Datadog",
        "source_url": f"https://datadoghq.com/careers/cloud-{int(datetime_now_str())}",
        "raw_description": "We are seeking a Cloud Engineer skilled in Python and infrastructure.",
        "target_locations": ["Remote, US"],
        "required_skills": ["Python"],
    })
    assert job_resp.status_code == 201
    job_id = job_resp.json()["id"]

    # Create application & evaluate & generate resume
    app_resp = client.post("/api/v1/applications", json={"candidate_id": candidate_id, "job_id": job_id})
    assert app_resp.status_code == 201
    app_id = app_resp.json()["id"]

    client.post(f"/api/v1/applications/{app_id}/evaluate")
    client.post(f"/api/v1/applications/{app_id}/generate-resume")

    # 1. POST /plan
    plan_resp = client.post(f"/api/v1/applications/{app_id}/plan")
    assert plan_resp.status_code == 200
    plan_data = plan_resp.json()
    assert plan_data["status"] == "planned"
    assert len(plan_data["fields"]) > 5

    # 2. GET /fields
    fields_resp = client.get(f"/api/v1/applications/{app_id}/fields")
    assert fields_resp.status_code == 200
    fields_data = fields_resp.json()
    assert len(fields_data["fields"]) > 5
    field_keys = [f["field_key"] for f in fields_data["fields"]]
    assert "full_name" in field_keys
    assert "email" in field_keys
    assert "experience_years" in field_keys

    # 3. PUT /fields
    put_resp = client.put(f"/api/v1/applications/{app_id}/fields", json={
        "fields": [
            {"field_key": "work_auth", "value": "YES"},
            {"field_key": "sponsorship", "value": "NO"},
        ]
    })
    assert put_resp.status_code == 200
    updated_fields = {f["field_key"]: f["value"] for f in put_resp.json()["fields"]}
    assert updated_fields["work_auth"] == "YES"
    assert updated_fields["sponsorship"] == "NO"

    # 4. GET /package manifest
    pkg_resp = client.get(f"/api/v1/applications/{app_id}/package")
    assert pkg_resp.status_code == 200
    pkg_data = pkg_resp.json()
    assert "package_hash" in pkg_data
    assert pkg_data["job"]["company_name"] == "Datadog"
    assert pkg_data["candidate"]["display_name"] == "Handoff Tester"

    # 5. GET /package.zip
    zip_resp = client.get(f"/api/v1/applications/{app_id}/package.zip")
    assert zip_resp.status_code == 200
    assert "application/zip" in zip_resp.headers["content-type"]
    assert len(zip_resp.content) > 1000

    # 6. POST /mark-submitted-manual
    manual_resp = client.post(f"/api/v1/applications/{app_id}/mark-submitted-manual")
    assert manual_resp.status_code == 200
    assert manual_resp.json()["status"] == "marked"
    assert manual_resp.json()["state"] == "MANUAL_HANDOFF"

    # Verify updated application state
    app_after = client.get(f"/api/v1/applications/{app_id}").json()
    assert app_after["state"] == "MANUAL_HANDOFF"


def datetime_now_str() -> str:
    import time
    return str(int(time.time() * 1000))

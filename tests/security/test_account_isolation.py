"""Two-Account Isolation Acceptance Tests for JOV.si.

Proves:
- User A and User B cannot view or manipulate each other's candidate profile.
- User B cannot view, confirm, edit, or delete User A's extracted facts.
- User B cannot upload a resume or download a document belonging to User A.
- User B cannot view, evaluate, approve, or submit User A's applications.
- User B cannot see User A's applications in GET /api/v1/applications.
- User B's metrics in GET /api/v1/metrics/summary are computed strictly from User B's records.
- Guessed foreign UUIDs return HTTP 403 Forbidden or 404 without leaking record details.
"""

import io
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from jovsi.api.main import app
from jovsi.adapters.db.session import init_db, get_db
from jovsi.services.auth import rate_limiter


@pytest.fixture
def isolated_env(tmp_path):
    rate_limiter.reset()
    db_file = tmp_path / "test_isolation.db"
    db_url = f"sqlite:///{db_file}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    init_db(engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestingSession
    app.dependency_overrides.clear()
    rate_limiter.reset()


def test_two_account_candidate_and_fact_isolation(isolated_env):
    # Client for User A (Alice)
    client_a = TestClient(app)
    resp_a = client_a.post(
        "/api/v1/auth/register",
        json={"email": "alice@example.com", "password": "AlicePassword123!", "display_name": "Alice Smith"},
    )
    assert resp_a.status_code == 201

    # Get Alice's candidate profile
    cands_a = client_a.get("/api/v1/candidates").json()
    assert len(cands_a) == 1
    alice_cand_id = cands_a[0]["id"]
    assert cands_a[0]["display_name"] == "Alice Smith"

    # Alice adds a private fact
    fact_resp_a = client_a.post(
        f"/api/v1/candidates/{alice_cand_id}/facts",
        json={"kind": "SKILL", "key": "python_secret", "value": {"name": "Python Cryptography", "level": "expert"}},
    )
    assert fact_resp_a.status_code == 201
    alice_fact_id = fact_resp_a.json()["id"]

    # Client for User B (Bob)
    client_b = TestClient(app)
    resp_b = client_b.post(
        "/api/v1/auth/register",
        json={"email": "bob@example.com", "password": "BobPassword123!", "display_name": "Bob Jones"},
    )
    assert resp_b.status_code == 201

    # Bob's candidate profile is separate and does not show Alice's profile
    cands_b = client_b.get("/api/v1/candidates").json()
    assert len(cands_b) == 1
    bob_cand_id = cands_b[0]["id"]
    assert bob_cand_id != alice_cand_id
    assert cands_b[0]["display_name"] == "Bob Jones"

    # Bob tries to view Alice's candidate profile directly by ID -> 403 Forbidden
    cross_cand = client_b.get(f"/api/v1/candidates/{alice_cand_id}")
    assert cross_cand.status_code == 403
    assert "access denied" in cross_cand.json()["detail"].lower()

    # Bob tries to view Alice's facts -> 403 Forbidden
    cross_facts = client_b.get(f"/api/v1/candidates/{alice_cand_id}/facts")
    assert cross_facts.status_code == 403

    # Bob tries to confirm Alice's fact -> 403 Forbidden
    cross_confirm = client_b.post(f"/api/v1/facts/{alice_fact_id}/confirm")
    assert cross_confirm.status_code == 403

    # Bob tries to update Alice's fact -> 403 Forbidden
    cross_update = client_b.put(f"/api/v1/facts/{alice_fact_id}", json={"value": {"hacked": True}})
    assert cross_update.status_code == 403

    # Bob tries to delete Alice's fact -> 403 Forbidden
    cross_delete = client_b.delete(f"/api/v1/facts/{alice_fact_id}")
    assert cross_delete.status_code == 403

    # Alice's fact remains intact
    alice_facts = client_a.get(f"/api/v1/candidates/{alice_cand_id}/facts").json()
    assert len(alice_facts) == 1
    assert alice_facts[0]["value"]["name"] == "Python Cryptography"


def test_two_account_resume_and_document_isolation(isolated_env):
    client_a = TestClient(app)
    client_a.post(
        "/api/v1/auth/register",
        json={"email": "alice_doc@example.com", "password": "Password123!", "display_name": "Alice Doc"},
    )
    alice_cand_id = client_a.get("/api/v1/candidates").json()[0]["id"]

    # Alice uploads resume
    resume_text = """
    Alice Doc
    alice_doc@example.com | +1 555-010-9999 | Austin, TX
    EXPERIENCE
    Lead Architect | Quantum Corp | 2020 - 2024
    Engineered quantum key distribution systems in Python.
    SKILLS
    Python, FastAPI, Docker
    """
    files = {"file": ("alice_resume.txt", io.BytesIO(resume_text.encode("utf-8")), "text/plain")}
    upload_resp = client_a.post(f"/api/v1/candidates/{alice_cand_id}/resume/upload", files=files)
    assert upload_resp.status_code == 201
    alice_doc_id = upload_resp.json()["document_id"]

    # Bob registers
    client_b = TestClient(app)
    client_b.post(
        "/api/v1/auth/register",
        json={"email": "bob_doc@example.com", "password": "Password123!", "display_name": "Bob Doc"},
    )
    bob_cand_id = client_b.get("/api/v1/candidates").json()[0]["id"]

    # Bob cannot inspect Alice's master resume status
    stat_b = client_b.get(f"/api/v1/candidates/{alice_cand_id}/master-resume")
    assert stat_b.status_code == 403

    # Bob cannot upload to Alice's candidate ID
    bob_file = {"file": ("bob_resume.txt", io.BytesIO(b"Bob resume content"), "text/plain")}
    cross_upload = client_b.post(f"/api/v1/candidates/{alice_cand_id}/resume/upload", files=bob_file)
    assert cross_upload.status_code == 403

    # Bob cannot download Alice's resume document
    cross_dl = client_b.get(f"/api/v1/documents/{alice_doc_id}/download")
    assert cross_dl.status_code == 403

    # Alice can download her own document
    own_dl = client_a.get(f"/api/v1/documents/{alice_doc_id}/download")
    assert own_dl.status_code == 200
    assert b"Quantum Corp" in own_dl.content


def test_two_account_application_pipeline_isolation(isolated_env):
    client_a = TestClient(app)
    client_a.post(
        "/api/v1/auth/register",
        json={"email": "alice_app@example.com", "password": "Password123!", "display_name": "Alice App"},
    )
    alice_cand_id = client_a.get("/api/v1/candidates").json()[0]["id"]

    # Import sample job
    job_resp = client_a.post(
        "/api/v1/jobs/import",
        json={
            "source": "manual",
            "source_url": "http://127.0.0.1:8765/jobs/iso-1/apply",
            "company_name": "Security Labs",
            "title": "Application Security Specialist",
            "raw_description": "AppSec role with Python and Docker.",
            "required_skills": ["Python"],
        },
    )
    assert job_resp.status_code == 201
    job_id = job_resp.json()["id"]

    # Alice creates application
    app_resp_a = client_a.post(
        "/api/v1/applications",
        json={"candidate_id": alice_cand_id, "job_id": job_id},
    )
    assert app_resp_a.status_code == 201
    alice_app_id = app_resp_a.json()["id"]

    # Bob registers
    client_b = TestClient(app)
    client_b.post(
        "/api/v1/auth/register",
        json={"email": "bob_app@example.com", "password": "Password123!", "display_name": "Bob App"},
    )

    # Bob checks applications list -> 0 applications
    b_apps = client_b.get("/api/v1/applications").json()
    assert len(b_apps) == 0

    # Bob tries to inspect Alice's application directly -> 403 Forbidden
    cross_app = client_b.get(f"/api/v1/applications/{alice_app_id}")
    assert cross_app.status_code == 403

    # Bob tries to evaluate Alice's application -> 403 Forbidden
    cross_eval = client_b.post(f"/api/v1/applications/{alice_app_id}/evaluate")
    assert cross_eval.status_code == 403

    # Bob tries to generate resume for Alice's application -> 403 Forbidden
    cross_gen = client_b.post(f"/api/v1/applications/{alice_app_id}/generate-resume")
    assert cross_gen.status_code == 403

    # Bob tries to run gate on Alice's application -> 403 Forbidden
    cross_gate = client_b.post(f"/api/v1/applications/{alice_app_id}/gate")
    assert cross_gate.status_code == 403

    # Bob tries to download Alice's resume PDF -> 403 Forbidden
    cross_res_pdf = client_b.get(f"/api/v1/applications/{alice_app_id}/resume/pdf")
    assert cross_res_pdf.status_code == 403

    # Bob tries to edit Alice's resume -> 403 Forbidden
    cross_res_edit = client_b.put(
        f"/api/v1/applications/{alice_app_id}/resume",
        json={"candidate_name": "Bob", "email": "bob@example.com", "phone": "123", "sections": []},
    )
    assert cross_res_edit.status_code == 403

    # Bob tries to download Alice's cover letter PDF -> 403 Forbidden
    cross_cl_pdf = client_b.get(f"/api/v1/applications/{alice_app_id}/cover-letter/pdf")
    assert cross_cl_pdf.status_code == 403

    # Bob tries to edit Alice's cover letter -> 403 Forbidden
    cross_cl_edit = client_b.put(f"/api/v1/applications/{alice_app_id}/cover-letter", json={"cover_letter": "hack"})
    assert cross_cl_edit.status_code == 403

    # Bob tries to download Alice's handoff package ZIP -> 403 Forbidden
    cross_pkg_zip = client_b.get(f"/api/v1/applications/{alice_app_id}/package.zip")
    assert cross_pkg_zip.status_code == 403

    # Bob tries to pause Alice's portal auth -> 403 Forbidden
    cross_pause = client_b.post(f"/api/v1/applications/{alice_app_id}/portal-auth/pause")
    assert cross_pause.status_code == 403

    # Bob tries to resume Alice's portal auth -> 403 Forbidden
    cross_resume = client_b.post(f"/api/v1/applications/{alice_app_id}/portal-auth/resume", json={})
    assert cross_resume.status_code == 403

    # Bob tries to approve Alice's application -> 403 Forbidden
    cross_appr = client_b.post(f"/api/v1/applications/{alice_app_id}/approve", json={"package_hash": "abc"})
    assert cross_appr.status_code == 403

    # Bob checks metrics -> all counts are 0 for Bob
    metrics_b = client_b.get("/api/v1/metrics/summary").json()
    assert metrics_b["discovered"] == 0
    assert metrics_b["confirmed"] == 0

    # Alice checks metrics -> discovered is 1
    metrics_a = client_a.get("/api/v1/metrics/summary").json()
    assert metrics_a["discovered"] == 1

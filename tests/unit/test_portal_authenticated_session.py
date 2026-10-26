"""Comprehensive unit & integration tests for Milestone 13:
External Portal Authenticated-Session Workflow, PAUSED_AUTH, Safe Credential Encryption & Anti-Tamper Re-Inspection.
"""

import pytest
from fastapi.testclient import TestClient

from jovsi.domain.models import FactKind
from jovsi.domain.provenance import ProvenanceEngine
from jovsi.domain.state_machine import ApplicationState
from jovsi.adapters.db.session import init_db
from jovsi.adapters.db.models import ApplicationDB, CandidateDB, FormSnapshotDB, JobDB
from jovsi.services.portal_auth import PortalAuthService
from jovsi.api.main import app


# -------------------------------------------------------------------------
# 1. ENCRYPTION HELPER FOR PORTAL CREDENTIALS / SESSIONS
# -------------------------------------------------------------------------

def test_portal_auth_cipher_encryption_and_decryption() -> None:
    """Verifies that portal secrets can be safely encrypted and decrypted without plaintext leakage."""
    secret = "SuperSecretPassword123!_OAuthToken"
    encrypted = PortalAuthService.encrypt_secret(secret, salt="custom_portal_salt")

    assert encrypted != secret
    assert "SuperSecretPassword123" not in encrypted
    assert len(encrypted) > len(secret)

    decrypted = PortalAuthService.decrypt_secret(encrypted, salt="custom_portal_salt")
    assert decrypted == secret


# -------------------------------------------------------------------------
# 2. STATE TRANSITIONS & PAUSED_AUTH LIFECYCLE
# -------------------------------------------------------------------------

def test_pause_and_resume_portal_authentication_lifecycle() -> None:
    """Verifies transition to PAUSED_AUTH, state preservation, event recording, and tamper-verified resumption."""
    init_db()
    from jovsi.adapters.db.session import SessionLocal
    import time

    uid = str(int(time.time() * 1000))
    cand_id = f"c_auth_{uid}"
    job_id = f"j_auth_{uid}"
    app_id = f"app_auth_{uid}"

    db = SessionLocal()
    try:
        # Setup application in READY_FOR_REVIEW
        candidate = CandidateDB(id=cand_id, display_name="Auth Tester")
        job = JobDB(
            id=job_id,
            source="MANUAL",
            source_url=f"https://okta.com/jobs/sec-{uid}",
            canonical_url=f"https://okta.com/jobs/sec-{uid}",
            canonical_job_key=f"key_okta_sec_{uid}",
            title_norm="Security Engineer",
            company_norm="Okta",
            description_clean="Clean security description",
            requirements={},
            raw_sha256="dummy_sha",
        )
        db.add_all([candidate, job])
        db.commit()

        app_row = ApplicationDB(
            id=app_id,
            candidate_id=candidate.id,
            job_id=job.id,
            canonical_job_key=f"key_okta_sec_{uid}",
            state=ApplicationState.READY_FOR_REVIEW.value,
            version=1,
        )
        db.add(app_row)
        db.commit()

        snapshot = FormSnapshotDB(
            application_id=app_row.id,
            url=job.canonical_url,
            fields=[{"field_key": "email", "required": True}],
            dom_hash="original_dom_hash_123",
        )
        db.add(snapshot)
        db.commit()

        # 1. Pause for authentication
        paused_app = PortalAuthService.pause_for_authentication(
            db=db,
            application_id=app_row.id,
            reason="SSO login wall encountered",
            actor="SYSTEM",
        )
        assert paused_app.state == ApplicationState.PAUSED_AUTH.value
        assert paused_app.paused_from_state == ApplicationState.READY_FOR_REVIEW.value
        assert paused_app.version == 2

        # 2. Resume with matching skeleton hash -> tamper_verified is True
        resumed_app, tamper_verified = PortalAuthService.resume_from_authentication(
            db=db,
            application_id=app_row.id,
            new_skeleton_hash="original_dom_hash_123",
            actor="CANDIDATE",
        )
        assert resumed_app.state == ApplicationState.READY_FOR_REVIEW.value
        assert resumed_app.paused_from_state is None
        assert resumed_app.version == 3
        assert tamper_verified is True

        # 3. Pause again and resume with altered skeleton hash -> tamper_verified is False
        PortalAuthService.pause_for_authentication(db=db, application_id=app_row.id)
        _, drift_detected = PortalAuthService.resume_from_authentication(
            db=db,
            application_id=app_row.id,
            new_skeleton_hash="drifted_dom_hash_999",
        )
        assert drift_detected is False

    finally:
        db.close()


# -------------------------------------------------------------------------
# 3. FULL API VERTICAL SLICE
# -------------------------------------------------------------------------

def test_portal_auth_api_vertical_slice() -> None:
    """Verifies /portal-auth/pause and /portal-auth/resume API endpoints."""
    init_db()
    client = TestClient(app)

    user_email = f"auth_flow_{datetime_now_str()}@jov.si"
    reg_resp = client.post(
        "/api/v1/auth/register",
        json={"email": user_email, "password": "SecurePassword123!", "display_name": "Auth Flow Tester"},
    )
    assert reg_resp.status_code == 201

    cand_resp = client.get("/api/v1/candidates")
    candidate_id = cand_resp.json()[0]["id"]

    # Ingest candidate facts
    client.post(f"/api/v1/candidates/{candidate_id}/facts", json={
        "kind": "CONTACT", "key": "contact", "value": {"name": "Auth Flow Tester", "email": user_email, "phone": "+19996665555"}, "status": "ACTIVE", "provenance": "USER_VERIFIED"
    })
    client.post(f"/api/v1/candidates/{candidate_id}/facts", json={
        "kind": "SKILL", "key": "sk_python", "value": {"name": "Python"}, "status": "ACTIVE", "provenance": "USER_VERIFIED"
    })

    # Import Job
    job_resp = client.post("/api/v1/jobs/import", json={
        "title": "Auth Engineer",
        "company_name": "Auth0",
        "source_url": f"https://auth0.com/careers/auth-{int(datetime_now_str())}",
        "raw_description": "We are seeking an Authentication Engineer skilled in Python.",
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

    # App state before pause
    app_before = client.get(f"/api/v1/applications/{app_id}").json()
    assert app_before["state"] == "RESUME_GENERATED"

    # 1. POST /portal-auth/pause
    pause_resp = client.post(f"/api/v1/applications/{app_id}/portal-auth/pause")
    assert pause_resp.status_code == 200
    pause_data = pause_resp.json()
    assert pause_data["status"] == "paused"
    assert pause_data["state"] == "PAUSED_AUTH"
    assert "auth0.com" in pause_data["login_url"]

    # Verify application reflects PAUSED_AUTH
    app_paused = client.get(f"/api/v1/applications/{app_id}").json()
    assert app_paused["state"] == "PAUSED_AUTH"

    # 2. POST /portal-auth/resume
    resume_resp = client.post(f"/api/v1/applications/{app_id}/portal-auth/resume", json={})
    assert resume_resp.status_code == 200
    resume_data = resume_resp.json()
    assert resume_data["status"] == "resumed"
    assert resume_data["state"] == "RESUME_GENERATED"

    # Verify application state restored
    app_resumed = client.get(f"/api/v1/applications/{app_id}").json()
    assert app_resumed["state"] == "RESUME_GENERATED"


def datetime_now_str() -> str:
    import time
    return str(int(time.time() * 1000))

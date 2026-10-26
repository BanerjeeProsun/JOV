"""Integration tests for Milestone 15: Dashboard Metrics, Display Name Greetings & Settings Isolation."""

import time
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from jovsi.api.main import app
from jovsi.adapters.db.session import SessionLocal
from jovsi.adapters.db.models import (
    ApplicationDB,
    CandidateDB,
    JobDB,
    UserDB,
    UserSettingsDB,
)
from jovsi.domain.state_machine import ApplicationState
from jovsi.services.auth import AuthService


def test_dashboard_metrics_and_settings_persistence_isolated():
    client = TestClient(app)
    db = SessionLocal()

    ts = int(time.time() * 1000)
    email_a = f"user_a_{ts}@example.com"
    email_b = f"user_b_{ts}@example.com"

    # 1. Register User A and User B
    user_a, _ = AuthService.register_user(db, email=email_a, password="Password123!", display_name="Alice Architect")
    user_b, _ = AuthService.register_user(db, email=email_b, password="Password123!", display_name="Bob Builder")

    candidate_a = CandidateDB(id=f"cand_a_{ts}", user_id=user_a.id, display_name="Alice Architect")
    candidate_b = CandidateDB(id=f"cand_b_{ts}", user_id=user_b.id, display_name="Bob Builder")
    db.add_all([candidate_a, candidate_b])
    db.commit()

    # 2. Login as User A
    login_a = client.post("/api/v1/auth/login", json={"email": email_a, "password": "Password123!"})
    assert login_a.status_code == 200

    # 3. Check display name greeting contract
    me_a = client.get("/api/v1/auth/me")
    assert me_a.status_code == 200
    assert me_a.json()["display_name"] == "Alice Architect"

    # 4. Check initial metrics for User A (zero baseline, no synthetic entries)
    metrics_a = client.get("/api/v1/metrics/summary")
    assert metrics_a.status_code == 200
    m_data = metrics_a.json()
    assert m_data["discovered"] == 0
    assert m_data["confirmed"] == 0
    assert m_data["ready_for_review"] == 0
    assert m_data["autonomy_level"] == "L0_DRY_RUN"

    # 5. Check and update settings for User A
    settings_a_init = client.get("/api/v1/settings")
    assert settings_a_init.status_code == 200

    patch_a = client.patch(
        "/api/v1/settings",
        json={
            "suitability_floor": 80,
            "daily_cap_global": 15,
            "daily_cap_per_portal": 6,
            "daily_cap_per_company": 2,
            "timezone": "America/New_York",
            "autonomy_level": "L1_MOCK_SUPERVISED",
        },
    )
    assert patch_a.status_code == 200
    saved_a = patch_a.json()
    assert saved_a["suitability_floor"] == 80
    assert saved_a["daily_cap_global"] == 15
    assert saved_a["daily_cap_per_portal"] == 6
    assert saved_a["daily_cap_per_company"] == 2
    assert saved_a["timezone"] == "America/New_York"
    assert saved_a["autonomy_level"] == "L1_MOCK_SUPERVISED"

    # Verify metrics reflects updated autonomy level
    metrics_a_updated = client.get("/api/v1/metrics/summary")
    assert metrics_a_updated.json()["autonomy_level"] == "L1_MOCK_SUPERVISED"

    # 6. Switch session to User B
    login_b = client.post("/api/v1/auth/login", json={"email": email_b, "password": "Password123!"})
    assert login_b.status_code == 200

    # 7. Verify User B has separate identity and defaults (isolation)
    me_b = client.get("/api/v1/auth/me")
    assert me_b.status_code == 200
    assert me_b.json()["display_name"] == "Bob Builder"

    settings_b = client.get("/api/v1/settings")
    assert settings_b.status_code == 200
    b_data = settings_b.json()
    # User B should have default settings, NOT User A's updated values
    assert b_data["suitability_floor"] != 80 or b_data["timezone"] != "America/New_York"
    assert b_data["autonomy_level"] == "L0_DRY_RUN"

    # 8. Update User A's profile display name
    # Switch back to User A
    login_a2 = client.post("/api/v1/auth/login", json={"email": email_a, "password": "Password123!"})
    assert login_a2.status_code == 200

    prof_patch = client.patch("/api/v1/auth/profile", json={"display_name": "Alice A. Turing"})
    assert prof_patch.status_code == 200
    assert prof_patch.json()["display_name"] == "Alice A. Turing"

    me_updated = client.get("/api/v1/auth/me")
    assert me_updated.json()["display_name"] == "Alice A. Turing"

    db.close()

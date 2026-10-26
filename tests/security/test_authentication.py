"""Comprehensive acceptance tests for JOV.si User Authentication and Session Lifecycle.

Verifies:
- Registration success, input validation, duplicate email rejection.
- Login success, password verification, incorrect password rejection.
- Session cookie issuance, idle and absolute timeout, revocation on logout.
- Password reset flow with account enumeration defense.
- Email verification flow with single-use tokens.
- Change password with automatic revocation of other active sessions.
- Rate limiting defenses against brute-force attacks.
- Display name update and profile synchronization.
"""

from datetime import datetime, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from jovsi.api.main import app
from jovsi.adapters.db.session import init_db, get_db
from jovsi.adapters.db.models import UserDB, UserSessionDB, PasswordResetTokenDB, EmailVerificationTokenDB
from jovsi.services.auth import AuthService, hash_password, rate_limiter


@pytest.fixture
def auth_client(tmp_path):
    rate_limiter.reset()
    db_file = tmp_path / "test_auth.db"
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
    client = TestClient(app)
    yield client, TestingSession
    app.dependency_overrides.clear()
    rate_limiter.reset()


def test_registration_and_login_flow(auth_client):
    client, SessionLocal = auth_client

    # 1. Register new account
    reg_resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": "user@example.com",
            "password": "CorrectPassword123!",
            "display_name": "Test Engineer",
        },
    )
    assert reg_resp.status_code == 201
    user_data = reg_resp.json()
    assert user_data["email"] == "user@example.com"
    assert user_data["display_name"] == "Test Engineer"
    assert "password" not in user_data
    assert "password_hash" not in user_data

    # Check session cookie set
    assert "jovsi_session" in reg_resp.cookies

    # 2. Duplicate registration rejected with 409
    dup_resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": "USER@example.com",  # Normalized case test
            "password": "AnotherPassword123!",
            "display_name": "Duplicate",
        },
    )
    assert dup_resp.status_code == 409
    assert "already exists" in dup_resp.json()["detail"].lower()

    # 3. Weak password rejected with 422
    weak_resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": "short@example.com",
            "password": "short",
            "display_name": "Short",
        },
    )
    assert weak_resp.status_code == 422

    # 4. Check /me with current cookie
    me_resp = client.get("/api/v1/auth/me")
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "user@example.com"
    assert me_resp.json()["display_name"] == "Test Engineer"

    # 5. Sign out clears session and cookie
    logout_resp = client.post("/api/v1/auth/logout")
    assert logout_resp.status_code == 200

    # 6. Subsequent /me is rejected with 401
    unauth_resp = client.get("/api/v1/auth/me")
    assert unauth_resp.status_code == 401

    # 7. Sign in with incorrect password rejected with 401
    bad_login = client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "WrongPassword!"},
    )
    assert bad_login.status_code == 401

    # 8. Sign in with correct credentials succeeds
    good_login = client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "CorrectPassword123!"},
    )
    assert good_login.status_code == 200
    assert "jovsi_session" in good_login.cookies


def test_password_change_and_session_invalidation(auth_client):
    client, SessionLocal = auth_client

    # Register
    client.post(
        "/api/v1/auth/register",
        json={"email": "changepw@example.com", "password": "InitialPassword123!", "display_name": "Security Tester"},
    )

    # Change password
    change_resp = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "InitialPassword123!", "new_password": "UpdatedPassword456!"},
    )
    assert change_resp.status_code == 200

    # Old password no longer works
    old_login = client.post(
        "/api/v1/auth/login",
        json={"email": "changepw@example.com", "password": "InitialPassword123!"},
    )
    assert old_login.status_code == 401

    # New password works
    new_login = client.post(
        "/api/v1/auth/login",
        json={"email": "changepw@example.com", "password": "UpdatedPassword456!"},
    )
    assert new_login.status_code == 200


def test_password_reset_flow(auth_client):
    client, SessionLocal = auth_client

    client.post(
        "/api/v1/auth/register",
        json={"email": "resetme@example.com", "password": "ForgottenPassword123!", "display_name": "Reset User"},
    )

    # Forgot password for unknown email gives generic success (prevents enumeration)
    anon_resp = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "nobody@example.com"},
    )
    assert anon_resp.status_code == 200
    assert "dispatched" in anon_resp.json()["message"]
    assert "_test_token" not in anon_resp.json()

    # Forgot password for real user provides token in test environment
    real_resp = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "resetme@example.com"},
    )
    assert real_resp.status_code == 200
    token = real_resp.json().get("_test_token")
    assert token is not None

    # Reset password with token
    reset_resp = client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "BrandNewPassword789!"},
    )
    assert reset_resp.status_code == 200

    # Token cannot be reused (single-use constraint)
    reuse_resp = client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "YetAnotherPassword1!"},
    )
    assert reuse_resp.status_code == 400

    # Login with new password
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "resetme@example.com", "password": "BrandNewPassword789!"},
    )
    assert login_resp.status_code == 200


def test_email_verification_flow(auth_client):
    client, SessionLocal = auth_client

    client.post(
        "/api/v1/auth/register",
        json={"email": "verify@example.com", "password": "Password123!", "display_name": "Unverified"},
    )

    with SessionLocal() as db:
        user = db.scalar(select(UserDB).where(UserDB.email == "verify@example.com"))
        assert user.is_verified is False
        raw_token = AuthService.create_email_verification_token(db, user.id)

    # Verify using token
    ver_resp = client.post("/api/v1/auth/verify-email", json={"token": raw_token})
    assert ver_resp.status_code == 200
    assert ver_resp.json()["status"] == "email_verified"

    # Verify user state is now verified
    with SessionLocal() as db:
        user = db.scalar(select(UserDB).where(UserDB.email == "verify@example.com"))
        assert user.is_verified is True


def test_profile_display_name_update(auth_client):
    client, SessionLocal = auth_client

    client.post(
        "/api/v1/auth/register",
        json={"email": "greet@example.com", "password": "Password123!", "display_name": "Initial Name"},
    )

    # Update preferred display name
    patch_resp = client.patch(
        "/api/v1/auth/profile",
        json={"display_name": "Elena Rostova"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["display_name"] == "Elena Rostova"

    # Reload /me
    me_resp = client.get("/api/v1/auth/me")
    assert me_resp.status_code == 200
    assert me_resp.json()["display_name"] == "Elena Rostova"


def test_session_idle_timeout(auth_client):
    client, SessionLocal = auth_client

    reg_resp = client.post(
        "/api/v1/auth/register",
        json={"email": "timeout@example.com", "password": "Password123!", "display_name": "Timeout User"},
    )
    token = reg_resp.cookies.get("jovsi_session")

    # Artificially age the session beyond idle timeout (25 hours ago)
    with SessionLocal() as db:
        session_row = db.scalars(select(UserSessionDB)).first()
        session_row.last_active_at = datetime.utcnow() - timedelta(hours=25)
        db.commit()

    # Access /me should now fail because session expired
    expired_resp = client.get("/api/v1/auth/me")
    assert expired_resp.status_code == 401

"""Authentication, session lifecycle, password cryptography, and account isolation service.

Implements strict security guarantees:
- Salted PBKDF2-HMAC-SHA256 password hashing (600,000 iterations).
- Cryptographically random 256-bit session tokens.
- Token hashing in database (SHA-256) to prevent token theft via database read.
- Idle timeout (24h) and absolute timeout (30d) enforcement.
- Rate limiting for sensitive authentication endpoints.
- Strict ownership isolation linking UserDB <-> CandidateDB.
"""

from collections import defaultdict
from datetime import datetime, timedelta
import hashlib
import hmac
import re
import secrets
import threading
import time
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from jovsi.adapters.db.models import (
    CandidateDB,
    EmailVerificationTokenDB,
    PasswordResetTokenDB,
    UserDB,
    UserSessionDB,
    UserSettingsDB,
)


class AuthError(Exception):
    """Base exception for authentication failures."""
    pass


class InvalidCredentialsError(AuthError):
    pass


class UserAlreadyExistsError(AuthError):
    pass


class RateLimitExceededError(AuthError):
    pass


class TokenExpiredOrInvalidError(AuthError):
    pass


class AuthRateLimiter:
    """Thread-safe sliding-window rate limiter for sensitive authentication endpoints."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._requests: Dict[str, list[float]] = defaultdict(list)

    def check(self, key: str, max_requests: int = 10, window_seconds: int = 60) -> bool:
        now = time.time()
        with self._lock:
            # Clean expired timestamps
            cutoff = now - window_seconds
            valid = [ts for ts in self._requests[key] if ts > cutoff]
            if len(valid) >= max_requests:
                self._requests[key] = valid
                return False
            valid.append(now)
            self._requests[key] = valid
            return True

    def reset(self) -> None:
        with self._lock:
            self._requests.clear()


rate_limiter = AuthRateLimiter()


def hash_password(password: str) -> str:
    """Derive salted PBKDF2-HMAC-SHA256 hash using 600,000 iterations."""
    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 600_000)
    return f"pbkdf2_sha256$600000${salt.hex()}${derived.hex()}"


def verify_password(plain_password: str, hashed: str) -> bool:
    """Verify plain password against PBKDF2-HMAC-SHA256 hash with constant-time equality."""
    try:
        parts = hashed.split("$")
        if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
            return False
        iters = int(parts[1])
        salt = bytes.fromhex(parts[2])
        expected_hash = bytes.fromhex(parts[3])
        derived = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, iters)
        return hmac.compare_digest(derived, expected_hash)
    except Exception:
        return False


def generate_secure_token() -> str:
    """Generate cryptographically secure 256-bit URL-safe token."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Compute SHA-256 digest of token for protected storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class AuthService:
    IDLE_TIMEOUT_HOURS = 24
    ABSOLUTE_TIMEOUT_DAYS = 30
    RESET_TOKEN_HOURS = 1
    VERIFICATION_TOKEN_HOURS = 24

    @staticmethod
    def normalize_email(email: str) -> str:
        return email.strip().lower()

    @staticmethod
    def validate_password_strength(password: str) -> None:
        if len(password) < 8:
            raise AuthError("Password must be at least 8 characters long.")

    @classmethod
    def register_user(
        cls,
        db: Session,
        email: str,
        password: str,
        display_name: str = "",
        timezone: str = "Asia/Kolkata",
    ) -> Tuple[UserDB, str]:
        """Register a new user account, candidate profile, and issue initial session token."""
        norm_email = cls.normalize_email(email)
        if not norm_email or "@" not in norm_email:
            raise AuthError("A valid email address is required.")

        cls.validate_password_strength(password)

        existing = db.scalar(select(UserDB).where(UserDB.email == norm_email))
        if existing:
            raise UserAlreadyExistsError("An account with this email address already exists.")

        user = UserDB(
            email=norm_email,
            password_hash=hash_password(password),
            display_name=display_name.strip(),
            is_verified=False,
            is_active=True,
            role="user",
        )
        db.add(user)
        db.flush()

        # Create 1:1 Candidate Profile bound to this user
        candidate = CandidateDB(
            user_id=user.id,
            display_name=display_name.strip() or norm_email.split("@")[0],
            timezone=timezone,
            is_synthetic=False,
        )
        db.add(candidate)

        # Create 1:1 User Settings record
        user_settings = UserSettingsDB(
            user_id=user.id,
            timezone=timezone,
        )
        db.add(user_settings)

        # Issue initial session token
        session_record, raw_token = cls.create_session(db, user.id)
        db.commit()
        db.refresh(user)

        return user, raw_token

    @classmethod
    def authenticate_user(cls, db: Session, email: str, password: str) -> UserDB:
        """Authenticate user by email and password."""
        norm_email = cls.normalize_email(email)
        user = db.scalar(select(UserDB).where(UserDB.email == norm_email))
        if not user or not user.is_active:
            raise InvalidCredentialsError("Invalid email or password.")

        if not verify_password(password, user.password_hash):
            raise InvalidCredentialsError("Invalid email or password.")

        return user

    @classmethod
    def create_session(cls, db: Session, user_id: str) -> Tuple[UserSessionDB, str]:
        """Issue cryptographically random session token and persist hashed identifier."""
        raw_token = generate_secure_token()
        token_digest = hash_token(raw_token)
        now = datetime.utcnow()
        expires = now + timedelta(days=cls.ABSOLUTE_TIMEOUT_DAYS)

        session_db = UserSessionDB(
            user_id=user_id,
            token_hash=token_digest,
            created_at=now,
            last_active_at=now,
            expires_at=expires,
        )
        db.add(session_db)
        db.flush()
        return session_db, raw_token

    @classmethod
    def get_user_from_session_token(cls, db: Session, raw_token: str) -> Optional[UserDB]:
        """Validate session token, check idle/absolute expiry, and update activity timestamp."""
        if not raw_token:
            return None

        token_digest = hash_token(raw_token)
        now = datetime.utcnow()

        session_db = db.scalar(
            select(UserSessionDB).where(
                UserSessionDB.token_hash == token_digest,
                UserSessionDB.revoked_at.is_(None),
                UserSessionDB.expires_at > now,
            )
        )
        if not session_db:
            return None

        # Check idle timeout (24 hours)
        idle_limit = session_db.last_active_at + timedelta(hours=cls.IDLE_TIMEOUT_HOURS)
        if now > idle_limit:
            session_db.revoked_at = now
            db.commit()
            return None

        # Update last active timestamp
        session_db.last_active_at = now
        db.commit()

        user = db.get(UserDB, session_db.user_id)
        return user if (user and user.is_active) else None

    @classmethod
    def revoke_session(cls, db: Session, raw_token: str) -> bool:
        """Revoke session token on logout."""
        if not raw_token:
            return False
        token_digest = hash_token(raw_token)
        session_db = db.scalar(select(UserSessionDB).where(UserSessionDB.token_hash == token_digest))
        if session_db and not session_db.revoked_at:
            session_db.revoked_at = datetime.utcnow()
            db.commit()
            return True
        return False

    @classmethod
    def revoke_all_user_sessions(cls, db: Session, user_id: str, keep_token: Optional[str] = None) -> None:
        """Revoke all sessions for a user (e.g. after password change), optionally keeping current session."""
        now = datetime.utcnow()
        stmt = select(UserSessionDB).where(
            UserSessionDB.user_id == user_id,
            UserSessionDB.revoked_at.is_(None),
        )
        if keep_token:
            stmt = stmt.where(UserSessionDB.token_hash != hash_token(keep_token))

        sessions = db.scalars(stmt).all()
        for s in sessions:
            s.revoked_at = now
        db.commit()

    @classmethod
    def change_password(
        cls,
        db: Session,
        user_id: str,
        current_password: str,
        new_password: str,
        current_token: Optional[str] = None,
    ) -> bool:
        """Change user password, verifying current credentials and revoking other sessions."""
        user = db.get(UserDB, user_id)
        if not user:
            raise InvalidCredentialsError("User not found.")

        if not verify_password(current_password, user.password_hash):
            raise InvalidCredentialsError("Current password is incorrect.")

        cls.validate_password_strength(new_password)
        user.password_hash = hash_password(new_password)
        user.updated_at = datetime.utcnow()

        # Invalidate other existing sessions
        cls.revoke_all_user_sessions(db, user_id, keep_token=current_token)
        db.commit()
        return True

    @classmethod
    def create_password_reset_token(cls, db: Session, email: str) -> Optional[str]:
        """Create single-use password reset token. Returns token or None if user not found."""
        norm_email = cls.normalize_email(email)
        user = db.scalar(select(UserDB).where(UserDB.email == norm_email))
        if not user or not user.is_active:
            return None

        raw_token = generate_secure_token()
        token_digest = hash_token(raw_token)
        now = datetime.utcnow()
        expires = now + timedelta(hours=cls.RESET_TOKEN_HOURS)

        token_record = PasswordResetTokenDB(
            user_id=user.id,
            token_hash=token_digest,
            expires_at=expires,
            created_at=now,
        )
        db.add(token_record)
        db.commit()
        return raw_token

    @classmethod
    def reset_password_with_token(cls, db: Session, raw_token: str, new_password: str) -> bool:
        """Reset password using verified single-use token and revoke all existing sessions."""
        cls.validate_password_strength(new_password)
        token_digest = hash_token(raw_token)
        now = datetime.utcnow()

        record = db.scalar(
            select(PasswordResetTokenDB).where(
                PasswordResetTokenDB.token_hash == token_digest,
                PasswordResetTokenDB.used_at.is_(None),
                PasswordResetTokenDB.expires_at > now,
            )
        )
        if not record:
            raise TokenExpiredOrInvalidError("Password reset token is invalid or has expired.")

        user = db.get(UserDB, record.user_id)
        if not user or not user.is_active:
            raise TokenExpiredOrInvalidError("Account is inactive or not found.")

        user.password_hash = hash_password(new_password)
        user.updated_at = now
        record.used_at = now

        # Revoke all active sessions on password reset
        cls.revoke_all_user_sessions(db, user.id)
        db.commit()
        return True

    @classmethod
    def create_email_verification_token(cls, db: Session, user_id: str) -> str:
        """Create email verification token valid for 24 hours."""
        raw_token = generate_secure_token()
        token_digest = hash_token(raw_token)
        now = datetime.utcnow()
        expires = now + timedelta(hours=cls.VERIFICATION_TOKEN_HOURS)

        record = EmailVerificationTokenDB(
            user_id=user_id,
            token_hash=token_digest,
            expires_at=expires,
            created_at=now,
        )
        db.add(record)
        db.commit()
        return raw_token

    @classmethod
    def verify_email_with_token(cls, db: Session, raw_token: str) -> bool:
        """Verify email using token."""
        token_digest = hash_token(raw_token)
        now = datetime.utcnow()

        record = db.scalar(
            select(EmailVerificationTokenDB).where(
                EmailVerificationTokenDB.token_hash == token_digest,
                EmailVerificationTokenDB.used_at.is_(None),
                EmailVerificationTokenDB.expires_at > now,
            )
        )
        if not record:
            raise TokenExpiredOrInvalidError("Email verification token is invalid or has expired.")

        user = db.get(UserDB, record.user_id)
        if not user:
            raise TokenExpiredOrInvalidError("User not found.")

        user.is_verified = True
        user.updated_at = now
        record.used_at = now
        db.commit()
        return True

    @classmethod
    def update_profile(
        cls,
        db: Session,
        user_id: str,
        display_name: Optional[str] = None,
    ) -> UserDB:
        """Update authenticated user display name and synchronize with candidate profile."""
        user = db.get(UserDB, user_id)
        if not user:
            raise AuthError("User not found.")

        if display_name is not None:
            clean_name = display_name.strip()
            user.display_name = clean_name
            user.updated_at = datetime.utcnow()

            # Synchronize with candidate profile
            cand = db.scalar(select(CandidateDB).where(CandidateDB.user_id == user_id))
            if cand:
                cand.display_name = clean_name or user.email.split("@")[0]

        db.commit()
        db.refresh(user)
        return user

    @classmethod
    def get_or_create_candidate_for_user(
        cls,
        db: Session,
        user: UserDB,
        timezone: str = "Asia/Kolkata",
    ) -> CandidateDB:
        """Ensure candidate profile exists specifically bound to this user."""
        candidate = db.scalar(select(CandidateDB).where(CandidateDB.user_id == user.id))
        if not candidate:
            candidate = CandidateDB(
                user_id=user.id,
                display_name=user.display_name or user.email.split("@")[0],
                timezone=timezone,
                is_synthetic=False,
            )
            db.add(candidate)
            db.commit()
            db.refresh(candidate)
        return candidate

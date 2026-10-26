"""FastAPI dependencies for authentication, database sessions, and user context."""

from typing import Optional
from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from jovsi.adapters.db.models import UserDB
from jovsi.adapters.db.session import get_db
from jovsi.services.auth import AuthService


def get_session_token_from_request(
    request: Request,
    authorization: Optional[str] = Header(None),
    jovsi_session: Optional[str] = Cookie(None),
) -> Optional[str]:
    """Extract session token from Authorization header (Bearer) or jovsi_session cookie."""
    if authorization and authorization.startswith("Bearer "):
        return authorization[7:].strip()
    return jovsi_session


def get_current_user(
    token: Optional[str] = Depends(get_session_token_from_request),
    db: Session = Depends(get_db),
) -> UserDB:
    """Enforce strict server-side authentication. Raises HTTP 401 if token is missing, invalid, or expired."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please sign in.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = AuthService.get_user_from_session_token(db, token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has expired or is invalid. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive or disabled.",
        )

    return user


def get_optional_current_user(
    token: Optional[str] = Depends(get_session_token_from_request),
    db: Session = Depends(get_db),
) -> Optional[UserDB]:
    """Retrieve current authenticated user if valid session exists, otherwise return None."""
    if not token:
        return None
    return AuthService.get_user_from_session_token(db, token)

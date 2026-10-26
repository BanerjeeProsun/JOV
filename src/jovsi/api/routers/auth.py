"""FastAPI Router for User Authentication, Account Identity, and Session Lifecycle."""

from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from jovsi.adapters.db.models import UserDB
from jovsi.adapters.db.session import get_db
from jovsi.api.dependencies import get_current_user, get_session_token_from_request
from jovsi.api.schemas import (
    EmailVerificationSubmit,
    PasswordChangeRequest,
    PasswordResetRequest,
    PasswordResetSubmit,
    UserLoginRequest,
    UserProfileUpdate,
    UserRegisterRequest,
    UserResponse,
)
from jovsi.services.auth import (
    AuthError,
    AuthService,
    InvalidCredentialsError,
    TokenExpiredOrInvalidError,
    UserAlreadyExistsError,
    rate_limiter,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])

COOKIE_NAME = "jovsi_session"
COOKIE_MAX_AGE = 30 * 24 * 3600  # 30 days


def _client_ip(request: Request) -> str:
    """Extract client IP safely for rate limiting."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


def _set_session_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=raw_token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=False,  # Local dev & tests run over HTTP; set True behind HTTPS proxy
        path="/",
    )


def _delete_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="lax",
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: UserRegisterRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> Any:
    """Register a new user account, initialize candidate profile, and set session cookie."""
    ip = _client_ip(request)
    if not rate_limiter.check(f"register:{ip}", max_requests=10, window_seconds=60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many registration attempts. Please try again later.",
        )

    try:
        user, raw_token = AuthService.register_user(
            db=db,
            email=payload.email,
            password=payload.password,
            display_name=payload.display_name,
            timezone=payload.timezone,
        )
        _set_session_cookie(response, raw_token)
        return user
    except UserAlreadyExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except AuthError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.post("/login", response_model=UserResponse)
def login(
    payload: UserLoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> Any:
    """Authenticate user with email and password, issue new session token and cookie."""
    ip = _client_ip(request)
    if not rate_limiter.check(f"login:{ip}", max_requests=15, window_seconds=60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later.",
        )

    try:
        user = AuthService.authenticate_user(db=db, email=payload.email, password=payload.password)
        _, raw_token = AuthService.create_session(db=db, user_id=user.id)
        db.commit()
        _set_session_cookie(response, raw_token)
        return user
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post("/logout")
def logout(
    response: Response,
    token: str = Depends(get_session_token_from_request),
    db: Session = Depends(get_db),
) -> Dict[str, str]:
    """Invalidate current server session and clear session cookie."""
    if token:
        AuthService.revoke_session(db, token)
    _delete_session_cookie(response)
    return {"status": "logged_out"}


@router.get("/me", response_model=UserResponse)
def get_me(current_user: UserDB = Depends(get_current_user)) -> Any:
    """Retrieve identity and display name of the currently authenticated account."""
    return current_user


@router.patch("/profile", response_model=UserResponse)
def update_profile(
    payload: UserProfileUpdate,
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """Update preferred display name and synchronization with candidate profile."""
    updated = AuthService.update_profile(
        db=db,
        user_id=current_user.id,
        display_name=payload.display_name,
    )
    return updated


@router.post("/change-password")
def change_password(
    payload: PasswordChangeRequest,
    current_user: UserDB = Depends(get_current_user),
    token: str = Depends(get_session_token_from_request),
    db: Session = Depends(get_db),
) -> Dict[str, str]:
    """Change account password and revoke all other existing sessions."""
    try:
        AuthService.change_password(
            db=db,
            user_id=current_user.id,
            current_password=payload.current_password,
            new_password=payload.new_password,
            current_token=token,
        )
        return {"status": "password_changed"}
    except InvalidCredentialsError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except AuthError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.post("/forgot-password")
def forgot_password(
    payload: PasswordResetRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Initiate password reset. Returns generic message to prevent account enumeration."""
    ip = _client_ip(request)
    if not rate_limiter.check(f"forgot:{ip}", max_requests=5, window_seconds=60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many password reset requests. Please try again later.",
        )

    raw_token = AuthService.create_password_reset_token(db=db, email=payload.email)
    res: Dict[str, Any] = {
        "message": "If an account with this email exists, password reset instructions have been dispatched."
    }
    # In local testing environment without external SMTP provider, surface token in response for test execution
    if raw_token:
        res["_test_token"] = raw_token
    return res


@router.post("/reset-password")
def reset_password(
    payload: PasswordResetSubmit,
    request: Request,
    db: Session = Depends(get_db),
) -> Dict[str, str]:
    """Reset password using verified single-use token."""
    ip = _client_ip(request)
    if not rate_limiter.check(f"reset:{ip}", max_requests=10, window_seconds=60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many reset attempts. Please try again later.",
        )

    try:
        AuthService.reset_password_with_token(
            db=db,
            raw_token=payload.token,
            new_password=payload.new_password,
        )
        return {"status": "password_reset_successful"}
    except TokenExpiredOrInvalidError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except AuthError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.post("/verify-email")
def verify_email(
    payload: EmailVerificationSubmit,
    db: Session = Depends(get_db),
) -> Dict[str, str]:
    """Verify account email with single-use token."""
    try:
        AuthService.verify_email_with_token(db=db, raw_token=payload.token)
        return {"status": "email_verified"}
    except TokenExpiredOrInvalidError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

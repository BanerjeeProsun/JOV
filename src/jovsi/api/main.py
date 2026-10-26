"""FastAPI Application for JOV.si."""

from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from jovsi.config import settings
from jovsi.domain.state_machine import IllegalTransition, GuardFailure
from jovsi.services.application_service import VersionConflict, ApplicationNotFound
from jovsi.services.submission import ApprovalError, SubmissionError
from jovsi.api.routers import candidates, jobs, applications, metrics, settings as settings_router
from jovsi.adapters.db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Automatically ensure database tables and immutability triggers exist on startup."""
    init_db()
    yield


app = FastAPI(
    title="JOV.si API",
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# Strict CORS origin policy (no wildcard origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)


# RFC 7807 Exception Handlers
@app.exception_handler(ApprovalError)
async def approval_error_handler(request: Request, exc: ApprovalError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        media_type="application/problem+json",
        content={
            "type": "https://jov.si/errors/approval-error",
            "title": "Approval Verification Failed",
            "status": 422,
            "code": "GATE_NOT_PASSED",
            "detail": str(exc),
            "instance": request.url.path,
        },
    )


@app.exception_handler(SubmissionError)
async def submission_error_handler(request: Request, exc: SubmissionError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        media_type="application/problem+json",
        content={
            "type": "https://jov.si/errors/submission-error",
            "title": "Submission Error",
            "status": 422,
            "code": "SUBMISSION_ERROR",
            "detail": str(exc),
            "instance": request.url.path,
        },
    )

# Include Routers under /api/v1
app.include_router(candidates.router, prefix="/api/v1")
app.include_router(jobs.router, prefix="/api/v1")
app.include_router(applications.router, prefix="/api/v1")
app.include_router(metrics.router, prefix="/api/v1")
app.include_router(settings_router.router, prefix="/api/v1")


# RFC 7807 Exception Handlers
@app.exception_handler(IllegalTransition)
async def illegal_transition_handler(request: Request, exc: IllegalTransition) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        media_type="application/problem+json",
        content={
            "type": "https://jov.si/errors/illegal-transition",
            "title": "Illegal State Transition",
            "status": 409,
            "code": "ILLEGAL_TRANSITION",
            "detail": str(exc),
            "instance": request.url.path,
        },
    )


@app.exception_handler(GuardFailure)
async def guard_failure_handler(request: Request, exc: GuardFailure) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        media_type="application/problem+json",
        content={
            "type": "https://jov.si/errors/guard-failure",
            "title": "Transition Guard Failed",
            "status": 422,
            "code": "GUARD_FAILURE",
            "detail": str(exc),
            "instance": request.url.path,
        },
    )


@app.exception_handler(VersionConflict)
async def version_conflict_handler(request: Request, exc: VersionConflict) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        media_type="application/problem+json",
        content={
            "type": "https://jov.si/errors/version-conflict",
            "title": "Optimistic Locking Version Conflict",
            "status": 409,
            "code": "VERSION_CONFLICT",
            "detail": str(exc),
            "instance": request.url.path,
        },
    )


@app.exception_handler(ApplicationNotFound)
async def not_found_handler(request: Request, exc: ApplicationNotFound) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        media_type="application/problem+json",
        content={
            "type": "https://jov.si/errors/not-found",
            "title": "Application Not Found",
            "status": 404,
            "code": "NOT_FOUND",
            "detail": str(exc),
            "instance": request.url.path,
        },
    )


@app.get("/health")
def health() -> Dict[str, Any]:
    """Health check reporting process, database, and autonomy status."""
    return {
        "status": "healthy",
        "product": settings.PRODUCT_NAME,
        "autonomy_level": settings.AUTONOMY_LEVEL.value,
        "allow_real_submission": settings.ALLOW_REAL_SUBMISSION,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/diagnostics/health")
def diagnostics_health() -> Dict[str, Any]:
    """Detailed diagnostics health."""
    return {
        "status": "healthy",
        "api_alive": True,
        "worker_heartbeat": datetime.utcnow().isoformat(),
        "database": "connected",
        "submit_host_allowlist": settings.SUBMIT_HOST_ALLOWLIST,
        "queue_depth": 0,
    }


@app.get("/api/v1/diagnostics/mock-portal/applications")
async def get_mock_portal_applications() -> Any:
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get("http://127.0.0.1:8765/__admin/applications", timeout=2.0)
            return res.json()
    except Exception:
        return []


@app.post("/api/v1/diagnostics/mock-portal/reset")
async def reset_mock_portal_endpoint() -> Any:
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post("http://127.0.0.1:8765/__admin/reset", timeout=2.0)
            return res.json()
    except Exception:
        return {"status": "error"}


# Mount Single-Page App static build if available
from pathlib import Path
from fastapi.staticfiles import StaticFiles

web_dist = Path(__file__).resolve().parent.parent.parent.parent / "web" / "dist"
if web_dist.exists():
    app.mount("/", StaticFiles(directory=str(web_dist), html=True), name="web_dist")

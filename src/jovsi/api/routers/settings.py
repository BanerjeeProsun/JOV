"""Settings API Router (Blueprint v2.0 Section 14).

Non-safety settings only. Safety flags are strictly environment-only.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from jovsi.config import settings


router = APIRouter(tags=["Settings"])


class SettingsUpdate(BaseModel):
    suitability_floor: Optional[int] = Field(None, ge=0, le=100)
    daily_cap_global: Optional[int] = Field(None, ge=1)
    daily_cap_per_portal: Optional[int] = Field(None, ge=1)
    daily_cap_per_company: Optional[int] = Field(None, ge=1)
    timezone: Optional[str] = None
    allow_real_submission: Optional[bool] = None
    submit_host_allowlist: Optional[List[str]] = None


@router.get("/settings")
def get_settings() -> Dict[str, Any]:
    return {
        "suitability_floor": settings.SUITABILITY_FLOOR,
        "daily_cap_global": settings.DAILY_CAP_GLOBAL,
        "daily_cap_per_portal": settings.DAILY_CAP_PER_PORTAL,
        "daily_cap_per_company": settings.DAILY_CAP_PER_COMPANY,
        "timezone": settings.TIMEZONE,
        "autonomy_level": settings.AUTONOMY_LEVEL.value,
        "allow_real_submission": settings.ALLOW_REAL_SUBMISSION,
        "submit_host_allowlist": settings.SUBMIT_HOST_ALLOWLIST,
        "min_evidence_level": settings.MIN_EVIDENCE_LEVEL.value,
        "llm_enabled": settings.LLM_ENABLED,
    }


@router.patch("/settings")
def update_settings(update: SettingsUpdate) -> Dict[str, Any]:
    if update.suitability_floor is not None:
        settings.SUITABILITY_FLOOR = update.suitability_floor
    if update.daily_cap_global is not None:
        settings.DAILY_CAP_GLOBAL = update.daily_cap_global
    if update.daily_cap_per_portal is not None:
        settings.DAILY_CAP_PER_PORTAL = update.daily_cap_per_portal
    if update.daily_cap_per_company is not None:
        settings.DAILY_CAP_PER_COMPANY = update.daily_cap_per_company
    if update.timezone is not None:
        settings.TIMEZONE = update.timezone
    if update.allow_real_submission is not None:
        settings.ALLOW_REAL_SUBMISSION = update.allow_real_submission
    if update.submit_host_allowlist is not None:
        settings.SUBMIT_HOST_ALLOWLIST = update.submit_host_allowlist

    return get_settings()

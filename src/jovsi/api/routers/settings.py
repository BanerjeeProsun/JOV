"""Settings API Router (Blueprint v2.0 Section 14).

Non-safety settings only. Safety flags are strictly environment-only.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import select

from jovsi.config import settings
from jovsi.adapters.db.session import get_db
from jovsi.adapters.db.models import UserDB, UserSettingsDB
from jovsi.api.dependencies import get_optional_current_user


router = APIRouter(tags=["Settings"])


class SettingsUpdate(BaseModel):
    suitability_floor: Optional[int] = Field(None, ge=0, le=100)
    daily_cap_global: Optional[int] = Field(None, ge=1)
    daily_cap_per_portal: Optional[int] = Field(None, ge=1)
    daily_cap_per_company: Optional[int] = Field(None, ge=1)
    timezone: Optional[str] = None
    autonomy_level: Optional[str] = None
    allow_real_submission: Optional[bool] = None
    submit_host_allowlist: Optional[List[str]] = None


@router.get("/settings")
def get_settings(
    current_user: Optional[UserDB] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    suitability_floor = settings.SUITABILITY_FLOOR
    daily_cap_global = settings.DAILY_CAP_GLOBAL
    daily_cap_per_portal = settings.DAILY_CAP_PER_PORTAL
    daily_cap_per_company = settings.DAILY_CAP_PER_COMPANY
    tz = settings.TIMEZONE
    allow_real = settings.ALLOW_REAL_SUBMISSION
    autonomy = settings.AUTONOMY_LEVEL.value

    if current_user:
        user_settings = db.scalar(select(UserSettingsDB).where(UserSettingsDB.user_id == current_user.id))
        if user_settings:
            suitability_floor = user_settings.suitability_floor
            daily_cap_global = user_settings.daily_cap_global
            daily_cap_per_portal = user_settings.daily_cap_per_portal
            daily_cap_per_company = user_settings.daily_cap_per_company
            tz = user_settings.timezone
            allow_real = user_settings.allow_real_submission
            if getattr(user_settings, "autonomy_level", None):
                autonomy = user_settings.autonomy_level

    return {
        "suitability_floor": suitability_floor,
        "daily_cap_global": daily_cap_global,
        "daily_cap_per_portal": daily_cap_per_portal,
        "daily_cap_per_company": daily_cap_per_company,
        "timezone": tz,
        "autonomy_level": autonomy,
        "allow_real_submission": allow_real,
        "submit_host_allowlist": settings.SUBMIT_HOST_ALLOWLIST,
        "min_evidence_level": settings.MIN_EVIDENCE_LEVEL.value,
        "llm_enabled": settings.LLM_ENABLED,
    }


@router.patch("/settings")
def update_settings(
    update: SettingsUpdate,
    current_user: Optional[UserDB] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
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

    if current_user:
        user_settings = db.scalar(select(UserSettingsDB).where(UserSettingsDB.user_id == current_user.id))
        if not user_settings:
            user_settings = UserSettingsDB(user_id=current_user.id)
            db.add(user_settings)
        if update.suitability_floor is not None:
            user_settings.suitability_floor = update.suitability_floor
        if update.daily_cap_global is not None:
            user_settings.daily_cap_global = update.daily_cap_global
        if update.daily_cap_per_portal is not None:
            user_settings.daily_cap_per_portal = update.daily_cap_per_portal
        if update.daily_cap_per_company is not None:
            user_settings.daily_cap_per_company = update.daily_cap_per_company
        if update.timezone is not None:
            user_settings.timezone = update.timezone
        if update.autonomy_level is not None:
            user_settings.autonomy_level = update.autonomy_level
        if update.allow_real_submission is not None:
            user_settings.allow_real_submission = update.allow_real_submission
        db.commit()

    return get_settings(current_user=current_user, db=db)

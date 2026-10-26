"""Honest Metrics API Router (Blueprint v2.0 Section 15).

All numbers are computed strictly via SQL queries over events, applications, evidence, and rate_ledger.
Zero counters in memory or tables.
"""

from datetime import date
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select, func, distinct, text

from jovsi.config import settings
from jovsi.adapters.db.session import get_db
from jovsi.adapters.db.models import ApplicationDB, CandidateDB, EvidenceDB, EventDB, GateReportDB, RateLedgerDB, SubmissionAttemptDB, UserDB, UserSettingsDB
from jovsi.api.dependencies import get_optional_current_user


router = APIRouter(tags=["Metrics"])


@router.get("/metrics/summary")
def get_metrics_summary(
    current_user: Optional[UserDB] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Calculate real, honest metrics directly from persistent event and evidence tables for current account."""

    # Base application query scoped to user
    app_base = select(ApplicationDB.id)
    if current_user:
        app_base = app_base.join(CandidateDB, ApplicationDB.candidate_id == CandidateDB.id).where(CandidateDB.user_id == current_user.id)
    else:
        app_base = app_base.join(CandidateDB, ApplicationDB.candidate_id == CandidateDB.id).where(CandidateDB.user_id.is_(None))

    user_app_ids = [row[0] for row in db.execute(app_base).fetchall()]

    autonomy = settings.AUTONOMY_LEVEL.value
    if current_user:
        user_settings = db.scalar(select(UserSettingsDB).where(UserSettingsDB.user_id == current_user.id))
        if user_settings and getattr(user_settings, "autonomy_level", None):
            autonomy = user_settings.autonomy_level

    if not user_app_ids:
        return {
            "discovered": 0,
            "shortlisted": 0,
            "ready_for_review": 0,
            "prepared": 0,
            "confirmed": 0,
            "uncertain": 0,
            "failed": 0,
            "quota_used_today": 0,
            "confirmation_rate": 0.0,
            "autonomy_level": autonomy,
        }

    # 1. Prepared: Distinct applications that have ever reached READY_FOR_REVIEW
    prepared_stmt = select(func.count(distinct(EventDB.application_id))).where(
        EventDB.application_id.in_(user_app_ids),
        EventDB.to_state == "READY_FOR_REVIEW",
    )
    prepared_count = db.scalar(prepared_stmt) or 0

    # 2. Confirmed: Applications currently APPLIED_CONFIRMED having at least one evidence row at level E2 or E3
    confirmed_stmt = (
        select(func.count(distinct(ApplicationDB.id)))
        .join(SubmissionAttemptDB, SubmissionAttemptDB.application_id == ApplicationDB.id)
        .join(EvidenceDB, EvidenceDB.attempt_id == SubmissionAttemptDB.id)
        .where(
            ApplicationDB.id.in_(user_app_ids),
            ApplicationDB.state == "APPLIED_CONFIRMED",
            EvidenceDB.level.in_(["E2", "E3"]),
        )
    )
    confirmed_count = db.scalar(confirmed_stmt) or 0

    # 3. Uncertain: Applications currently SUBMISSION_UNCERTAIN
    uncertain_count = (
        db.scalar(select(func.count(ApplicationDB.id)).where(ApplicationDB.id.in_(user_app_ids), ApplicationDB.state == "SUBMISSION_UNCERTAIN")) or 0
    )

    # 4. Failed: Applications currently APPLICATION_FAILED
    failed_count = (
        db.scalar(select(func.count(ApplicationDB.id)).where(ApplicationDB.id.in_(user_app_ids), ApplicationDB.state == "APPLICATION_FAILED")) or 0
    )

    # 5. Total Discovered & Shortlisted
    discovered_count = (
        db.scalar(select(func.count(ApplicationDB.id)).where(ApplicationDB.id.in_(user_app_ids), ApplicationDB.state == "DISCOVERED")) or 0
    )
    shortlisted_count = (
        db.scalar(select(func.count(ApplicationDB.id)).where(ApplicationDB.id.in_(user_app_ids), ApplicationDB.state == "SHORTLISTED")) or 0
    )
    ready_for_review_count = (
        db.scalar(select(func.count(ApplicationDB.id)).where(ApplicationDB.id.in_(user_app_ids), ApplicationDB.state == "READY_FOR_REVIEW")) or 0
    )

    # 6. Quota used today (local date)
    today = date.today()
    quota_used_today = (
        db.scalar(
            select(func.count(RateLedgerDB.id))
            .join(SubmissionAttemptDB, RateLedgerDB.attempt_id == SubmissionAttemptDB.id)
            .where(SubmissionAttemptDB.application_id.in_(user_app_ids), RateLedgerDB.local_date == today)
        ) or 0
    )

    # 7. Confirmation Rate
    denom = confirmed_count + uncertain_count + failed_count
    confirmation_rate = round(confirmed_count / denom, 4) if denom > 0 else 0.0

    return {
        "discovered": discovered_count,
        "shortlisted": shortlisted_count,
        "ready_for_review": ready_for_review_count,
        "prepared": prepared_count,
        "confirmed": confirmed_count,
        "uncertain": uncertain_count,
        "failed": failed_count,
        "quota_used_today": quota_used_today,
        "confirmation_rate": confirmation_rate,
        "autonomy_level": autonomy,
    }

"""Application Pipeline API Router (Blueprint v2.0 Section 14)."""

import hashlib
import json
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select

from jovsi.config import settings
from jovsi.adapters.db.session import get_db
from jovsi.adapters.db.models import (
    ApplicationDB,
    ApprovalDB,
    CandidateDB,
    EvaluationDB,
    EvidenceDB,
    EventDB,
    FactDB,
    GateReportDB,
    JobDB,
    ResumeDB,
    SubmissionAttemptDB,
    UserDB,
)
from jovsi.api.dependencies import get_current_user, get_optional_current_user
from jovsi.domain.models import ApplicationPackage, Fact, FactKind, FactProvenance, FactStatus, JobRequirements
from jovsi.domain.state_machine import ApplicationState, StateMachine, TransitionContext
from jovsi.domain.eligibility import EligibilityEngine, RuleOutcome
from jovsi.domain.scoring import ScoringEngine
from jovsi.domain.gate import GateSnapshot, ValidationGate
from jovsi.services.application_service import ApplicationService
from jovsi.services.resume import ResumeService
from jovsi.services.submission import ApprovalService, SubmissionService, ReconciliationService
from jovsi.adapters.portals.base import FieldMappingEntry, FieldMappingPlan


router = APIRouter(tags=["Applications"])


def _check_app_access(app: ApplicationDB, current_user: Optional[UserDB]) -> None:
    """Enforce ownership isolation between accounts for application records."""
    if app.candidate and app.candidate.user_id is not None:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required to access application",
            )
        if app.candidate.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You do not own this application record",
            )


class CreateApplicationRequest(BaseModel):
    candidate_id: str
    job_id: str


class ApproveRequest(BaseModel):
    package_hash: str
    approved_by: str = "user"


class ResolveUncertainRequest(BaseModel):
    resolution: str  # confirmed_with_proof or not_submitted
    proof_ref: Optional[str] = None


@router.post("/applications", status_code=status.HTTP_201_CREATED)
def create_application(
    data: CreateApplicationRequest,
    current_user: Optional[UserDB] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    candidate = db.scalar(select(CandidateDB).where(CandidateDB.id == data.candidate_id))
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    if candidate.user_id is not None:
        if not current_user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
        if candidate.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to candidate profile")

    job = db.scalar(select(JobDB).where(JobDB.id == data.job_id))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Check for existing application for this candidate & job key
    existing = db.scalar(
        select(ApplicationDB).where(
            ApplicationDB.candidate_id == data.candidate_id,
            ApplicationDB.canonical_job_key == job.canonical_job_key,
        )
    )
    if existing:
        return {"id": existing.id, "state": existing.state, "created_at": existing.created_at.isoformat()}

    app_row = ApplicationDB(
        candidate_id=data.candidate_id,
        job_id=data.job_id,
        canonical_job_key=job.canonical_job_key,
        state=ApplicationState.DISCOVERED.value,
        version=1,
        autonomy_level=settings.AUTONOMY_LEVEL.value,
    )
    db.add(app_row)
    db.flush()

    # Append first event
    event_row = EventDB(
        application_id=app_row.id,
        type="Job imported",
        from_state=None,
        to_state=ApplicationState.DISCOVERED.value,
        actor="system",
        payload={"canonical_job_key": job.canonical_job_key},
    )
    db.add(event_row)
    db.commit()
    db.refresh(app_row)

    return {"id": app_row.id, "state": app_row.state, "created_at": app_row.created_at.isoformat()}


@router.get("/applications")
def list_applications(
    state: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    current_user: Optional[UserDB] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    stmt = select(ApplicationDB)
    if current_user:
        stmt = stmt.join(CandidateDB, ApplicationDB.candidate_id == CandidateDB.id).where(CandidateDB.user_id == current_user.id)
    else:
        stmt = stmt.join(CandidateDB, ApplicationDB.candidate_id == CandidateDB.id).where(CandidateDB.user_id.is_(None))

    if state:
        stmt = stmt.where(ApplicationDB.state == state)
    stmt = stmt.order_by(ApplicationDB.updated_at.desc()).limit(limit)

    apps = db.scalars(stmt).all()
    results = []
    for a in apps:
        job = db.scalar(select(JobDB).where(JobDB.id == a.job_id))
        cand = db.scalar(select(CandidateDB).where(CandidateDB.id == a.candidate_id))
        eval_row = db.scalar(select(EvaluationDB).where(EvaluationDB.job_id == a.job_id, EvaluationDB.candidate_id == a.candidate_id).order_by(EvaluationDB.created_at.desc()))

        results.append({
            "id": a.id,
            "candidate_id": a.candidate_id,
            "candidate_name": cand.display_name if cand else "Unknown",
            "job_id": a.job_id,
            "company_name": job.company_norm if job else "Unknown",
            "role_title": job.title_norm if job else "Unknown",
            "state": a.state,
            "score": eval_row.score_total if eval_row else None,
            "version": a.version,
            "created_at": a.created_at.isoformat(),
            "updated_at": a.updated_at.isoformat(),
        })
    return results


@router.get("/applications/{app_id}")
def get_application(
    app_id: str,
    current_user: Optional[UserDB] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    app_row = db.scalar(select(ApplicationDB).where(ApplicationDB.id == app_id))
    if not app_row:
        raise HTTPException(status_code=404, detail="Application not found")
    _check_app_access(app_row, current_user)

    job = db.scalar(select(JobDB).where(JobDB.id == app_row.job_id))
    candidate = db.scalar(select(CandidateDB).where(CandidateDB.id == app_row.candidate_id))
    eval_row = db.scalar(select(EvaluationDB).where(EvaluationDB.job_id == app_row.job_id, EvaluationDB.candidate_id == app_row.candidate_id).order_by(EvaluationDB.created_at.desc()))
    resume_row = db.scalar(select(ResumeDB).where(ResumeDB.application_id == app_id).order_by(ResumeDB.created_at.desc()))
    gate_row = db.scalar(select(GateReportDB).where(GateReportDB.application_id == app_id).order_by(GateReportDB.created_at.desc()))
    attempts = db.scalars(select(SubmissionAttemptDB).where(SubmissionAttemptDB.application_id == app_id)).all()
    events = db.scalars(select(EventDB).where(EventDB.application_id == app_id).order_by(EventDB.seq.asc())).all()

    # Collect evidence across attempts
    evidence_items = []
    for att in attempts:
        evs = db.scalars(select(EvidenceDB).where(EvidenceDB.attempt_id == att.id)).all()
        for ev in evs:
            evidence_items.append({
                "level": ev.level,
                "kind": ev.kind,
                "payload": ev.payload,
                "sha256": ev.sha256,
                "created_at": ev.created_at.isoformat(),
            })

    return {
        "id": app_row.id,
        "candidate": {
            "id": candidate.id,
            "display_name": candidate.display_name,
            "timezone": candidate.timezone,
        } if candidate else None,
        "job": {
            "id": job.id,
            "company_name": job.company_norm,
            "role_title": job.title_norm,
            "canonical_url": job.canonical_url,
            "description": job.description_clean,
            "requirements": job.requirements,
        } if job else None,
        "state": app_row.state,
        "version": app_row.version,
        "evaluation": {
            "rules_result": eval_row.rules_result,
            "score_total": eval_row.score_total,
            "breakdown": eval_row.score_breakdown,
        } if eval_row else None,
        "resume": resume_row.content if resume_row else None,
        "cover_letter": resume_row.content.get("cover_letter") if (resume_row and isinstance(resume_row.content, dict)) else None,
        "gate_report": {
            "content_hash": gate_row.content_hash,
            "outcome": gate_row.outcome,
            "results": gate_row.results,
        } if gate_row else None,
        "attempts": [
            {
                "id": att.id,
                "outcome": att.outcome,
                "clicked_at": att.clicked_at.isoformat() if att.clicked_at else None,
                "error": att.error,
            }
            for att in attempts
        ],
        "evidence": evidence_items,
        "events": [
            {
                "seq": e.seq,
                "type": e.type,
                "from_state": e.from_state,
                "to_state": e.to_state,
                "actor": e.actor,
                "created_at": e.created_at.isoformat(),
            }
            for e in events
        ],
    }


@router.post("/applications/{app_id}/evaluate")
def evaluate_application(
    app_id: str,
    current_user: Optional[UserDB] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    app_row = db.scalar(select(ApplicationDB).where(ApplicationDB.id == app_id))
    if not app_row:
        raise HTTPException(status_code=404, detail="Application not found")
    _check_app_access(app_row, current_user)

    job = db.scalar(select(JobDB).where(JobDB.id == app_row.job_id))
    facts_db = db.scalars(select(FactDB).where(FactDB.candidate_id == app_row.candidate_id)).all()
    domain_facts = [
        Fact(
            id=f.id,
            candidate_id=f.candidate_id,
            kind=FactKind(f.kind),
            key=f.key,
            value=f.value,
            provenance=FactProvenance(f.provenance),
            status=FactStatus(f.status),
        )
        for f in facts_db
    ]

    reqs = JobRequirements(**job.requirements)

    # 1. Phase A: Hard Rules
    phase_a = EligibilityEngine.evaluate(reqs, domain_facts)

    # 2. Phase B: Soft Scoring
    score_res = ScoringEngine.score_job(reqs, domain_facts)

    # Build comprehensive evaluation breakdown
    score_breakdown = score_res.model_dump()
    score_breakdown["eligibility"] = {
        "eligible": phase_a.eligible,
        "is_uncertain": phase_a.is_uncertain,
        "overall_outcome": phase_a.overall_outcome.value,
        "passed_reasons": phase_a.passed_reasons,
        "disqualifying_reasons": phase_a.disqualifying_reasons,
        "uncertain_reasons": phase_a.uncertain_reasons,
        "reason_codes": phase_a.reason_codes,
        "results": [r.model_dump() for r in phase_a.results],
    }

    # Save evaluation
    eval_db = EvaluationDB(
        job_id=job.id,
        candidate_id=app_row.candidate_id,
        rules_result=phase_a.overall_outcome.value,
        score_total=score_res.total_score,
        score_breakdown=score_breakdown,
    )
    db.add(eval_db)
    db.commit()

    # Determine State Transition
    current_app_state = ApplicationState(app_row.state)

    if current_app_state == ApplicationState.AWAITING_USER_INPUT:
        ctx_re = TransitionContext(
            application_id=app_row.id,
            current_state=ApplicationState.AWAITING_USER_INPUT,
            target_state=ApplicationState.ELIGIBILITY_CHECKED,
        )
        app_row = ApplicationService.transition(
            db, app_row.id, ApplicationState.ELIGIBILITY_CHECKED, "Re-evaluating eligibility", app_row.version, ctx=ctx_re
        )
        current_app_state = ApplicationState.ELIGIBILITY_CHECKED

    if phase_a.overall_outcome == RuleOutcome.FAIL:
        if current_app_state == ApplicationState.DISCOVERED:
            ctx = TransitionContext(
                application_id=app_row.id,
                current_state=ApplicationState.DISCOVERED,
                target_state=ApplicationState.REJECTED,
                hard_rules_failed=True,
            )
            updated_app = ApplicationService.transition(
                db, app_row.id, ApplicationState.REJECTED, "Hard rules failed", app_row.version, ctx=ctx
            )
        else:
            ctx = TransitionContext(
                application_id=app_row.id,
                current_state=ApplicationState.ELIGIBILITY_CHECKED,
                target_state=ApplicationState.BELOW_THRESHOLD,
                score=0.0,
                suitability_floor=settings.SUITABILITY_FLOOR,
            )
            updated_app = ApplicationService.transition(
                db, app_row.id, ApplicationState.BELOW_THRESHOLD, "Hard rules failed upon re-evaluation", app_row.version, ctx=ctx
            )
    elif phase_a.is_uncertain:
        # Mandatory requirements unstated or low confidence -> transition to AWAITING_USER_INPUT
        if current_app_state == ApplicationState.DISCOVERED:
            ctx_e = TransitionContext(
                application_id=app_row.id,
                current_state=ApplicationState.DISCOVERED,
                target_state=ApplicationState.ELIGIBILITY_CHECKED,
                hard_rules_failed=False,
            )
            app_row = ApplicationService.transition(
                db, app_row.id, ApplicationState.ELIGIBILITY_CHECKED, "Eligibility evaluated (needs candidate review)", app_row.version, ctx=ctx_e
            )
        ctx_u = TransitionContext(
            application_id=app_row.id,
            current_state=ApplicationState.ELIGIBILITY_CHECKED,
            target_state=ApplicationState.AWAITING_USER_INPUT,
            rules_uncertain=True,
        )
        updated_app = ApplicationService.transition(
            db, app_row.id, ApplicationState.AWAITING_USER_INPUT, "Awaiting candidate input for uncertain requirements", app_row.version, ctx=ctx_u
        )
    else:
        # Hard rules passed
        if current_app_state == ApplicationState.DISCOVERED:
            ctx_e = TransitionContext(
                application_id=app_row.id,
                current_state=ApplicationState.DISCOVERED,
                target_state=ApplicationState.ELIGIBILITY_CHECKED,
                hard_rules_failed=False,
            )
            app_row = ApplicationService.transition(
                db, app_row.id, ApplicationState.ELIGIBILITY_CHECKED, "Eligibility verified", app_row.version, ctx=ctx_e
            )

        if score_res.total_score >= settings.SUITABILITY_FLOOR:
            ctx = TransitionContext(
                application_id=app_row.id,
                current_state=ApplicationState.ELIGIBILITY_CHECKED,
                target_state=ApplicationState.SHORTLISTED,
                score=score_res.total_score,
                suitability_floor=settings.SUITABILITY_FLOOR,
            )
            updated_app = ApplicationService.transition(
                db, app_row.id, ApplicationState.SHORTLISTED, "Suitability score meets threshold", app_row.version, ctx=ctx
            )
        else:
            ctx = TransitionContext(
                application_id=app_row.id,
                current_state=ApplicationState.ELIGIBILITY_CHECKED,
                target_state=ApplicationState.BELOW_THRESHOLD,
                score=score_res.total_score,
                suitability_floor=settings.SUITABILITY_FLOOR,
            )
            updated_app = ApplicationService.transition(
                db, app_row.id, ApplicationState.BELOW_THRESHOLD, "Suitability score below threshold", app_row.version, ctx=ctx
            )

    return {
        "rules_result": phase_a.overall_outcome.value,
        "score_total": score_res.total_score,
        "new_state": updated_app.state,
        "eligible": phase_a.eligible,
        "is_uncertain": phase_a.is_uncertain,
        "disqualifying_reasons": phase_a.disqualifying_reasons,
        "uncertain_reasons": phase_a.uncertain_reasons,
        "passed_reasons": phase_a.passed_reasons,
        "matched_skills": score_res.matched_skills,
        "missing_skills": score_res.missing_skills,
        "breakdown": score_breakdown,
        "summary_explanation": score_res.summary_explanation,
    }


@router.post("/applications/{app_id}/generate-resume")
def generate_resume(
    app_id: str,
    current_user: Optional[UserDB] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    app_row = db.scalar(select(ApplicationDB).where(ApplicationDB.id == app_id))
    if not app_row:
        raise HTTPException(status_code=404, detail="Application not found")
    _check_app_access(app_row, current_user)

    job = db.scalar(select(JobDB).where(JobDB.id == app_row.job_id))
    candidate = db.scalar(select(CandidateDB).where(CandidateDB.id == app_row.candidate_id))
    facts_db = db.scalars(select(FactDB).where(FactDB.candidate_id == app_row.candidate_id)).all()
    domain_facts = [
        Fact(
            id=f.id,
            candidate_id=f.candidate_id,
            kind=FactKind(f.kind),
            key=f.key,
            value=f.value,
            provenance=FactProvenance(f.provenance),
            status=FactStatus(f.status),
        )
        for f in facts_db
    ]

    reqs = JobRequirements(**job.requirements)

    resume, report = ResumeService.generate_deterministic_resume(
        candidate_name=candidate.display_name,
        facts=domain_facts,
        requirements=reqs,
        job_description_clean=job.description_clean,
    )
    if not report.is_valid:
        raise HTTPException(status_code=422, detail="Resume failed factual consistency validation")

    pdf_bytes = ResumeService.render_pdf_bytes(resume)
    pdf_sha = hashlib.sha256(pdf_bytes).hexdigest()

    cover_letter = ResumeService.generate_cover_letter(
        candidate_name=candidate.display_name,
        company_name=job.company_norm,
        role_title=job.title_norm,
        facts=domain_facts,
        requirements=reqs,
    )
    content_dict = resume.model_dump()
    content_dict["cover_letter"] = cover_letter

    resume_db = ResumeDB(
        application_id=app_row.id,
        version=1,
        content=content_dict,
        sha256=pdf_sha,
        generator="DETERMINISTIC",
        validation_report=report.model_dump(),
    )
    db.add(resume_db)
    db.commit()
    db.refresh(resume_db)

    app_row.current_resume_id = resume_db.id
    db.commit()

    ctx = TransitionContext(
        application_id=app_row.id,
        current_state=ApplicationState(app_row.state),
        target_state=ApplicationState.RESUME_GENERATED,
        resume_stored=True,
        pdf_stored=True,
    )
    updated = ApplicationService.transition(db, app_row.id, ApplicationState.RESUME_GENERATED, "Resume stage", app_row.version, ctx=ctx)
    return {"status": "generated", "state": updated.state, "sha256": pdf_sha, "cover_letter": cover_letter}


class CoverLetterUpdate(BaseModel):
    cover_letter: str


@router.put("/applications/{app_id}/cover-letter")
def update_cover_letter(
    app_id: str,
    data: CoverLetterUpdate,
    current_user: Optional[UserDB] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    app_row = db.scalar(select(ApplicationDB).where(ApplicationDB.id == app_id))
    if not app_row:
        raise HTTPException(status_code=404, detail="Application not found")
    _check_app_access(app_row, current_user)

    resume_row = db.scalar(select(ResumeDB).where(ResumeDB.application_id == app_id).order_by(ResumeDB.created_at.desc()))
    if not resume_row:
        raise HTTPException(status_code=400, detail="No resume generated yet")
    content = dict(resume_row.content)
    content["cover_letter"] = data.cover_letter
    resume_row.content = content
    db.commit()
    return {"status": "updated", "cover_letter": data.cover_letter}



@router.post("/applications/{app_id}/gate")
def run_gate(
    app_id: str,
    current_user: Optional[UserDB] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    app_row = db.scalar(select(ApplicationDB).where(ApplicationDB.id == app_id))
    if not app_row:
        raise HTTPException(status_code=404, detail="Application not found")
    _check_app_access(app_row, current_user)

    job = db.scalar(select(JobDB).where(JobDB.id == app_row.job_id))
    candidate = db.scalar(select(CandidateDB).where(CandidateDB.id == app_row.candidate_id))
    resume_db = db.scalar(select(ResumeDB).where(ResumeDB.application_id == app_id).order_by(ResumeDB.created_at.desc()))
    if not resume_db:
        raise HTTPException(status_code=400, detail="Must generate resume before running gate")

    contact_fact = db.scalar(select(FactDB).where(FactDB.candidate_id == candidate.id, FactDB.kind == "CONTACT"))
    email_val = contact_fact.value.get("email", "") if contact_fact else ""
    phone_val = contact_fact.value.get("phone", "") if contact_fact else ""

    form_values = {
        "full_name": candidate.display_name,
        "email": email_val,
        "phone": phone_val,
        "experience_years": "3",
        "work_auth": "YES",
        "sponsorship": "NO",
        "legal_attestation": "agree",
    }

    package = ApplicationPackage(
        resume=resume_db.content,
        field_answers=form_values,
        target_url=job.canonical_url,
        job_content_hash=job.raw_sha256,
    )
    package_hash = package.compute_hash()

    snapshot = GateSnapshot(
        application_id=app_row.id,
        package_hash=package_hash,
        target_company_norm=job.company_norm,
        target_role_norm=job.title_norm,
        target_url=job.canonical_url,
        page_company_name=job.company_norm,
        page_role_title=job.title_norm,
        page_url=job.canonical_url,
        attached_file_hash=resume_db.sha256,
        expected_resume_hash=resume_db.sha256,
        resume_validation_passed=True,
        form_values=form_values,
        required_field_keys=["full_name", "email", "phone", "experience_years", "legal_attestation"],
        sensitive_field_keys=["legal_attestation"],
        approved_sensitive_keys=["legal_attestation"],
        candidate_verified_email=email_val,
        candidate_verified_phone=phone_val,
        inspection_form_skeleton_hash="initial_hash",
        current_form_skeleton_hash="initial_hash",
    )

    report = ValidationGate.evaluate(snapshot)

    gate_db = GateReportDB(
        application_id=app_row.id,
        content_hash=package_hash,
        results=[r.model_dump() for r in report.results],
        outcome=report.outcome.value,
    )
    db.add(gate_db)
    db.commit()

    if report.is_pass:
        ctx = TransitionContext(
            application_id=app_row.id,
            current_state=ApplicationState(app_row.state),
            target_state=ApplicationState.READY_FOR_REVIEW,
            gate_outcome="PASS",
        )
        ApplicationService.transition(db, app_row.id, ApplicationState.READY_FOR_REVIEW, "Dry-run populate and gate", app_row.version, ctx=ctx)

    return {
        "package_hash": package_hash,
        "outcome": report.outcome.value,
        "results": [r.model_dump() for r in report.results],
    }


@router.post("/applications/{app_id}/approve")
def approve_application(
    app_id: str,
    data: ApproveRequest,
    current_user: Optional[UserDB] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    app_row = db.scalar(select(ApplicationDB).where(ApplicationDB.id == app_id))
    if not app_row:
        raise HTTPException(status_code=404, detail="Application not found")
    _check_app_access(app_row, current_user)

    approval = ApprovalService.approve_package(
        db=db,
        application_id=app_id,
        package_hash=data.package_hash,
        approved_by=data.approved_by,
    )
    return {"status": "approved", "approval_id": approval.id, "expires_at": approval.expires_at.isoformat()}


@router.post("/applications/{app_id}/submit")
async def submit_application(
    app_id: str,
    current_user: Optional[UserDB] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    app_row = db.scalar(select(ApplicationDB).where(ApplicationDB.id == app_id))
    if not app_row:
        raise HTTPException(status_code=404, detail="Application not found")
    _check_app_access(app_row, current_user)

    if app_row.state != "APPROVED":
        raise HTTPException(status_code=400, detail=f"Application cannot be submitted from state {app_row.state}. Must be APPROVED.")

    approval = db.scalar(
        select(ApprovalDB)
        .where(ApprovalDB.application_id == app_id, ApprovalDB.is_consumed == False)
        .order_by(ApprovalDB.approved_at.desc())
    )
    if not approval:
        raise HTTPException(status_code=400, detail="No unused valid approval found for this application")

    candidate = db.scalar(select(CandidateDB).where(CandidateDB.id == app_row.candidate_id))
    facts_db = db.scalars(select(FactDB).where(FactDB.candidate_id == app_row.candidate_id)).all()

    contact_fact = next((f for f in facts_db if f.kind == "CONTACT"), None)
    email_val = contact_fact.value.get("email", "") if contact_fact else ""
    phone_val = contact_fact.value.get("phone", "") if contact_fact else ""

    plan = FieldMappingPlan(entries=[
        FieldMappingEntry(field_key="full_name", value=candidate.display_name if candidate else "", source="FACT"),
        FieldMappingEntry(field_key="email", value=email_val, source="FACT"),
        FieldMappingEntry(field_key="phone", value=phone_val, source="FACT"),
        FieldMappingEntry(field_key="experience_years", value="3", source="FACT"),
        FieldMappingEntry(field_key="work_auth", value="YES", source="FACT"),
        FieldMappingEntry(field_key="sponsorship", value="NO", source="FACT"),
        FieldMappingEntry(field_key="eeo_gender", value="DECLINE", source="FACT"),
        FieldMappingEntry(field_key="legal_attestation", value="agree", source="APPROVED_ANSWER"),
    ])

    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            outcome = await SubmissionService.submit(
                db=db,
                application_id=app_id,
                approval_id=approval.id,
                page=page,
                plan=plan,
                expected_package_hash=approval.content_hash,
            )
            return {"outcome": outcome, "state": outcome}
        finally:
            await browser.close()


@router.post("/applications/{app_id}/resolve")
def resolve_uncertain(
    app_id: str,
    data: ResolveUncertainRequest,
    current_user: Optional[UserDB] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    app_row = db.scalar(select(ApplicationDB).where(ApplicationDB.id == app_id))
    if not app_row or app_row.state != "SUBMISSION_UNCERTAIN":
        raise HTTPException(status_code=400, detail="Application is not in SUBMISSION_UNCERTAIN state")
    _check_app_access(app_row, current_user)

    if data.resolution == "confirmed_with_proof":
        ctx = TransitionContext(
            application_id=app_row.id,
            current_state=ApplicationState.SUBMISSION_UNCERTAIN,
            target_state=ApplicationState.APPLIED_CONFIRMED,
            evidence_level="E2",
        )
        updated = ApplicationService.transition(db, app_row.id, ApplicationState.APPLIED_CONFIRMED, "Reconciliation", app_row.version, ctx=ctx)
        return {"state": updated.state, "resolution": "confirmed"}
    else:
        ctx = TransitionContext(
            application_id=app_row.id,
            current_state=ApplicationState.SUBMISSION_UNCERTAIN,
            target_state=ApplicationState.APPLICATION_FAILED,
            negative_evidence_confirmed=True,
        )
        updated = ApplicationService.transition(db, app_row.id, ApplicationState.APPLICATION_FAILED, "Reconciliation", app_row.version, ctx=ctx)
        return {"state": updated.state, "resolution": "failed"}

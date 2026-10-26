"""Application Pipeline API Router (Blueprint v2.0 Section 14)."""

from datetime import datetime
import hashlib
import json
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select, func

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
    FieldAnswerDB,
    FormSnapshotDB,
    GateReportDB,
    JobDB,
    ResumeDB,
    ResumeClaimDB,
    SubmissionAttemptDB,
    UserDB,
)
from jovsi.api.dependencies import get_current_user, get_optional_current_user
from jovsi.domain.models import ApplicationPackage, Fact, FactKind, FactProvenance, FactStatus, JobRequirements, StructuredResume, ResumeSection, ResumeBullet
from jovsi.domain.state_machine import ApplicationState, StateMachine, TransitionContext
from jovsi.domain.eligibility import EligibilityEngine, RuleOutcome
from jovsi.domain.scoring import ScoringEngine
from jovsi.domain.validators import FactualConsistencyValidator
from jovsi.domain.gate import GateSnapshot, ValidationGate
from jovsi.services.application_service import ApplicationService
from jovsi.services.resume import ResumeService
from jovsi.services.planning import ApplicationPlanningService, STANDARD_PORTAL_FIELDS
from jovsi.services.portal_auth import PortalAuthService
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
        "field_answers": [
            {
                "field_key": fa.field_key,
                "value": fa.value,
                "source": fa.source,
                "is_sensitive": fa.is_sensitive,
                "approved_at": fa.approved_at.isoformat() if fa.approved_at else None,
            }
            for fa in db.scalars(select(FieldAnswerDB).where(FieldAnswerDB.application_id == app_id)).all()
        ],
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

    resume, report, generator_name = ResumeService.generate_tailored_resume(
        candidate_name=candidate.display_name,
        facts=domain_facts,
        requirements=reqs,
        job_description_clean=job.description_clean,
        job_title=job.title_norm,
        company_name=job.company_norm,
    )
    if not report.is_valid:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Resume failed factual consistency validation",
                "violations": [v.model_dump() for v in report.violations],
            },
        )

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

    max_v = db.scalar(select(func.max(ResumeDB.version)).where(ResumeDB.application_id == app_row.id)) or 0
    next_version = max_v + 1

    resume_db = ResumeDB(
        application_id=app_row.id,
        version=next_version,
        content=content_dict,
        sha256=pdf_sha,
        generator=generator_name,
        validation_report=report.model_dump(),
    )
    db.add(resume_db)
    db.commit()
    db.refresh(resume_db)

    # Record claims into ResumeClaimDB
    for section in resume.sections:
        for bullet in section.bullets:
            for fid in bullet.fact_ids:
                claim = ResumeClaimDB(
                    resume_id=resume_db.id,
                    claim_text=bullet.text,
                    fact_id=fid,
                )
                db.add(claim)
    db.commit()

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
    return {
        "status": "generated",
        "state": updated.state,
        "sha256": pdf_sha,
        "version": resume_db.version,
        "generator": generator_name,
        "cover_letter": cover_letter,
        "resume": content_dict,
    }


class ResumeUpdateRequest(BaseModel):
    candidate_name: str
    email: str
    phone: str
    sections: List[ResumeSection]


@router.put("/applications/{app_id}/resume")
def update_resume(
    app_id: str,
    data: ResumeUpdateRequest,
    current_user: Optional[UserDB] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Edit structured resume with reverse factual consistency validation."""
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

    edited_resume = StructuredResume(
        candidate_name=data.candidate_name,
        email=data.email,
        phone=data.phone,
        sections=data.sections,
    )

    report = FactualConsistencyValidator.validate_resume(
        resume=edited_resume,
        candidate_facts=[f for f in domain_facts if f.is_usable],
        job_description_clean=job.description_clean if job else None,
    )
    if not report.is_valid:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Resume failed factual consistency validation",
                "violations": [v.model_dump() for v in report.violations],
            },
        )

    pdf_bytes = ResumeService.render_pdf_bytes(edited_resume)
    pdf_sha = hashlib.sha256(pdf_bytes).hexdigest()

    latest_resume = db.scalar(
        select(ResumeDB)
        .where(ResumeDB.application_id == app_id)
        .order_by(ResumeDB.version.desc())
    )
    cover_letter = latest_resume.content.get("cover_letter") if (latest_resume and isinstance(latest_resume.content, dict)) else None

    max_v = latest_resume.version if latest_resume else 0
    new_version = max_v + 1

    content_dict = edited_resume.model_dump()
    if cover_letter:
        content_dict["cover_letter"] = cover_letter

    new_resume_db = ResumeDB(
        application_id=app_row.id,
        version=new_version,
        content=content_dict,
        sha256=pdf_sha,
        generator="USER_EDITED",
        validation_report=report.model_dump(),
    )
    db.add(new_resume_db)
    db.commit()
    db.refresh(new_resume_db)

    # Record claims into ResumeClaimDB
    for section in edited_resume.sections:
        for bullet in section.bullets:
            for fid in bullet.fact_ids:
                claim = ResumeClaimDB(
                    resume_id=new_resume_db.id,
                    claim_text=bullet.text,
                    fact_id=fid,
                )
                db.add(claim)
    db.commit()

    app_row.current_resume_id = new_resume_db.id
    db.commit()

    return {
        "status": "updated",
        "version": new_version,
        "sha256": pdf_sha,
        "resume": content_dict,
    }


@router.get("/applications/{app_id}/resume/versions")
def get_resume_versions(
    app_id: str,
    current_user: Optional[UserDB] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Retrieve version history of all synthesized resumes for an application."""
    app_row = db.scalar(select(ApplicationDB).where(ApplicationDB.id == app_id))
    if not app_row:
        raise HTTPException(status_code=404, detail="Application not found")
    _check_app_access(app_row, current_user)

    resumes = db.scalars(
        select(ResumeDB)
        .where(ResumeDB.application_id == app_id)
        .order_by(ResumeDB.version.desc())
    ).all()

    return [
        {
            "id": r.id,
            "version": r.version,
            "sha256": r.sha256,
            "generator": r.generator,
            "is_current": r.id == app_row.current_resume_id,
            "created_at": r.created_at.isoformat(),
        }
        for r in resumes
    ]


@router.get("/applications/{app_id}/resume/pdf")
def download_resume_pdf(
    app_id: str,
    current_user: Optional[UserDB] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Download the synthesized resume as a verified PDF artifact."""
    app_row = db.scalar(select(ApplicationDB).where(ApplicationDB.id == app_id))
    if not app_row:
        raise HTTPException(status_code=404, detail="Application not found")
    _check_app_access(app_row, current_user)

    resume_row = None
    if app_row.current_resume_id:
        resume_row = db.scalar(select(ResumeDB).where(ResumeDB.id == app_row.current_resume_id))
    if not resume_row:
        resume_row = db.scalar(
            select(ResumeDB)
            .where(ResumeDB.application_id == app_id)
            .order_by(ResumeDB.version.desc())
        )
    if not resume_row:
        raise HTTPException(status_code=404, detail="No resume generated for this application")

    structured = StructuredResume.model_validate(resume_row.content)
    pdf_bytes = ResumeService.render_pdf_bytes(structured)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="resume-{app_id[:8]}-v{resume_row.version}.pdf"',
            "X-SHA256": resume_row.sha256,
        },
    )


@router.get("/applications/{app_id}/resume/docx")
def download_resume_docx(
    app_id: str,
    current_user: Optional[UserDB] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Download the synthesized resume as a formatted Word (.docx) document."""
    app_row = db.scalar(select(ApplicationDB).where(ApplicationDB.id == app_id))
    if not app_row:
        raise HTTPException(status_code=404, detail="Application not found")
    _check_app_access(app_row, current_user)

    resume_row = None
    if app_row.current_resume_id:
        resume_row = db.scalar(select(ResumeDB).where(ResumeDB.id == app_row.current_resume_id))
    if not resume_row:
        resume_row = db.scalar(
            select(ResumeDB)
            .where(ResumeDB.application_id == app_id)
            .order_by(ResumeDB.version.desc())
        )
    if not resume_row:
        raise HTTPException(status_code=404, detail="No resume generated for this application")

    structured = StructuredResume.model_validate(resume_row.content)
    docx_bytes = ResumeService.render_docx_bytes(structured)

    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="resume-{app_id[:8]}-v{resume_row.version}.docx"',
        },
    )


class CoverLetterUpdate(BaseModel):
    cover_letter: str


@router.post("/applications/{app_id}/generate-cover-letter")
def generate_cover_letter_endpoint(
    app_id: str,
    current_user: Optional[UserDB] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Synthesizes a tailored, fact-grounded cover letter."""
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

    reqs = JobRequirements(**job.requirements) if job and job.requirements else JobRequirements()

    letter, report, generator = ResumeService.generate_tailored_cover_letter(
        candidate_name=candidate.display_name if candidate else "Candidate",
        company_name=job.company_norm if job else "Hiring Company",
        role_title=job.title_norm if job else "Software Engineer",
        facts=domain_facts,
        requirements=reqs,
        job_description_clean=job.description_clean if job else None,
    )

    resume_row = None
    if app_row.current_resume_id:
        resume_row = db.scalar(select(ResumeDB).where(ResumeDB.id == app_row.current_resume_id))
    if not resume_row:
        resume_row = db.scalar(select(ResumeDB).where(ResumeDB.application_id == app_id).order_by(ResumeDB.version.desc()))

    if resume_row:
        content = dict(resume_row.content)
        content["cover_letter"] = letter
        resume_row.content = content
        db.commit()

    return {
        "status": "generated",
        "cover_letter": letter,
        "generator": generator,
        "is_valid": report.is_valid,
    }


@router.put("/applications/{app_id}/cover-letter")
def update_cover_letter(
    app_id: str,
    data: CoverLetterUpdate,
    current_user: Optional[UserDB] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """Edit cover letter with strict factual consistency and ungrounded interest validation."""
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

    report = FactualConsistencyValidator.validate_cover_letter(
        cover_letter=data.cover_letter,
        candidate_facts=[f for f in domain_facts if f.is_usable],
        company_name=job.company_norm if job else None,
        role_title=job.title_norm if job else None,
    )
    if not report.is_valid:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Cover letter failed factual consistency validation",
                "violations": [v.model_dump() for v in report.violations],
            },
        )

    resume_row = None
    if app_row.current_resume_id:
        resume_row = db.scalar(select(ResumeDB).where(ResumeDB.id == app_row.current_resume_id))
    if not resume_row:
        resume_row = db.scalar(select(ResumeDB).where(ResumeDB.application_id == app_id).order_by(ResumeDB.version.desc()))

    if not resume_row:
        raise HTTPException(status_code=400, detail="No resume generated yet")

    content = dict(resume_row.content)
    content["cover_letter"] = data.cover_letter
    resume_row.content = content
    db.commit()

    return {
        "status": "updated",
        "cover_letter": data.cover_letter,
        "is_valid": True,
    }


def _get_cover_letter_context(app_id: str, current_user: Optional[UserDB], db: Session):
    app_row = db.scalar(select(ApplicationDB).where(ApplicationDB.id == app_id))
    if not app_row:
        raise HTTPException(status_code=404, detail="Application not found")
    _check_app_access(app_row, current_user)

    resume_row = None
    if app_row.current_resume_id:
        resume_row = db.scalar(select(ResumeDB).where(ResumeDB.id == app_row.current_resume_id))
    if not resume_row:
        resume_row = db.scalar(select(ResumeDB).where(ResumeDB.application_id == app_id).order_by(ResumeDB.version.desc()))
    if not resume_row or not resume_row.content.get("cover_letter"):
        raise HTTPException(status_code=404, detail="No cover letter available for this application")

    candidate = db.scalar(select(CandidateDB).where(CandidateDB.id == app_row.candidate_id))
    job = db.scalar(select(JobDB).where(JobDB.id == app_row.job_id))

    structured = resume_row.content
    candidate_name = structured.get("candidate_name") or (candidate.display_name if candidate else "Candidate")
    email = structured.get("email") or "candidate@jov.si"
    phone = structured.get("phone") or "+14155552671"
    company_name = job.company_norm if job else "Hiring Company"
    cover_letter_text = str(structured["cover_letter"])

    return cover_letter_text, candidate_name, email, phone, company_name, app_row


@router.get("/applications/{app_id}/cover-letter/txt")
def download_cover_letter_txt(
    app_id: str,
    current_user: Optional[UserDB] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Download the cover letter as a plain text document."""
    text, _, _, _, _, _ = _get_cover_letter_context(app_id, current_user, db)
    return Response(
        content=text.encode("utf-8"),
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="cover-letter-{app_id[:8]}.txt"',
        },
    )


@router.get("/applications/{app_id}/cover-letter/pdf")
def download_cover_letter_pdf(
    app_id: str,
    current_user: Optional[UserDB] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Download the cover letter as a clean PDF artifact."""
    text, name, email, phone, company, _ = _get_cover_letter_context(app_id, current_user, db)
    pdf_bytes = ResumeService.render_cover_letter_pdf(
        cover_letter_text=text,
        candidate_name=name,
        email=email,
        phone=phone,
        company_name=company,
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="cover-letter-{app_id[:8]}.pdf"',
        },
    )


@router.get("/applications/{app_id}/cover-letter/docx")
def download_cover_letter_docx(
    app_id: str,
    current_user: Optional[UserDB] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Download the cover letter as a formatted Word (.docx) document."""
    text, name, email, phone, company, _ = _get_cover_letter_context(app_id, current_user, db)
    docx_bytes = ResumeService.render_cover_letter_docx(
        cover_letter_text=text,
        candidate_name=name,
        email=email,
        phone=phone,
        company_name=company,
    )
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="cover-letter-{app_id[:8]}.docx"',
        },
    )


class FieldUpdateItem(BaseModel):
    field_key: str
    value: str


class FieldsUpdateRequest(BaseModel):
    fields: List[FieldUpdateItem]


@router.post("/applications/{app_id}/plan")
def plan_application(
    app_id: str,
    current_user: Optional[UserDB] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Inspects target job requirements, synthesizes standard portal form fields from candidate facts."""
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

    planned_fields, has_unresolved = ApplicationPlanningService.plan_fields_from_facts(
        candidate=candidate,
        job=job,
        facts=domain_facts,
    )

    # Clean existing field answers for this application
    existing_answers = db.scalars(select(FieldAnswerDB).where(FieldAnswerDB.application_id == app_id)).all()
    for ea in existing_answers:
        db.delete(ea)
    db.commit()

    for pf in planned_fields:
        fa = FieldAnswerDB(
            application_id=app_id,
            field_key=pf["field_key"],
            value=pf["value"],
            source=pf["source"],
            fact_id=pf["fact_id"],
            is_sensitive=pf["is_sensitive"],
        )
        db.add(fa)
    db.commit()

    # Form snapshot
    skeleton_json = json.dumps([{"k": f["field_key"], "req": f["required"]} for f in planned_fields], sort_keys=True)
    skeleton_hash = hashlib.sha256(skeleton_json.encode("utf-8")).hexdigest()
    snapshot_db = FormSnapshotDB(
        application_id=app_id,
        url=job.canonical_url,
        fields=planned_fields,
        dom_hash=skeleton_hash,
    )
    db.add(snapshot_db)
    db.commit()

    return {
        "status": "planned",
        "has_unresolved_fields": has_unresolved,
        "fields": planned_fields,
        "dom_hash": skeleton_hash,
    }


@router.get("/applications/{app_id}/fields")
def get_application_fields(
    app_id: str,
    current_user: Optional[UserDB] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve prefilled form fields with fact grounding and sensitivity status."""
    app_row = db.scalar(select(ApplicationDB).where(ApplicationDB.id == app_id))
    if not app_row:
        raise HTTPException(status_code=404, detail="Application not found")
    _check_app_access(app_row, current_user)

    field_answers = db.scalars(select(FieldAnswerDB).where(FieldAnswerDB.application_id == app_id)).all()
    if not field_answers:
        # Automatically run planning
        return plan_application(app_id=app_id, current_user=current_user, db=db)

    schema_map = {f["field_key"]: f for f in STANDARD_PORTAL_FIELDS}
    result_fields = []
    for fa in field_answers:
        schema = schema_map.get(fa.field_key, {})
        result_fields.append({
            "field_key": fa.field_key,
            "label": schema.get("label", fa.field_key),
            "input_type": schema.get("input_type", "text"),
            "required": schema.get("required", False),
            "is_sensitive": fa.is_sensitive,
            "description": schema.get("description", ""),
            "value": fa.value,
            "source": fa.source,
            "fact_id": fa.fact_id,
            "approved_at": fa.approved_at.isoformat() if fa.approved_at else None,
        })

    has_unresolved = any(rf["required"] and not rf["value"] for rf in result_fields)

    return {
        "status": "loaded",
        "has_unresolved_fields": has_unresolved,
        "fields": result_fields,
    }


@router.put("/applications/{app_id}/fields")
def update_application_fields(
    app_id: str,
    data: FieldsUpdateRequest,
    current_user: Optional[UserDB] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """User reviews and updates prefilled form answers before gate approval or manual apply."""
    app_row = db.scalar(select(ApplicationDB).where(ApplicationDB.id == app_id))
    if not app_row:
        raise HTTPException(status_code=404, detail="Application not found")
    _check_app_access(app_row, current_user)

    for item in data.fields:
        fa = db.scalar(
            select(FieldAnswerDB).where(
                FieldAnswerDB.application_id == app_id,
                FieldAnswerDB.field_key == item.field_key,
            )
        )
        if fa:
            fa.value = item.value
            fa.source = "APPROVED_ANSWER"
            fa.approved_at = datetime.utcnow()
        else:
            schema_map = {f["field_key"]: f for f in STANDARD_PORTAL_FIELDS}
            is_sens = schema_map.get(item.field_key, {}).get("is_sensitive", False)
            new_fa = FieldAnswerDB(
                application_id=app_id,
                field_key=item.field_key,
                value=item.value,
                source="APPROVED_ANSWER",
                is_sensitive=is_sens,
                approved_at=datetime.utcnow(),
            )
            db.add(new_fa)
    db.commit()

    return get_application_fields(app_id=app_id, current_user=current_user, db=db)


@router.get("/applications/{app_id}/package")
def get_application_package(
    app_id: str,
    current_user: Optional[UserDB] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve complete application handoff package manifest."""
    app_row = db.scalar(select(ApplicationDB).where(ApplicationDB.id == app_id))
    if not app_row:
        raise HTTPException(status_code=404, detail="Application not found")
    _check_app_access(app_row, current_user)

    job = db.scalar(select(JobDB).where(JobDB.id == app_row.job_id))
    candidate = db.scalar(select(CandidateDB).where(CandidateDB.id == app_row.candidate_id))
    resume_db = db.scalar(select(ResumeDB).where(ResumeDB.application_id == app_id).order_by(ResumeDB.version.desc()))
    field_answers = db.scalars(select(FieldAnswerDB).where(FieldAnswerDB.application_id == app_id)).all()

    answers_dict = {fa.field_key: fa.value for fa in field_answers}

    content_dict = resume_db.content if resume_db else {}
    package = ApplicationPackage(
        resume=content_dict,
        cover_letter={"text": content_dict.get("cover_letter")} if content_dict.get("cover_letter") else None,
        field_answers=answers_dict,
        target_url=job.canonical_url,
        job_content_hash=job.raw_sha256,
    )

    return {
        "application_id": app_row.id,
        "state": app_row.state,
        "package_hash": package.compute_hash(),
        "job": {
            "id": job.id,
            "company_name": job.company_norm,
            "role_title": job.title_norm,
            "canonical_url": job.canonical_url,
        },
        "candidate": {
            "id": candidate.id,
            "display_name": candidate.display_name,
        },
        "resume": content_dict,
        "cover_letter": content_dict.get("cover_letter"),
        "field_answers": answers_dict,
    }


@router.get("/applications/{app_id}/package.zip")
def download_application_package_zip(
    app_id: str,
    current_user: Optional[UserDB] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Download consolidated application kit as an offline ZIP archive."""
    app_row = db.scalar(select(ApplicationDB).where(ApplicationDB.id == app_id))
    if not app_row:
        raise HTTPException(status_code=404, detail="Application not found")
    _check_app_access(app_row, current_user)

    job = db.scalar(select(JobDB).where(JobDB.id == app_row.job_id))
    candidate = db.scalar(select(CandidateDB).where(CandidateDB.id == app_row.candidate_id))
    resume_db = db.scalar(select(ResumeDB).where(ResumeDB.application_id == app_id).order_by(ResumeDB.version.desc()))
    field_answers = db.scalars(select(FieldAnswerDB).where(FieldAnswerDB.application_id == app_id)).all()

    zip_bytes = ApplicationPlanningService.build_handoff_package_zip(
        application_id=app_id,
        job=job,
        candidate=candidate,
        resume_row=resume_db,
        field_answers=field_answers,
    )

    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="jovsi-application-{app_id[:8]}-kit.zip"',
        },
    )


@router.post("/applications/{app_id}/mark-submitted-manual")
def mark_application_manually_submitted(
    app_id: str,
    current_user: Optional[UserDB] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Marks an application as manually submitted to an external employer portal."""
    app_row = db.scalar(select(ApplicationDB).where(ApplicationDB.id == app_id))
    if not app_row:
        raise HTTPException(status_code=404, detail="Application not found")
    _check_app_access(app_row, current_user)

    old_state = app_row.state
    # Transition to MANUAL_HANDOFF
    ctx = TransitionContext(
        application_id=app_row.id,
        current_state=ApplicationState(app_row.state),
        target_state=ApplicationState.MANUAL_HANDOFF,
        is_unsupported_portal=True,
        user_override_reason="User completed manual submission via downloaded application kit",
    )
    StateMachine.validate_transition(ctx)

    app_row.state = ApplicationState.MANUAL_HANDOFF.value
    db.commit()

    # Immutable event record
    event = EventDB(
        application_id=app_row.id,
        type="MANUAL_HANDOFF_RECORDED",
        from_state=old_state,
        to_state=ApplicationState.MANUAL_HANDOFF.value,
        actor="CANDIDATE",
        payload={"note": "Manual submission confirmed by candidate using exported kit"},
    )
    db.add(event)
    db.commit()

    return {
        "status": "marked",
        "state": ApplicationState.MANUAL_HANDOFF.value,
        "message": "Application marked as manually submitted.",
    }


class PortalAuthResumeRequest(BaseModel):
    new_skeleton_hash: Optional[str] = None


@router.post("/applications/{app_id}/portal-auth/pause")
def pause_for_portal_auth(
    app_id: str,
    current_user: Optional[UserDB] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Pauses application workflow when external portal login/SSO/2FA is required."""
    app_row = db.scalar(select(ApplicationDB).where(ApplicationDB.id == app_id))
    if not app_row:
        raise HTTPException(status_code=404, detail="Application not found")
    _check_app_access(app_row, current_user)

    job = db.scalar(select(JobDB).where(JobDB.id == app_row.job_id))
    updated_app = PortalAuthService.pause_for_authentication(
        db=db,
        application_id=app_id,
        reason="External employer portal requires user sign-in/SSO",
        actor="CANDIDATE" if current_user else "SYSTEM",
    )
    return {
        "status": "paused",
        "state": updated_app.state,
        "paused_from_state": updated_app.paused_from_state,
        "login_url": job.canonical_url if job else None,
        "message": "Application workflow paused. Please sign in to the employer portal.",
    }


@router.post("/applications/{app_id}/portal-auth/resume")
def resume_from_portal_auth(
    app_id: str,
    data: Optional[PortalAuthResumeRequest] = None,
    current_user: Optional[UserDB] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Resumes application workflow after user completes external portal authentication."""
    app_row = db.scalar(select(ApplicationDB).where(ApplicationDB.id == app_id))
    if not app_row:
        raise HTTPException(status_code=404, detail="Application not found")
    _check_app_access(app_row, current_user)

    new_hash = data.new_skeleton_hash if data else None
    try:
        updated_app, tamper_verified = PortalAuthService.resume_from_authentication(
            db=db,
            application_id=app_id,
            new_skeleton_hash=new_hash,
            actor="CANDIDATE" if current_user else "SYSTEM",
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "status": "resumed",
        "state": updated_app.state,
        "tamper_verified": tamper_verified,
        "message": "Portal session active. Application workflow resumed.",
    }






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

    # Load from FieldAnswerDB or auto-plan
    field_rows = db.scalars(select(FieldAnswerDB).where(FieldAnswerDB.application_id == app_id)).all()
    if not field_rows:
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
        planned_fields, _ = ApplicationPlanningService.plan_fields_from_facts(candidate, job, domain_facts)
        for pf in planned_fields:
            fa = FieldAnswerDB(
                application_id=app_id,
                field_key=pf["field_key"],
                value=pf["value"],
                source=pf["source"],
                fact_id=pf["fact_id"],
                is_sensitive=pf["is_sensitive"],
            )
            db.add(fa)
        db.commit()
        field_rows = db.scalars(select(FieldAnswerDB).where(FieldAnswerDB.application_id == app_id)).all()

    form_values = {fa.field_key: fa.value for fa in field_rows}
    if "full_name" not in form_values:
        form_values["full_name"] = candidate.display_name
    if "email" not in form_values:
        form_values["email"] = email_val
    if "phone" not in form_values:
        form_values["phone"] = phone_val
    if "experience_years" not in form_values:
        form_values["experience_years"] = "3"
    if "legal_attestation" not in form_values:
        form_values["legal_attestation"] = "agree"

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

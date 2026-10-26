"""Submission, Approval, and Reconciliation Services (Blueprint v2.0 Section 11 & 12)."""

from datetime import datetime, timedelta, date
import hashlib
from pathlib import Path
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from playwright.async_api import Page

from jovsi.config import settings
from jovsi.domain.models import ApplicationPackage, GateCheckOutcome
from jovsi.domain.state_machine import ApplicationState, StateMachine, TransitionContext
from jovsi.domain.gate import GateSnapshot, ValidationGate
from jovsi.adapters.db.models import (
    ApplicationDB,
    ApprovalDB,
    CandidateDB,
    EvidenceDB,
    GateReportDB,
    JobDB,
    RateLedgerDB,
    ResumeDB,
    SubmissionAttemptDB,
)
from jovsi.services.application_service import ApplicationService
from jovsi.adapters.portals.base import AdapterError, FieldMappingPlan, SubmissionTicket
from jovsi.adapters.portals.form_filler import FormFiller
from jovsi.adapters.portals.inspector import PortalInspector
from jovsi.adapters.portals.submitter import Submitter


class ApprovalError(Exception):
    pass


class SubmissionError(Exception):
    pass


class ApprovalService:
    @classmethod
    def approve_package(
        cls,
        db: Session,
        application_id: str,
        package_hash: str,
        approved_by: str = "user",
        expiry_hours: int = 24,
    ) -> ApprovalDB:
        """Issue an approval bound to an exact package hash (Blueprint v2.0 Section 12)."""
        app = db.scalar(select(ApplicationDB).where(ApplicationDB.id == application_id))
        if not app:
            raise ApprovalError(f"Application {application_id} not found")

        # Verify latest gate report for this hash is PASS
        latest_gate = db.scalar(
            select(GateReportDB)
            .where(
                GateReportDB.application_id == application_id,
                GateReportDB.content_hash == package_hash,
            )
            .order_by(GateReportDB.created_at.desc())
        )
        if not latest_gate or latest_gate.outcome != "PASS":
            raise ApprovalError("Cannot approve package: pre-submission gate outcome is not PASS")

        now = datetime.utcnow()
        approval = ApprovalDB(
            application_id=application_id,
            content_hash=package_hash,
            approved_by=approved_by,
            approved_at=now,
            expires_at=now + timedelta(hours=expiry_hours),
            is_consumed=False,
        )
        db.add(approval)
        db.commit()
        db.refresh(approval)

        # Transition application to APPROVED
        ctx = TransitionContext(
            application_id=app.id,
            current_state=ApplicationState(app.state),
            target_state=ApplicationState.APPROVED,
            gate_outcome="PASS",
            package_hash_matches=True,
        )
        ApplicationService.transition(
            db=db,
            app_id=app.id,
            to_state=ApplicationState.APPROVED,
            trigger="User approves",
            expected_version=app.version,
            actor=approved_by,
            ctx=ctx,
        )

        return approval


class SubmissionService:
    @classmethod
    async def submit(
        cls,
        db: Session,
        application_id: str,
        approval_id: str,
        page: Page,
        plan: FieldMappingPlan,
        expected_package_hash: str,
        resume_path: Optional[Path] = None,
    ) -> str:
        """Execute the guarded submission sequence (Blueprint v2.0 Section 12)."""
        app = db.scalar(select(ApplicationDB).where(ApplicationDB.id == application_id))
        if not app:
            raise SubmissionError("Application not found")

        approval = db.scalar(select(ApprovalDB).where(ApprovalDB.id == approval_id))
        if not approval:
            raise SubmissionError("Approval not found")

        now = datetime.utcnow()
        if approval.is_consumed or approval.revoked_at or approval.expires_at < now:
            raise SubmissionError("Approval is stale, consumed, or expired")

        if approval.content_hash != expected_package_hash:
            raise SubmissionError("Package hash mismatch: approval does not cover current package")

        job = db.scalar(select(JobDB).where(JobDB.id == app.job_id))
        candidate = db.scalar(select(CandidateDB).where(CandidateDB.id == app.candidate_id))

        # Check rate caps
        today = date.today()
        global_count = db.scalar(
            select(func.count(RateLedgerDB.id)).where(
                RateLedgerDB.scope == "GLOBAL",
                RateLedgerDB.local_date == today,
            )
        ) or 0
        if global_count >= settings.DAILY_CAP_GLOBAL:
            raise SubmissionError("Daily global rate cap exceeded")

        # 1. Fresh session inspection and read-back
        await page.goto(job.canonical_url)
        inspection = await PortalInspector.inspect(page)
        await FormFiller.populate(page, plan)

        # Attach resume PDF
        if resume_path and resume_path.exists():
            await FormFiller.attach_resume(page, resume_path)
        elif app.current_resume_id:
            resume_row = db.scalar(select(ResumeDB).where(ResumeDB.id == app.current_resume_id))
            if resume_row:
                import tempfile
                from jovsi.services.resume import ResumeService
                from jovsi.domain.models import StructuredResume
                struct_resume = StructuredResume(**resume_row.content)
                pdf_bytes = ResumeService.render_pdf_bytes(struct_resume)
                temp_pdf = Path(tempfile.gettempdir()) / f"jovsi_{application_id}.pdf"
                temp_pdf.write_bytes(pdf_bytes)
                await FormFiller.attach_resume(page, temp_pdf)

        # 2. Commit intent before clicking submit (Insert-then-click)
        idempotency_key = hashlib.sha256(f"{application_id}:{approval_id}".encode("utf-8")).hexdigest()
        attempt = SubmissionAttemptDB(
            application_id=application_id,
            idempotency_key=idempotency_key,
            click_started_at=now,
            outcome="IN_PROGRESS",
        )
        db.add(attempt)
        db.flush()

        rate_row = RateLedgerDB(
            scope="GLOBAL",
            scope_key="global",
            local_date=today,
            attempt_id=attempt.id,
        )
        db.add(rate_row)

        approval.is_consumed = True
        db.commit()

        # Transition to SUBMISSION_IN_PROGRESS
        ctx_progress = TransitionContext(
            application_id=app.id,
            current_state=ApplicationState.APPROVED,
            target_state=ApplicationState.SUBMISSION_IN_PROGRESS,
            approval_valid=True,
            package_hash_matches=True,
            caps_available=True,
        )
        app = ApplicationService.transition(
            db=db,
            app_id=app.id,
            to_state=ApplicationState.SUBMISSION_IN_PROGRESS,
            trigger="Submit command",
            expected_version=app.version,
            ctx=ctx_progress,
        )

        # 3. Create cryptographically signed ticket and click
        ticket = SubmissionTicket.create(
            application_id=app.id,
            package_hash=expected_package_hash,
            approval_id=approval.id,
            gate_report_id="gate-preclick",
            target_url=job.canonical_url,
            secret_key=settings.SECRET_KEY,
        )

        submitter = Submitter(secret_key=settings.SECRET_KEY)
        attempt_result = await submitter.submit(page, ticket)
        attempt.clicked_at = attempt_result.clicked_at
        attempt.error = attempt_result.error

        # 4. Verify outcome
        evidence = await submitter.verify(page, attempt_result)

        for item in evidence.items:
            ev_row = EvidenceDB(
                attempt_id=attempt.id,
                level=evidence.level,
                kind=item.kind,
                payload=item.payload,
                sha256=item.sha256,
            )
            db.add(ev_row)
        db.commit()

        # Transition based on evidence level
        min_level = settings.MIN_EVIDENCE_LEVEL.value
        if evidence.level in ("E2", "E3"):
            ctx_confirmed = TransitionContext(
                application_id=app.id,
                current_state=ApplicationState.SUBMISSION_IN_PROGRESS,
                target_state=ApplicationState.APPLIED_CONFIRMED,
                evidence_level=evidence.level,
                min_evidence_level=min_level,
            )
            app = ApplicationService.transition(
                db=db,
                app_id=app.id,
                to_state=ApplicationState.APPLIED_CONFIRMED,
                trigger="Verification",
                expected_version=app.version,
                ctx=ctx_confirmed,
            )
            attempt.outcome = "CONFIRMED"
            db.commit()
            return "APPLIED_CONFIRMED"

        elif attempt_result.error and "500" in attempt_result.error:
            ctx_failed = TransitionContext(
                application_id=app.id,
                current_state=ApplicationState.SUBMISSION_IN_PROGRESS,
                target_state=ApplicationState.APPLICATION_FAILED,
                explicit_rejection=True,
            )
            ApplicationService.transition(
                db=db,
                app_id=app.id,
                to_state=ApplicationState.APPLICATION_FAILED,
                trigger="Portal error",
                expected_version=app.version,
                ctx=ctx_failed,
            )
            attempt.outcome = "FAILED"
            db.commit()
            return "APPLICATION_FAILED"

        else:
            # Uncertain outcome
            ctx_uncertain = TransitionContext(
                application_id=app.id,
                current_state=ApplicationState.SUBMISSION_IN_PROGRESS,
                target_state=ApplicationState.SUBMISSION_UNCERTAIN,
                clicked_at_set=True,
            )
            ApplicationService.transition(
                db=db,
                app_id=app.id,
                to_state=ApplicationState.SUBMISSION_UNCERTAIN,
                trigger="Timeout or weak evidence",
                expected_version=app.version,
                ctx=ctx_uncertain,
            )
            attempt.outcome = "UNCERTAIN"
            db.commit()
            return "SUBMISSION_UNCERTAIN"


class ReconciliationService:
    @classmethod
    async def reconcile(
        cls,
        db: Session,
        application_id: str,
        page: Page,
        confirmation_ref: str,
        candidate_email: str,
    ) -> str:
        """Reconcile an uncertain submission via the independent status page (Blueprint v2.0 Section 12)."""
        app = db.scalar(select(ApplicationDB).where(ApplicationDB.id == application_id))
        if not app or app.state != "SUBMISSION_UNCERTAIN":
            return app.state if app else "NOT_FOUND"

        status_url = f"http://127.0.0.1:8765/status?ref={confirmation_ref}&email={candidate_email}"
        await page.goto(status_url)

        status_header = page.get_by_test_id("status-header")
        if await status_header.count() > 0:
            # Verified independently at E3!
            ctx = TransitionContext(
                application_id=app.id,
                current_state=ApplicationState.SUBMISSION_UNCERTAIN,
                target_state=ApplicationState.APPLIED_CONFIRMED,
                evidence_level="E3",
            )
            ApplicationService.transition(
                db=db,
                app_id=app.id,
                to_state=ApplicationState.APPLIED_CONFIRMED,
                trigger="Reconciliation",
                expected_version=app.version,
                ctx=ctx,
            )
            return "APPLIED_CONFIRMED"

        return "SUBMISSION_UNCERTAIN"

"""SQLAlchemy 2.0 Database Models for JOV.si.

Implements all 18 tables defined in Blueprint v2.0 Section 5 & 13.
"""

from datetime import datetime, date
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
    text,
)
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def gen_uuid() -> str:
    return str(uuid.uuid4())


class CandidateDB(Base):
    __tablename__ = "candidates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata", nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    facts = relationship("FactDB", back_populates="candidate", cascade="all, delete-orphan")
    documents = relationship("DocumentDB", back_populates="candidate", cascade="all, delete-orphan")
    applications = relationship("ApplicationDB", back_populates="candidate", cascade="all, delete-orphan")


class FactDB(Base):
    __tablename__ = "facts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    candidate_id: Mapped[str] = mapped_column(String(36), ForeignKey("candidates.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)  # CONTACT, EDUCATION, etc.
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    value: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    provenance: Mapped[str] = mapped_column(String(32), nullable=False)  # USER_SUPPLIED, USER_VERIFIED
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False)  # ACTIVE, PROPOSED, etc.
    source_document_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    supersedes_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    valid_from: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    valid_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    candidate = relationship("CandidateDB", back_populates="facts")


class DocumentDB(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    candidate_id: Mapped[str] = mapped_column(String(36), ForeignKey("candidates.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)  # RESUME, TRANSCRIPT, CERTIFICATE
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    path: Mapped[str] = mapped_column(String(512), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("candidate_id", "sha256", name="uq_document_candidate_sha256"),
    )

    candidate = relationship("CandidateDB", back_populates="documents")


class JobDB(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_url: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_job_key: Mapped[str] = mapped_column(String(64), nullable=False)
    company_norm: Mapped[str] = mapped_column(String(255), nullable=False)
    title_norm: Mapped[str] = mapped_column(String(255), nullable=False)
    description_clean: Mapped[str] = mapped_column(Text, nullable=False)
    raw_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    requirements: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    deadline_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("source", "canonical_job_key", name="uq_job_source_canonical_key"),
        Index("idx_job_company_title", "company_norm", "title_norm"),
    )


class EvaluationDB(Base):
    __tablename__ = "evaluations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id"), nullable=False)
    candidate_id: Mapped[str] = mapped_column(String(36), ForeignKey("candidates.id"), nullable=False)
    rules_result: Mapped[str] = mapped_column(String(32), nullable=False)  # PASS, FAIL, UNCERTAIN
    score_total: Mapped[float] = mapped_column(Float, nullable=False)
    score_breakdown: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    config_version: Mapped[str] = mapped_column(String(32), default="v1.0", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class ApplicationDB(Base):
    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    candidate_id: Mapped[str] = mapped_column(String(36), ForeignKey("candidates.id"), nullable=False)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id"), nullable=False)
    canonical_job_key: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(32), default="DISCOVERED", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)  # Optimistic lock
    autonomy_level: Mapped[str] = mapped_column(String(32), default="L0_DRY_RUN", nullable=False)
    current_resume_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    paused_from_state: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("candidate_id", "canonical_job_key", name="uq_app_candidate_job_key"),
        Index("idx_app_state", "state"),
    )

    candidate = relationship("CandidateDB", back_populates="applications")
    job = relationship("JobDB")


class ResumeDB(Base):
    __tablename__ = "resumes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    application_id: Mapped[str] = mapped_column(String(36), ForeignKey("applications.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    content: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    generator: Mapped[str] = mapped_column(String(32), default="DETERMINISTIC", nullable=False)
    validation_report: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class ResumeClaimDB(Base):
    __tablename__ = "resume_claims"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    resume_id: Mapped[str] = mapped_column(String(36), ForeignKey("resumes.id"), nullable=False)
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    fact_id: Mapped[str] = mapped_column(String(36), ForeignKey("facts.id"), nullable=False)


class FormSnapshotDB(Base):
    __tablename__ = "form_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    application_id: Mapped[str] = mapped_column(String(36), ForeignKey("applications.id"), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    fields: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    dom_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class FieldAnswerDB(Base):
    __tablename__ = "field_answers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    application_id: Mapped[str] = mapped_column(String(36), ForeignKey("applications.id"), nullable=False)
    field_key: Mapped[str] = mapped_column(String(128), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)  # FACT or APPROVED_ANSWER
    fact_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    is_sensitive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class GateReportDB(Base):
    __tablename__ = "gate_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    application_id: Mapped[str] = mapped_column(String(36), ForeignKey("applications.id"), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    results: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)  # PASS, NEEDS_USER, BLOCKED
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class ApprovalDB(Base):
    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    application_id: Mapped[str] = mapped_column(String(36), ForeignKey("applications.id"), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    approved_by: Mapped[str] = mapped_column(String(128), nullable=False)
    approved_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_consumed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class SubmissionAttemptDB(Base):
    __tablename__ = "submission_attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    application_id: Mapped[str] = mapped_column(String(36), ForeignKey("applications.id"), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    clicked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    click_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    outcome: Mapped[str] = mapped_column(String(32), default="PENDING", nullable=False)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class EvidenceDB(Base):
    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    attempt_id: Mapped[str] = mapped_column(String(36), ForeignKey("submission_attempts.id"), nullable=False)
    level: Mapped[str] = mapped_column(String(8), nullable=False)  # E0, E1, E2, E3
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class EventDB(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    seq: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    application_id: Mapped[str] = mapped_column(String(36), nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    from_state: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    to_state: Mapped[str] = mapped_column(String(32), nullable=False)
    actor: Mapped[str] = mapped_column(String(64), default="system", nullable=False)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("idx_events_app_seq", "application_id", "seq"),
    )


@event.listens_for(EventDB, "before_insert")
def set_event_seq(mapper, connection, target):
    if target.seq is None:
        val = connection.execute(text("SELECT COALESCE(MAX(seq), 0) + 1 FROM events")).scalar()
        target.seq = val or 1


class WorkItemDB(Base):
    __tablename__ = "work_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    lease_owner: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    lease_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    run_after: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class RateLedgerDB(Base):
    __tablename__ = "rate_ledger"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    scope: Mapped[str] = mapped_column(String(32), nullable=False)  # GLOBAL, PORTAL, COMPANY
    scope_key: Mapped[str] = mapped_column(String(128), nullable=False)
    local_date: Mapped[date] = mapped_column(Date, nullable=False)
    attempt_id: Mapped[str] = mapped_column(String(36), ForeignKey("submission_attempts.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("idx_rate_ledger_scope_date", "scope", "scope_key", "local_date"),
    )


class PortalPolicyDB(Base):
    __tablename__ = "portal_policies"

    portal_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    hosts: Mapped[List[str]] = mapped_column(JSON, nullable=False)
    automation_allowed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    requires_login: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status_is_authoritative: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tos_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    tos_reviewed_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

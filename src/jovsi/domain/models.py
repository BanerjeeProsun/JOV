"""JOV.si Core Domain Models.

Pure Python & Pydantic v2. Zero external I/O or database dependencies.
Enforces all constraints and data structures from Blueprint v2.0 Section 5 and Section 6.
"""

from datetime import datetime, date
from enum import Enum
import hashlib
import json
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class FactKind(str, Enum):
    CONTACT = "CONTACT"
    EDUCATION = "EDUCATION"
    EXPERIENCE = "EXPERIENCE"
    PROJECT = "PROJECT"
    SKILL = "SKILL"
    CERTIFICATION = "CERTIFICATION"
    WORK_AUTH = "WORK_AUTH"
    PREFERENCE = "PREFERENCE"


class FactProvenance(str, Enum):
    USER_SUPPLIED = "USER_SUPPLIED"
    USER_VERIFIED = "USER_VERIFIED"


class FactStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PROPOSED = "PROPOSED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


class Fact(BaseModel):
    id: str
    candidate_id: str
    kind: FactKind
    key: str
    value: Dict[str, Any]
    provenance: FactProvenance
    status: FactStatus = FactStatus.ACTIVE
    source_document_id: Optional[str] = None
    verified_at: Optional[datetime] = None
    supersedes_id: Optional[str] = None
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None

    @property
    def is_usable(self) -> bool:
        """Only ACTIVE facts with valid provenance are usable in generated resumes/answers."""
        return self.status == FactStatus.ACTIVE and self.provenance in (
            FactProvenance.USER_SUPPLIED,
            FactProvenance.USER_VERIFIED,
        )


class Candidate(BaseModel):
    id: str
    display_name: str
    timezone: str = "Asia/Kolkata"
    is_synthetic: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)


class JobStatus(str, Enum):
    ACTIVE = "ACTIVE"
    LINK_INVALID = "LINK_INVALID"
    EXPIRED = "EXPIRED"


class DegreeLevel(str, Enum):
    DIPLOMA = "DIPLOMA"
    BACHELOR = "BACHELOR"
    MASTER = "MASTER"
    DOCTORATE = "DOCTORATE"


class JobRequirements(BaseModel):
    min_degree: Optional[DegreeLevel] = None
    allowed_graduation_years: Optional[List[int]] = None
    min_experience_months: Optional[int] = None
    work_auth_countries: Optional[List[str]] = None
    mandatory_certifications: Optional[List[str]] = None
    required_skills: List[str] = Field(default_factory=list)
    preferred_skills: List[str] = Field(default_factory=list)
    responsibilities: List[str] = Field(default_factory=list)
    target_role_family: Optional[str] = None
    target_seniority: Optional[str] = None
    accepted_work_modes: List[str] = Field(default_factory=lambda: ["remote", "hybrid", "onsite"])
    target_locations: List[str] = Field(default_factory=list)
    deadline: Optional[datetime] = None
    extraction_confidence: float = 1.0


class Job(BaseModel):
    id: str
    source: str
    source_url: str
    canonical_url: str
    canonical_job_key: str
    company_norm: str
    title_norm: str
    description_clean: str
    raw_sha256: str
    requirements: JobRequirements = Field(default_factory=JobRequirements)
    deadline_at: Optional[datetime] = None
    status: JobStatus = JobStatus.ACTIVE
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @classmethod
    def compute_canonical_key(
        cls,
        company_norm: str,
        title_norm: str,
        location_norm: str = "",
        portal_key: Optional[str] = None,
        native_id: Optional[str] = None,
    ) -> str:
        """Compute canonical key as specified in Blueprint Section 5."""
        if portal_key and native_id:
            payload = f"{portal_key.strip().lower()}:{native_id.strip().lower()}"
        else:
            payload = f"{company_norm.strip().lower()}:{title_norm.strip().lower()}:{location_norm.strip().lower()}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class GateCheckOutcome(str, Enum):
    PASS = "PASS"
    NEEDS_USER = "NEEDS_USER"
    BLOCKED = "BLOCKED"
    WARN = "WARN"


class GateCheckResult(BaseModel):
    check_id: int
    name: str
    outcome: GateCheckOutcome
    code: str
    message: str
    observed: Optional[Any] = None
    expected: Optional[Any] = None
    evidence_ref: Optional[str] = None


class GateReport(BaseModel):
    id: str
    application_id: str
    content_hash: str
    outcome: GateCheckOutcome  # BLOCKED > NEEDS_USER > PASS
    results: List[GateCheckResult]
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def is_pass(self) -> bool:
        return self.outcome == GateCheckOutcome.PASS


class ResumeBullet(BaseModel):
    text: str
    fact_ids: List[str]

    @field_validator("fact_ids")
    @classmethod
    def must_not_be_empty(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("A resume bullet must cite at least one verified fact_id")
        return v


class ResumeSection(BaseModel):
    title: str
    bullets: List[ResumeBullet] = Field(default_factory=list)


class StructuredResume(BaseModel):
    candidate_name: str
    email: str
    phone: str
    sections: List[ResumeSection] = Field(default_factory=list)


class ApplicationPackage(BaseModel):
    resume: Dict[str, Any]
    cover_letter: Optional[Dict[str, Any]] = None
    field_answers: Dict[str, Any]
    target_url: str
    job_content_hash: str

    def compute_hash(self) -> str:
        """Compute the cryptographic package hash H = SHA-256(canonical JSON)."""
        data = {
            "resume": self.resume,
            "cover_letter": self.cover_letter,
            "field_answers": self.field_answers,
            "target_url": self.target_url,
            "job_content_hash": self.job_content_hash,
        }
        canonical_json = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

"""Pydantic API Request/Response Schemas."""

from datetime import datetime, date
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from jovsi.domain.models import DegreeLevel, FactKind, FactProvenance, FactStatus, JobStatus


class CandidateCreate(BaseModel):
    display_name: str
    timezone: str = "Asia/Kolkata"
    is_synthetic: bool = False


class CandidateResponse(BaseModel):
    id: str
    display_name: str
    timezone: str
    is_synthetic: bool
    created_at: datetime


class FactCreate(BaseModel):
    kind: FactKind
    key: str
    value: Dict[str, Any]
    source_document_id: Optional[str] = None
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None


class FactResponse(BaseModel):
    id: str
    candidate_id: str
    kind: FactKind
    key: str
    value: Dict[str, Any]
    provenance: FactProvenance
    status: FactStatus
    source_document_id: Optional[str] = None
    verified_at: Optional[datetime] = None
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    is_usable: bool


class JobImportRequest(BaseModel):
    source: str = "manual_import"
    source_url: str
    canonical_url: Optional[str] = None
    company_name: str
    title: str
    raw_description: str
    portal_key: Optional[str] = None
    native_id: Optional[str] = None
    min_degree: Optional[DegreeLevel] = None
    allowed_graduation_years: Optional[List[int]] = None
    min_experience_months: Optional[int] = None
    work_auth_countries: Optional[List[str]] = None
    mandatory_certifications: Optional[List[str]] = None
    required_skills: List[str] = Field(default_factory=list)
    preferred_skills: List[str] = Field(default_factory=list)
    responsibilities: List[str] = Field(default_factory=list)
    accepted_work_modes: List[str] = Field(default_factory=lambda: ["remote", "hybrid", "onsite"])
    target_locations: List[str] = Field(default_factory=list)
    deadline_at: Optional[datetime] = None


class JobResponse(BaseModel):
    id: str
    source: str
    source_url: str
    canonical_url: str
    canonical_job_key: str
    company_norm: str
    title_norm: str
    description_clean: str
    raw_sha256: str
    requirements: Dict[str, Any]
    deadline_at: Optional[datetime] = None
    status: JobStatus
    created_at: datetime


class FactUpdate(BaseModel):
    key: Optional[str] = None
    value: Dict[str, Any]


class MasterResumeResponse(BaseModel):
    document_id: str
    candidate_id: str
    filename: str
    sha256: str
    uploaded_at: datetime
    entities: Dict[str, Any]
    total_facts_extracted: int
    proposed_facts: List[FactResponse]


class MasterResumeStatusResponse(BaseModel):
    has_master_resume: bool
    document_id: Optional[str] = None
    filename: Optional[str] = None
    sha256: Optional[str] = None
    uploaded_at: Optional[datetime] = None
    total_facts: int = 0
    active_facts: int = 0
    proposed_facts: int = 0


class UserRegisterRequest(BaseModel):
    email: str
    password: str
    display_name: str = ""
    timezone: str = "Asia/Kolkata"


class UserLoginRequest(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: str
    is_verified: bool
    is_active: bool
    role: str
    created_at: datetime


class UserProfileUpdate(BaseModel):
    display_name: Optional[str] = None
    timezone: Optional[str] = None


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


class PasswordResetRequest(BaseModel):
    email: str


class PasswordResetSubmit(BaseModel):
    token: str
    new_password: str


class EmailVerificationSubmit(BaseModel):
    token: str


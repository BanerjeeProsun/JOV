"""Base protocols, data structures, and errors for Portal Adapters (Blueprint v2.0 Section 10)."""

from datetime import datetime
from enum import Enum
import hashlib
import hmac
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PageKind(str, Enum):
    FORM = "FORM"
    LOGIN = "LOGIN"
    CAPTCHA = "CAPTCHA"
    CONFIRMATION = "CONFIRMATION"
    ERROR = "ERROR"
    NOT_FOUND = "NOT_FOUND"
    ALREADY_APPLIED = "ALREADY_APPLIED"


class FieldSensitivity(str, Enum):
    NONE = "NONE"
    SENSITIVE = "SENSITIVE"
    LEGAL = "LEGAL"


class LocatorStrategy(str, Enum):
    ROLE = "ROLE"
    LABEL = "LABEL"
    PLACEHOLDER = "PLACEHOLDER"
    TEST_ID = "TEST_ID"


class FormLocator(BaseModel):
    strategy: LocatorStrategy
    value: str


class FormFieldSchema(BaseModel):
    key: str
    label: str
    role: str
    input_type: str
    required: bool
    options: List[str] = Field(default_factory=list)
    max_length: Optional[int] = None
    accept: Optional[str] = None
    sensitivity: FieldSensitivity = FieldSensitivity.NONE
    locator: FormLocator


class PageInspection(BaseModel):
    portal_key: str
    url: str
    page_kind: PageKind
    requires_auth: bool = False
    form_skeleton_hash: str
    role_title: Optional[str] = None
    company_name: Optional[str] = None
    fields: List[FormFieldSchema] = Field(default_factory=list)


class FieldMappingEntry(BaseModel):
    field_key: str
    value: str
    source: str  # FACT or APPROVED_ANSWER
    fact_id: Optional[str] = None


class FieldMappingPlan(BaseModel):
    entries: List[FieldMappingEntry] = Field(default_factory=list)
    unresolved_keys: List[str] = Field(default_factory=list)


class PopulationResult(BaseModel):
    filled_keys: List[str]
    skipped_keys: List[str]
    read_back_values: Dict[str, str]


class SubmissionTicket(BaseModel):
    """Cryptographically signed submission ticket (Blueprint v2.0 Section 10)."""
    application_id: str
    package_hash: str
    approval_id: str
    gate_report_id: str
    target_url: str
    hmac_signature: str

    @classmethod
    def create(
        cls,
        application_id: str,
        package_hash: str,
        approval_id: str,
        gate_report_id: str,
        target_url: str,
        secret_key: str,
    ) -> "SubmissionTicket":
        payload = f"{application_id}:{package_hash}:{approval_id}:{gate_report_id}:{target_url}"
        sig = hmac.new(secret_key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
        return cls(
            application_id=application_id,
            package_hash=package_hash,
            approval_id=approval_id,
            gate_report_id=gate_report_id,
            target_url=target_url,
            hmac_signature=sig,
        )

    def verify(self, secret_key: str) -> bool:
        payload = f"{self.application_id}:{self.package_hash}:{self.approval_id}:{self.gate_report_id}:{self.target_url}"
        expected = hmac.new(secret_key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
        return hmac.compare_digest(self.hmac_signature, expected)


class SubmissionAttemptResult(BaseModel):
    attempt_id: str
    clicked_at: Optional[datetime] = None
    navigation_observed: bool = False
    http_status: Optional[int] = None
    error: Optional[str] = None
    current_url: Optional[str] = None


class EvidenceItem(BaseModel):
    kind: str
    payload: Dict[str, Any]
    sha256: str
    artifact_path: Optional[str] = None


class VerificationEvidence(BaseModel):
    level: str  # E0, E1, E2, E3
    items: List[EvidenceItem] = Field(default_factory=list)
    confirmation_ref: Optional[str] = None


class AdapterError(Exception):
    pass

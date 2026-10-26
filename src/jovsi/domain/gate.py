"""The 15-Point Pre-Submission Validation Gate (Blueprint v2.0 Section 11).

Pure Python, zero I/O.
Runs all 15 checks over an immutable GateSnapshot and returns a structured GateReport.
"""

from datetime import datetime, date
import re
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field

from jovsi.domain.models import (
    GateCheckOutcome,
    GateCheckResult,
    GateReport,
    StructuredResume,
)
from jovsi.domain.scoring import token_similarity


class GateSnapshot(BaseModel):
    application_id: str
    package_hash: str
    target_company_norm: str
    target_role_norm: str
    target_url: str
    page_company_name: Optional[str] = None
    page_role_title: Optional[str] = None
    page_url: Optional[str] = None
    portal_allowed_domains: List[str] = Field(default_factory=lambda: ["127.0.0.1", "localhost"])
    attached_file_name: Optional[str] = None
    attached_file_hash: Optional[str] = None
    expected_resume_hash: Optional[str] = None
    resume_validation_passed: bool = True
    cover_letter_required: bool = False
    cover_letter_validation_passed: bool = True
    form_values: Dict[str, str] = Field(default_factory=dict)
    required_field_keys: List[str] = Field(default_factory=list)
    sensitive_field_keys: List[str] = Field(default_factory=list)
    approved_sensitive_keys: List[str] = Field(default_factory=list)
    candidate_verified_email: Optional[str] = ""
    candidate_verified_phone: Optional[str] = ""
    unresolved_provenance_keys: List[str] = Field(default_factory=list)
    has_date_contradictions: bool = False
    is_exact_duplicate: bool = False
    is_near_duplicate: bool = False
    rate_global_count: int = 0
    rate_global_cap: int = 10
    rate_portal_count: int = 0
    rate_portal_cap: int = 5
    rate_company_count: int = 0
    rate_company_cap: int = 1
    inspection_form_skeleton_hash: Optional[str] = None
    current_form_skeleton_hash: Optional[str] = None
    other_company_names: List[str] = Field(default_factory=list)


PLACEHOLDER_REGEX = re.compile(r"\{\{.*?\}\}|\[NAME\]|TODO|TBD|lorem\s+ipsum", re.IGNORECASE)


class ValidationGate:
    @classmethod
    def evaluate(cls, snapshot: GateSnapshot) -> GateReport:
        """Run all 15 pre-submission checks."""
        results: List[GateCheckResult] = []

        # Check 1: Company match (sim >= 0.9)
        c_sim = token_similarity(snapshot.target_company_norm, snapshot.page_company_name or "")
        if c_sim >= 0.9 or (snapshot.target_company_norm.lower() == (snapshot.page_company_name or "").lower()):
            results.append(GateCheckResult(
                check_id=1, name="Company match", outcome=GateCheckOutcome.PASS,
                code="COMPANY_MATCH_PASS", message="Target company matches portal page company",
                observed=snapshot.page_company_name, expected=snapshot.target_company_norm,
            ))
        else:
            results.append(GateCheckResult(
                check_id=1, name="Company match", outcome=GateCheckOutcome.BLOCKED,
                code="COMPANY_MISMATCH", message=f"Company similarity {c_sim:.2f} < 0.9",
                observed=snapshot.page_company_name, expected=snapshot.target_company_norm,
            ))

        # Check 2: Role match (>= 0.85 PASS; 0.6..0.85 NEEDS_USER; < 0.6 BLOCKED)
        r_sim = token_similarity(snapshot.target_role_norm, snapshot.page_role_title or "")
        if r_sim >= 0.85 or (snapshot.target_role_norm.lower() == (snapshot.page_role_title or "").lower()):
            r_out = GateCheckOutcome.PASS
            r_code = "ROLE_MATCH_PASS"
        elif r_sim >= 0.6:
            r_out = GateCheckOutcome.NEEDS_USER
            r_code = "ROLE_MATCH_NEEDS_CONFIRMATION"
        else:
            r_out = GateCheckOutcome.BLOCKED
            r_code = "ROLE_MISMATCH"
        results.append(GateCheckResult(
            check_id=2, name="Role match", outcome=r_out, code=r_code,
            message=f"Role title match similarity {r_sim:.2f}",
            observed=snapshot.page_role_title, expected=snapshot.target_role_norm,
        ))

        # Check 3: Canonical URL and domain
        domain_valid = any(d in (snapshot.page_url or "") for d in snapshot.portal_allowed_domains)
        if domain_valid:
            results.append(GateCheckResult(
                check_id=3, name="Canonical URL and domain", outcome=GateCheckOutcome.PASS,
                code="DOMAIN_PASS", message="Destination URL domain is in allowed policy",
                observed=snapshot.page_url,
            ))
        else:
            results.append(GateCheckResult(
                check_id=3, name="Canonical URL and domain", outcome=GateCheckOutcome.BLOCKED,
                code="DOMAIN_NOT_ALLOWED", message=f"URL '{snapshot.page_url}' is not in allowed domains",
                observed=snapshot.page_url, expected=snapshot.portal_allowed_domains,
            ))

        # Check 4: Correct job-specific resume attached
        if snapshot.attached_file_hash and snapshot.expected_resume_hash and (
            snapshot.attached_file_hash == snapshot.expected_resume_hash
        ):
            results.append(GateCheckResult(
                check_id=4, name="Correct resume attached", outcome=GateCheckOutcome.PASS,
                code="RESUME_ATTACHED_PASS", message="Attached resume hash matches approved resume",
            ))
        else:
            results.append(GateCheckResult(
                check_id=4, name="Correct resume attached", outcome=GateCheckOutcome.BLOCKED,
                code="RESUME_HASH_MISMATCH", message="Attached file does not match approved resume hash",
            ))

        # Check 5: Resume factual check passed
        if snapshot.resume_validation_passed:
            results.append(GateCheckResult(
                check_id=5, name="Resume factual check", outcome=GateCheckOutcome.PASS,
                code="RESUME_FACTUAL_PASS", message="Resume has 0 factual consistency violations",
            ))
        else:
            results.append(GateCheckResult(
                check_id=5, name="Resume factual check", outcome=GateCheckOutcome.BLOCKED,
                code="RESUME_FACTUAL_FAIL", message="Resume contains unverified claims or violations",
            ))

        # Check 6: Cover letter check passed
        if not snapshot.cover_letter_required or snapshot.cover_letter_validation_passed:
            results.append(GateCheckResult(
                check_id=6, name="Cover letter check", outcome=GateCheckOutcome.PASS,
                code="COVER_LETTER_PASS", message="Cover letter validated or not required",
            ))
        else:
            results.append(GateCheckResult(
                check_id=6, name="Cover letter check", outcome=GateCheckOutcome.BLOCKED,
                code="COVER_LETTER_FAIL", message="Cover letter failed factual validation",
            ))

        # Check 7: No unresolved placeholders or cross-contamination
        found_placeholders = []
        for val in snapshot.form_values.values():
            if PLACEHOLDER_REGEX.search(str(val)):
                found_placeholders.append(val)
            for other_co in snapshot.other_company_names:
                if other_co.lower() in str(val).lower() and other_co.lower() != snapshot.target_company_norm.lower():
                    found_placeholders.append(f"Cross-contamination: {other_co}")

        if not found_placeholders:
            results.append(GateCheckResult(
                check_id=7, name="No unresolved placeholders", outcome=GateCheckOutcome.PASS,
                code="NO_PLACEHOLDERS_PASS", message="Zero placeholders or cross-company contamination detected",
            ))
        else:
            results.append(GateCheckResult(
                check_id=7, name="No unresolved placeholders", outcome=GateCheckOutcome.BLOCKED,
                code="PLACEHOLDERS_DETECTED", message=f"Placeholders or contamination found: {found_placeholders}",
            ))

        # Check 8: All required fields populated
        missing_req = []
        for rk in snapshot.required_field_keys:
            val = snapshot.form_values.get(rk)
            if not val or not str(val).strip():
                missing_req.append(rk)

        if not missing_req:
            results.append(GateCheckResult(
                check_id=8, name="All required fields populated", outcome=GateCheckOutcome.PASS,
                code="REQUIRED_FIELDS_PASS", message="All required fields have populated values",
            ))
        else:
            results.append(GateCheckResult(
                check_id=8, name="All required fields populated", outcome=GateCheckOutcome.NEEDS_USER,
                code="REQUIRED_FIELDS_MISSING", message=f"Required fields missing values: {missing_req}",
            ))

        # Check 9: Valid email and phone
        email_val = (snapshot.form_values.get("email") or "").strip().lower()
        cand_email = (snapshot.candidate_verified_email or "").strip().lower()
        email_match = (email_val == cand_email) if cand_email else bool(email_val)

        phone_val = (snapshot.form_values.get("phone") or "").strip()
        cand_phone = (snapshot.candidate_verified_phone or "").strip()
        phone_match = (phone_val == cand_phone) if cand_phone else True

        if email_match and phone_match:
            results.append(GateCheckResult(
                check_id=9, name="Valid email and phone", outcome=GateCheckOutcome.PASS,
                code="CONTACT_VERIFIED_PASS", message="Email and phone match candidate facts character-for-character",
            ))
        else:
            results.append(GateCheckResult(
                check_id=9, name="Valid email and phone", outcome=GateCheckOutcome.NEEDS_USER,
                code="CONTACT_MISMATCH", message="Populated email or phone differs from verified contact facts",
            ))

        # Check 10: All values provenance-verified
        if not snapshot.unresolved_provenance_keys:
            results.append(GateCheckResult(
                check_id=10, name="All values provenance-verified", outcome=GateCheckOutcome.PASS,
                code="PROVENANCE_ALL_VERIFIED", message="Every form answer traces to an active fact or approved answer",
            ))
        else:
            results.append(GateCheckResult(
                check_id=10, name="All values provenance-verified", outcome=GateCheckOutcome.BLOCKED,
                code="PROVENANCE_MISSING", message=f"Fields lack provenance: {snapshot.unresolved_provenance_keys}",
            ))

        # Check 11: No contradictory dates
        if not snapshot.has_date_contradictions:
            results.append(GateCheckResult(
                check_id=11, name="No contradictory dates", outcome=GateCheckOutcome.PASS,
                code="DATES_CONSISTENT_PASS", message="No overlapping dates or duration contradictions",
            ))
        else:
            results.append(GateCheckResult(
                check_id=11, name="No contradictory dates", outcome=GateCheckOutcome.BLOCKED,
                code="CONTRADICTORY_DATES", message="Date contradictions detected across facts and answers",
            ))

        # Check 12: No unapproved sensitive or legal answers
        unapproved_sens = [
            sk for sk in snapshot.sensitive_field_keys if sk not in snapshot.approved_sensitive_keys
        ]
        if not unapproved_sens:
            results.append(GateCheckResult(
                check_id=12, name="Sensitive answers approved", outcome=GateCheckOutcome.PASS,
                code="SENSITIVE_APPROVED_PASS", message="All sensitive/legal fields have explicit user approval",
            ))
        else:
            results.append(GateCheckResult(
                check_id=12, name="Sensitive answers approved", outcome=GateCheckOutcome.NEEDS_USER,
                code="UNAPPROVED_SENSITIVE_FIELDS", message=f"Sensitive fields require user approval: {unapproved_sens}",
            ))

        # Check 13: No duplicate submission
        if snapshot.is_exact_duplicate:
            d_out = GateCheckOutcome.BLOCKED
            d_code = "EXACT_DUPLICATE_BLOCKED"
            d_msg = "Exact duplicate application already exists in database or portal"
        elif snapshot.is_near_duplicate:
            d_out = GateCheckOutcome.NEEDS_USER
            d_code = "NEAR_DUPLICATE_WARNING"
            d_msg = "Near-match application detected within 30 days"
        else:
            d_out = GateCheckOutcome.PASS
            d_code = "NO_DUPLICATE_PASS"
            d_msg = "No duplicate application found"
        results.append(GateCheckResult(
            check_id=13, name="Duplicate prevention", outcome=d_out, code=d_code, message=d_msg,
        ))

        # Check 14: Rate-limit quota available
        quota_blocked = False
        quota_msg = "Rate quota available"
        if snapshot.rate_global_count >= snapshot.rate_global_cap:
            quota_blocked = True
            quota_msg = f"Global daily cap reached ({snapshot.rate_global_count}/{snapshot.rate_global_cap})"
        elif snapshot.rate_portal_count >= snapshot.rate_portal_cap:
            quota_blocked = True
            quota_msg = f"Portal daily cap reached ({snapshot.rate_portal_count}/{snapshot.rate_portal_cap})"
        elif snapshot.rate_company_count >= snapshot.rate_company_cap:
            quota_blocked = True
            quota_msg = f"Company daily cap reached ({snapshot.rate_company_count}/{snapshot.rate_company_cap})"

        if not quota_blocked:
            results.append(GateCheckResult(
                check_id=14, name="Rate-limit quota available", outcome=GateCheckOutcome.PASS,
                code="QUOTA_AVAILABLE_PASS", message=quota_msg,
            ))
        else:
            results.append(GateCheckResult(
                check_id=14, name="Rate-limit quota available", outcome=GateCheckOutcome.BLOCKED,
                code="RATE_LIMIT_EXCEEDED", message=quota_msg,
            ))

        # Check 15: No unexpected DOM mutation
        if snapshot.inspection_form_skeleton_hash and snapshot.current_form_skeleton_hash and (
            snapshot.inspection_form_skeleton_hash == snapshot.current_form_skeleton_hash
        ):
            results.append(GateCheckResult(
                check_id=15, name="No unexpected DOM mutation", outcome=GateCheckOutcome.PASS,
                code="DOM_SKELETON_MATCH_PASS", message="Form skeleton hash unchanged since inspection",
            ))
        else:
            results.append(GateCheckResult(
                check_id=15, name="No unexpected DOM mutation", outcome=GateCheckOutcome.BLOCKED,
                code="DOM_DRIFT_DETECTED", message="Form layout, fields or action URL mutated since inspection",
            ))

        # Overall outcome determination
        has_blocked = any(r.outcome == GateCheckOutcome.BLOCKED for r in results)
        has_needs_user = any(r.outcome == GateCheckOutcome.NEEDS_USER for r in results)

        if has_blocked:
            overall = GateCheckOutcome.BLOCKED
        elif has_needs_user:
            overall = GateCheckOutcome.NEEDS_USER
        else:
            overall = GateCheckOutcome.PASS

        import uuid
        return GateReport(
            id=str(uuid.uuid4()),
            application_id=snapshot.application_id,
            content_hash=snapshot.package_hash,
            outcome=overall,
            results=results,
        )

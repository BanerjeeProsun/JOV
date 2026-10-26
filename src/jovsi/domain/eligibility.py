"""JOV.si Phase A Hard Constraints Eligibility Rules (Blueprint v2.0 Section 7).

Pure Python, zero I/O.
Evaluates:
1. Degree level
2. Graduation year
3. Minimum experience
4. Work authorization
5. Mandatory certifications
6. Deadline
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field

from jovsi.domain.models import DegreeLevel, Fact, FactKind, JobRequirements


class RuleOutcome(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNCERTAIN = "UNCERTAIN"


class HardRuleResult(BaseModel):
    rule_name: str
    outcome: RuleOutcome
    reason_code: str
    message: str
    warning: Optional[str] = None


class PhaseAResult(BaseModel):
    eligible: bool
    is_uncertain: bool
    overall_outcome: RuleOutcome  # PASS, FAIL, UNCERTAIN
    results: List[HardRuleResult]
    reason_codes: List[str] = Field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.overall_outcome == RuleOutcome.PASS


DEGREE_RANK = {
    DegreeLevel.DIPLOMA: 1,
    DegreeLevel.BACHELOR: 2,
    DegreeLevel.MASTER: 3,
    DegreeLevel.DOCTORATE: 4,
}


class EligibilityEngine:
    @classmethod
    def evaluate(
        cls,
        requirements: JobRequirements,
        active_facts: List[Fact],
        current_time: Optional[datetime] = None,
        candidate_timezone: str = "Asia/Kolkata",
    ) -> PhaseAResult:
        """Evaluate all 6 hard constraint rules over active candidate facts."""
        results: List[HardRuleResult] = []

        # Filter only usable facts
        facts = [f for f in active_facts if f.is_usable]

        # 1. Degree Level
        if requirements.min_degree is not None:
            results.append(cls._eval_degree(requirements, facts))

        # 2. Graduation Year
        if requirements.allowed_graduation_years is not None:
            results.append(cls._eval_grad_year(requirements, facts))

        # 3. Minimum Experience
        if requirements.min_experience_months is not None:
            results.append(cls._eval_experience(requirements, facts))

        # 4. Work Authorization
        if requirements.work_auth_countries:
            results.append(cls._eval_work_auth(requirements, facts))

        # 5. Mandatory Certifications
        if requirements.mandatory_certifications:
            results.append(cls._eval_certifications(requirements, facts))

        # 6. Deadline
        if requirements.deadline is not None:
            results.append(cls._eval_deadline(requirements, current_time or datetime.now(timezone.utc)))

        # Determine overall outcome
        has_fail = any(r.outcome == RuleOutcome.FAIL for r in results)
        has_uncertain = any(r.outcome == RuleOutcome.UNCERTAIN for r in results)

        reason_codes = [r.reason_code for r in results if r.outcome in (RuleOutcome.FAIL, RuleOutcome.UNCERTAIN)]

        if has_fail:
            overall = RuleOutcome.FAIL
            eligible = False
            is_uncertain = False
        elif has_uncertain:
            overall = RuleOutcome.UNCERTAIN
            eligible = False
            is_uncertain = True
        else:
            overall = RuleOutcome.PASS
            eligible = True
            is_uncertain = False

        return PhaseAResult(
            eligible=eligible,
            is_uncertain=is_uncertain,
            overall_outcome=overall,
            results=results,
            reason_codes=reason_codes,
        )

    @classmethod
    def _eval_degree(cls, req: JobRequirements, facts: List[Fact]) -> HardRuleResult:
        if req.extraction_confidence < 0.8:
            return HardRuleResult(
                rule_name="Degree Level",
                outcome=RuleOutcome.UNCERTAIN,
                reason_code="DEGREE_EXTRACTION_LOW_CONFIDENCE",
                message="Degree requirement extraction confidence is below 0.8",
            )

        edu_facts = [f for f in facts if f.kind == FactKind.EDUCATION]
        if not edu_facts:
            return HardRuleResult(
                rule_name="Degree Level",
                outcome=RuleOutcome.FAIL,
                reason_code="NO_EDUCATION_FACT",
                message="No verified education facts found for candidate",
            )

        max_candidate_rank = 0
        for f in edu_facts:
            deg_str = str(f.value.get("degree_level", "")).upper()
            try:
                deg_enum = DegreeLevel(deg_str)
                rank = DEGREE_RANK.get(deg_enum, 0)
                if rank > max_candidate_rank:
                    max_candidate_rank = rank
            except ValueError:
                pass

        required_rank = DEGREE_RANK.get(req.min_degree, 2)
        if max_candidate_rank >= required_rank:
            return HardRuleResult(
                rule_name="Degree Level",
                outcome=RuleOutcome.PASS,
                reason_code="DEGREE_PASS",
                message=f"Candidate degree rank {max_candidate_rank} meets requirement {required_rank}",
            )
        else:
            return HardRuleResult(
                rule_name="Degree Level",
                outcome=RuleOutcome.FAIL,
                reason_code="DEGREE_BELOW_MINIMUM",
                message=f"Candidate degree rank {max_candidate_rank} is below required {required_rank}",
            )

    @classmethod
    def _eval_grad_year(cls, req: JobRequirements, facts: List[Fact]) -> HardRuleResult:
        edu_facts = [f for f in facts if f.kind == FactKind.EDUCATION]
        grad_years = [f.value.get("graduation_year") for f in edu_facts if "graduation_year" in f.value]
        
        if not grad_years:
            return HardRuleResult(
                rule_name="Graduation Year",
                outcome=RuleOutcome.UNCERTAIN,
                reason_code="GRAD_YEAR_UNKNOWN",
                message="Candidate has no recorded graduation year fact",
            )

        allowed = set(req.allowed_graduation_years or [])
        if any(gy in allowed for gy in grad_years):
            return HardRuleResult(
                rule_name="Graduation Year",
                outcome=RuleOutcome.PASS,
                reason_code="GRAD_YEAR_PASS",
                message=f"Candidate graduation year in allowed set {allowed}",
            )
        else:
            return HardRuleResult(
                rule_name="Graduation Year",
                outcome=RuleOutcome.FAIL,
                reason_code="GRAD_YEAR_DISQUALIFIED",
                message=f"Candidate graduation year not in allowed set {allowed}",
            )

    @classmethod
    def _eval_experience(cls, req: JobRequirements, facts: List[Fact]) -> HardRuleResult:
        exp_facts = [f for f in facts if f.kind == FactKind.EXPERIENCE]
        total_months = 0
        for f in exp_facts:
            total_months += int(f.value.get("duration_months", 0))

        req_months = req.min_experience_months or 0
        if total_months >= req_months:
            return HardRuleResult(
                rule_name="Minimum Experience",
                outcome=RuleOutcome.PASS,
                reason_code="EXPERIENCE_PASS",
                message=f"Candidate has {total_months} months experience (required {req_months})",
            )
        else:
            return HardRuleResult(
                rule_name="Minimum Experience",
                outcome=RuleOutcome.FAIL,
                reason_code="EXPERIENCE_BELOW_MINIMUM",
                message=f"Candidate has {total_months} months experience, below required {req_months}",
            )

    @classmethod
    def _eval_work_auth(cls, req: JobRequirements, facts: List[Fact]) -> HardRuleResult:
        auth_facts = [f for f in facts if f.kind == FactKind.WORK_AUTH]
        if not auth_facts:
            return HardRuleResult(
                rule_name="Work Authorization",
                outcome=RuleOutcome.UNCERTAIN,
                reason_code="WORK_AUTH_UNKNOWN",
                message="No verified work authorization facts found (never assumed)",
            )

        authorized_countries = set()
        excluded_countries = set()
        for f in auth_facts:
            for country in f.value.get("authorized_countries", []):
                authorized_countries.add(str(country).upper())
            for country in f.value.get("excluded_countries", []):
                excluded_countries.add(str(country).upper())

        needed = {str(c).upper() for c in (req.work_auth_countries or [])}

        if any(c in excluded_countries for c in needed):
            return HardRuleResult(
                rule_name="Work Authorization",
                outcome=RuleOutcome.FAIL,
                reason_code="WORK_AUTH_EXCLUDED",
                message=f"Candidate explicitly excluded from working in {needed}",
            )

        if needed.issubset(authorized_countries):
            return HardRuleResult(
                rule_name="Work Authorization",
                outcome=RuleOutcome.PASS,
                reason_code="WORK_AUTH_PASS",
                message=f"Candidate authorized for {needed}",
            )

        return HardRuleResult(
            rule_name="Work Authorization",
            outcome=RuleOutcome.UNCERTAIN,
            reason_code="WORK_AUTH_INCOMPLETE",
            message=f"Candidate work authorization missing coverage for {needed - authorized_countries}",
        )

    @classmethod
    def _eval_certifications(cls, req: JobRequirements, facts: List[Fact]) -> HardRuleResult:
        cert_facts = [f for f in facts if f.kind == FactKind.CERTIFICATION]
        candidate_certs = {str(f.value.get("name", "")).strip().lower() for f in cert_facts}

        missing = []
        for c in (req.mandatory_certifications or []):
            if c.strip().lower() not in candidate_certs:
                missing.append(c)

        if not missing:
            return HardRuleResult(
                rule_name="Mandatory Certifications",
                outcome=RuleOutcome.PASS,
                reason_code="CERTIFICATIONS_PASS",
                message="All mandatory certifications verified",
            )
        else:
            return HardRuleResult(
                rule_name="Mandatory Certifications",
                outcome=RuleOutcome.FAIL,
                reason_code="CERTIFICATION_MISSING",
                message=f"Missing mandatory certifications: {missing}",
            )

    @classmethod
    def _eval_deadline(cls, req: JobRequirements, current_time: datetime) -> HardRuleResult:
        if req.deadline is None:
            return HardRuleResult(
                rule_name="Deadline",
                outcome=RuleOutcome.PASS,
                reason_code="DEADLINE_OPEN",
                message="No deadline specified",
            )

        # Make sure datetimes are comparable
        deadline = req.deadline
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)

        if current_time > deadline:
            return HardRuleResult(
                rule_name="Deadline",
                outcome=RuleOutcome.FAIL,
                reason_code="DEADLINE_EXPIRED",
                message="Application deadline has passed",
            )

        diff = (deadline - current_time).total_seconds()
        warning = None
        if diff <= 86400:  # within 24 hours
            warning = "Deadline is within 24 hours"

        return HardRuleResult(
            rule_name="Deadline",
            outcome=RuleOutcome.PASS,
            reason_code="DEADLINE_PASS",
            message="Deadline is active",
            warning=warning,
        )

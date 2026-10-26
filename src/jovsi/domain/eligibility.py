"""JOV.si Phase A Hard Constraints Eligibility Rules (Blueprint v2.0 Section 7).

Pure Python, zero I/O.
Evaluates:
1. Degree level
2. Degree field
3. Graduation year window
4. Minimum experience
5. Work authorization countries
6. Mandatory certifications
7. Mandatory skills
8. Location / remote eligibility
9. Application deadline
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field

from jovsi.domain.models import DegreeLevel, Fact, FactKind, JobRequirements
from jovsi.domain.scoring import RELATED_FIELDS, canonical_skill


class RuleOutcome(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNCERTAIN = "UNCERTAIN"
    NEEDS_REVIEW = "UNCERTAIN"  # Alias: unknown requirements yield UNCERTAIN / NEEDS_REVIEW


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
    passed_reasons: List[str] = Field(default_factory=list)
    disqualifying_reasons: List[str] = Field(default_factory=list)
    uncertain_reasons: List[str] = Field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.overall_outcome == RuleOutcome.PASS

    @property
    def needs_review(self) -> bool:
        return self.overall_outcome in (RuleOutcome.UNCERTAIN, RuleOutcome.NEEDS_REVIEW)


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
        """Evaluate hard constraint rules over active candidate facts."""
        results: List[HardRuleResult] = []

        # Filter only usable facts
        facts = [f for f in active_facts if f.is_usable]

        # 1. Degree Level
        if requirements.min_degree is not None:
            results.append(cls._eval_degree(requirements, facts))

        # 2. Degree Field
        if requirements.required_degree_fields:
            results.append(cls._eval_degree_field(requirements, facts))

        # 3. Graduation Year
        if requirements.allowed_graduation_years is not None:
            results.append(cls._eval_grad_year(requirements, facts))

        # 4. Minimum Experience
        if requirements.min_experience_months is not None:
            results.append(cls._eval_experience(requirements, facts))

        # 5. Work Authorization
        if requirements.work_auth_countries:
            results.append(cls._eval_work_auth(requirements, facts))

        # 6. Mandatory Certifications
        if requirements.mandatory_certifications:
            results.append(cls._eval_certifications(requirements, facts))

        # 7. Mandatory Skills
        if requirements.mandatory_skills:
            results.append(cls._eval_mandatory_skills(requirements, facts))

        # 8. Location / Remote Eligibility
        if requirements.accepted_work_modes or requirements.target_locations:
            results.append(cls._eval_location_eligibility(requirements, facts))

        # 9. Deadline
        if requirements.deadline is not None:
            results.append(cls._eval_deadline(requirements, current_time or datetime.now(timezone.utc)))

        # Determine overall outcome
        has_fail = any(r.outcome == RuleOutcome.FAIL for r in results)
        has_uncertain = any(r.outcome in (RuleOutcome.UNCERTAIN, RuleOutcome.NEEDS_REVIEW) for r in results)

        reason_codes = [r.reason_code for r in results if r.outcome in (RuleOutcome.FAIL, RuleOutcome.UNCERTAIN, RuleOutcome.NEEDS_REVIEW)]
        disqualifying_reasons = [r.message for r in results if r.outcome == RuleOutcome.FAIL]
        uncertain_reasons = [r.message for r in results if r.outcome in (RuleOutcome.UNCERTAIN, RuleOutcome.NEEDS_REVIEW)]
        passed_reasons = [r.message for r in results if r.outcome == RuleOutcome.PASS]

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
            passed_reasons=passed_reasons,
            disqualifying_reasons=disqualifying_reasons,
            uncertain_reasons=uncertain_reasons,
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
                outcome=RuleOutcome.UNCERTAIN,
                reason_code="NO_EDUCATION_FACT",
                message="Candidate has no verified education facts recorded (needs review)",
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
    def _eval_degree_field(cls, req: JobRequirements, facts: List[Fact]) -> HardRuleResult:
        edu_facts = [f for f in facts if f.kind == FactKind.EDUCATION]
        fields = [str(f.value.get("field", "")).strip().lower() for f in edu_facts if f.value.get("field")]
        if not fields:
            return HardRuleResult(
                rule_name="Degree Field",
                outcome=RuleOutcome.UNCERTAIN,
                reason_code="DEGREE_FIELD_UNKNOWN",
                message="Candidate has no recorded degree field fact (needs review)",
            )

        required_fields = [f.strip().lower() for f in (req.required_degree_fields or []) if f.strip()]
        matched = False
        for rf in required_fields:
            related = RELATED_FIELDS.get(rf, set())
            for cf in fields:
                if cf == rf or rf in cf or cf in rf or any(r in cf for r in related):
                    matched = True
                    break
            if matched:
                break

        if matched:
            return HardRuleResult(
                rule_name="Degree Field",
                outcome=RuleOutcome.PASS,
                reason_code="DEGREE_FIELD_PASS",
                message=f"Candidate degree field aligns with required fields {req.required_degree_fields}",
            )
        else:
            return HardRuleResult(
                rule_name="Degree Field",
                outcome=RuleOutcome.FAIL,
                reason_code="DEGREE_FIELD_DISQUALIFIED",
                message=f"Candidate degree field {fields} does not match required fields {req.required_degree_fields}",
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
                message="Candidate has no recorded graduation year fact (needs review)",
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
        total_months = sum(int(f.value.get("duration_months", 0)) for f in exp_facts)

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
        if not cert_facts:
            return HardRuleResult(
                rule_name="Mandatory Certifications",
                outcome=RuleOutcome.UNCERTAIN,
                reason_code="CERTIFICATION_UNRECORDED",
                message=f"Candidate has no recorded certification facts (needs review for: {req.mandatory_certifications})",
            )

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
    def _eval_mandatory_skills(cls, req: JobRequirements, facts: List[Fact]) -> HardRuleResult:
        candidate_skills: Set[str] = set()
        for f in facts:
            if f.kind == FactKind.SKILL:
                s_name = canonical_skill(str(f.value.get("name", "")))
                if s_name:
                    candidate_skills.add(s_name)
            elif f.kind in (FactKind.PROJECT, FactKind.EXPERIENCE):
                for s in f.value.get("skills", []):
                    s_name = canonical_skill(str(s))
                    if s_name:
                        candidate_skills.add(s_name)

        mandatory = [s for s in (req.mandatory_skills or []) if s.strip()]
        if not candidate_skills:
            return HardRuleResult(
                rule_name="Mandatory Skills",
                outcome=RuleOutcome.UNCERTAIN,
                reason_code="SKILLS_UNRECORDED",
                message=f"Candidate has no recorded skills (needs review for: {mandatory})",
            )

        missing = [s for s in mandatory if canonical_skill(s) not in candidate_skills]
        if not missing:
            return HardRuleResult(
                rule_name="Mandatory Skills",
                outcome=RuleOutcome.PASS,
                reason_code="MANDATORY_SKILLS_PASS",
                message="All mandatory skills verified in candidate profile",
            )
        else:
            return HardRuleResult(
                rule_name="Mandatory Skills",
                outcome=RuleOutcome.FAIL,
                reason_code="MANDATORY_SKILL_MISSING",
                message=f"Missing mandatory skills: {missing}",
            )

    @classmethod
    def _eval_location_eligibility(
        cls,
        req: JobRequirements,
        facts: List[Fact],
        candidate_work_modes: Optional[List[str]] = None,
        candidate_locations: Optional[List[str]] = None,
    ) -> HardRuleResult:
        cand_modes: Set[str] = set()
        cand_locs: Set[str] = set()

        if candidate_work_modes:
            cand_modes.update(m.lower() for m in candidate_work_modes)
        if candidate_locations:
            cand_locs.update(loc.lower() for loc in candidate_locations)

        for f in facts:
            if f.kind == FactKind.PREFERENCE:
                for m in f.value.get("work_modes", []):
                    cand_modes.add(str(m).lower())
                for loc in f.value.get("locations", []):
                    cand_locs.add(str(loc).lower())
            elif f.kind == FactKind.CONTACT:
                city = f.value.get("city")
                country = f.value.get("country")
                if city:
                    cand_locs.add(str(city).lower())
                if country:
                    cand_locs.add(str(country).lower())

        job_modes = {m.lower() for m in (req.accepted_work_modes or ["remote", "hybrid", "onsite"])}

        # If job supports remote and candidate accepts remote (or unstated)
        if "remote" in job_modes and (not cand_modes or "remote" in cand_modes):
            return HardRuleResult(
                rule_name="Location / Remote Eligibility",
                outcome=RuleOutcome.PASS,
                reason_code="LOCATION_REMOTE_PASS",
                message="Job supports remote work mode; candidate is remote-eligible",
            )

        # If job strictly requires onsite/hybrid without remote
        if "remote" not in job_modes:
            if cand_modes and "onsite" not in cand_modes and "hybrid" not in cand_modes:
                return HardRuleResult(
                    rule_name="Location / Remote Eligibility",
                    outcome=RuleOutcome.FAIL,
                    reason_code="WORK_MODE_INCOMPATIBLE",
                    message="Job requires on-site or hybrid presence, but candidate preferences exclude non-remote work",
                )

        # Check target locations if specified
        target_locs = [tl.lower() for tl in (req.target_locations or []) if tl.strip()]
        if target_locs:
            if cand_locs:
                matched_loc = any(
                    any(tl in cl or cl in tl for tl in target_locs)
                    for cl in cand_locs
                )
                if matched_loc:
                    return HardRuleResult(
                        rule_name="Location / Remote Eligibility",
                        outcome=RuleOutcome.PASS,
                        reason_code="LOCATION_PASS",
                        message=f"Candidate location matches target job location {req.target_locations}",
                    )
                else:
                    return HardRuleResult(
                        rule_name="Location / Remote Eligibility",
                        outcome=RuleOutcome.FAIL,
                        reason_code="LOCATION_MISMATCH",
                        message=f"Candidate location {list(cand_locs)} does not match required location {req.target_locations}",
                    )
            else:
                return HardRuleResult(
                    rule_name="Location / Remote Eligibility",
                    outcome=RuleOutcome.UNCERTAIN,
                    reason_code="LOCATION_UNKNOWN",
                    message=f"Job requires presence in {req.target_locations}; candidate location unstated (needs review)",
                )

        return HardRuleResult(
            rule_name="Location / Remote Eligibility",
            outcome=RuleOutcome.PASS,
            reason_code="LOCATION_PASS",
            message="Location and work mode requirements met",
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
        if diff <= 86400:
            warning = "Deadline is within 24 hours"

        return HardRuleResult(
            rule_name="Deadline",
            outcome=RuleOutcome.PASS,
            reason_code="DEADLINE_PASS",
            message="Deadline is active",
            warning=warning,
        )

"""Unit tests for Phase A Hard Eligibility Rules (Blueprint v2.0 Section 7)."""

from datetime import datetime, timedelta, timezone
import pytest
from jovsi.domain.models import DegreeLevel, FactKind, JobRequirements
from jovsi.domain.provenance import ProvenanceEngine
from jovsi.domain.eligibility import EligibilityEngine, RuleOutcome


@pytest.fixture
def base_facts():
    return [
        ProvenanceEngine.create_user_fact(
            candidate_id="c1",
            kind=FactKind.EDUCATION,
            key="edu1",
            value={"degree_level": "BACHELOR", "graduation_year": 2024},
        ),
        ProvenanceEngine.create_user_fact(
            candidate_id="c1",
            kind=FactKind.EXPERIENCE,
            key="exp1",
            value={"duration_months": 24, "title": "Software Engineer"},
        ),
        ProvenanceEngine.create_user_fact(
            candidate_id="c1",
            kind=FactKind.WORK_AUTH,
            key="auth1",
            value={"authorized_countries": ["US", "IN"], "excluded_countries": []},
        ),
        ProvenanceEngine.create_user_fact(
            candidate_id="c1",
            kind=FactKind.CERTIFICATION,
            key="cert1",
            value={"name": "AWS Certified Solutions Architect"},
        ),
    ]


def test_degree_level_pass_and_fail(base_facts) -> None:
    # Requires Bachelor -> PASS
    req_pass = JobRequirements(min_degree=DegreeLevel.BACHELOR)
    res_pass = EligibilityEngine.evaluate(req_pass, base_facts)
    assert res_pass.eligible is True
    assert res_pass.overall_outcome == RuleOutcome.PASS

    # Requires Master -> FAIL
    req_fail = JobRequirements(min_degree=DegreeLevel.MASTER)
    res_fail = EligibilityEngine.evaluate(req_fail, base_facts)
    assert res_fail.eligible is False
    assert res_fail.overall_outcome == RuleOutcome.FAIL
    assert "DEGREE_BELOW_MINIMUM" in res_fail.reason_codes


def test_graduation_year_pass_and_fail(base_facts) -> None:
    # Allowed [2023, 2024, 2025] -> PASS
    req_pass = JobRequirements(allowed_graduation_years=[2023, 2024])
    res_pass = EligibilityEngine.evaluate(req_pass, base_facts)
    assert res_pass.eligible is True

    # Allowed [2020, 2021] -> FAIL
    req_fail = JobRequirements(allowed_graduation_years=[2020, 2021])
    res_fail = EligibilityEngine.evaluate(req_fail, base_facts)
    assert res_fail.eligible is False
    assert "GRAD_YEAR_DISQUALIFIED" in res_fail.reason_codes


def test_experience_pass_and_fail(base_facts) -> None:
    # Candidate has 24 months
    req_pass = JobRequirements(min_experience_months=12)
    assert EligibilityEngine.evaluate(req_pass, base_facts).eligible is True

    req_fail = JobRequirements(min_experience_months=36)
    res_fail = EligibilityEngine.evaluate(req_fail, base_facts)
    assert res_fail.eligible is False
    assert "EXPERIENCE_BELOW_MINIMUM" in res_fail.reason_codes


def test_work_authorization_cases(base_facts) -> None:
    # Requires US -> PASS
    req_us = JobRequirements(work_auth_countries=["US"])
    assert EligibilityEngine.evaluate(req_us, base_facts).eligible is True

    # Requires UK (not in candidate auth) -> UNCERTAIN (never assumed)
    req_uk = JobRequirements(work_auth_countries=["UK"])
    res_uk = EligibilityEngine.evaluate(req_uk, base_facts)
    assert res_uk.eligible is False
    assert res_uk.is_uncertain is True
    assert res_uk.overall_outcome == RuleOutcome.UNCERTAIN
    assert "WORK_AUTH_INCOMPLETE" in res_uk.reason_codes

    # Explicit exclusion -> FAIL
    excluding_fact = ProvenanceEngine.create_user_fact(
        candidate_id="c1",
        kind=FactKind.WORK_AUTH,
        key="auth_excl",
        value={"authorized_countries": [], "excluded_countries": ["DE"]},
    )
    req_de = JobRequirements(work_auth_countries=["DE"])
    res_de = EligibilityEngine.evaluate(req_de, base_facts + [excluding_fact])
    assert res_de.eligible is False
    assert res_de.overall_outcome == RuleOutcome.FAIL
    assert "WORK_AUTH_EXCLUDED" in res_de.reason_codes


def test_deadline_expired_and_warning() -> None:
    now = datetime.now(timezone.utc)

    # Deadline in the past -> FAIL
    req_past = JobRequirements(deadline=now - timedelta(hours=2))
    res_past = EligibilityEngine.evaluate(req_past, [], current_time=now)
    assert res_past.overall_outcome == RuleOutcome.FAIL
    assert "DEADLINE_EXPIRED" in res_past.reason_codes

    # Deadline in 5 hours -> PASS with warning
    req_soon = JobRequirements(deadline=now + timedelta(hours=5))
    res_soon = EligibilityEngine.evaluate(req_soon, [], current_time=now)
    assert res_soon.overall_outcome == RuleOutcome.PASS
    deadline_rule = next(r for r in res_soon.results if r.rule_name == "Deadline")
    assert deadline_rule.warning is not None
    assert "24 hours" in deadline_rule.warning

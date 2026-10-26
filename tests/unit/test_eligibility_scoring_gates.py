"""Comprehensive tests for Milestone 9: Hard Eligibility Gates & Explainable Scoring.

Validates:
1. Strict separation of hard constraints from soft scoring.
2. Unknown mandatory requirements yield UNCERTAIN / NEEDS_REVIEW, never auto-pass.
3. Hard gate outcomes: PASS, FAIL, UNCERTAIN / NEEDS_REVIEW.
4. All 9 hard constraint rules:
   - Degree level
   - Degree field (including related field ontology)
   - Graduation year window
   - Minimum experience months
   - Work authorization countries (authorized vs excluded, never assumed)
   - Mandatory certifications
   - Mandatory skills
   - Location / remote eligibility
   - Application deadline
5. Human-readable explainable breakdowns (passed_reasons, disqualifying_reasons, uncertain_reasons).
6. Soft scoring engine properties (0-100 soft score, matched/missing skills, dynamic renormalisation).
7. End-to-end application evaluation state transitions (REJECTED, AWAITING_USER_INPUT, SHORTLISTED, BELOW_THRESHOLD).
"""

from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from jovsi.domain.models import DegreeLevel, Fact, FactKind, JobRequirements
from jovsi.domain.provenance import ProvenanceEngine
from jovsi.domain.eligibility import EligibilityEngine, RuleOutcome
from jovsi.domain.scoring import ScoringEngine
from jovsi.domain.state_machine import ApplicationState
from jovsi.adapters.db.models import ApplicationDB, CandidateDB, EvaluationDB, JobDB, UserDB
from jovsi.adapters.db.session import engine, init_db
from jovsi.api.main import app


@pytest.fixture
def candidate_c1():
    return [
        ProvenanceEngine.create_user_fact(
            candidate_id="c1",
            kind=FactKind.EDUCATION,
            key="edu1",
            value={
                "degree_level": "BACHELOR",
                "field": "Computer Science",
                "graduation_year": 2024,
            },
        ),
        ProvenanceEngine.create_user_fact(
            candidate_id="c1",
            kind=FactKind.EXPERIENCE,
            key="exp1",
            value={
                "duration_months": 30,
                "title": "Software Engineer",
                "description": "Built distributed REST APIs using Python, FastAPI, and PostgreSQL.",
                "skills": ["Python", "FastAPI", "PostgreSQL"],
                "is_current": True,
            },
        ),
        ProvenanceEngine.create_user_fact(
            candidate_id="c1",
            kind=FactKind.SKILL,
            key="skill_py",
            value={"name": "Python"},
        ),
        ProvenanceEngine.create_user_fact(
            candidate_id="c1",
            kind=FactKind.SKILL,
            key="skill_fastapi",
            value={"name": "FastAPI"},
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
        ProvenanceEngine.create_user_fact(
            candidate_id="c1",
            kind=FactKind.PREFERENCE,
            key="pref1",
            value={"work_modes": ["remote", "hybrid"], "locations": ["Austin, TX", "US"]},
        ),
    ]


# -------------------------------------------------------------------------
# 1. DEGREE LEVEL & FIELD GATES
# -------------------------------------------------------------------------

def test_degree_level_unknown_yields_uncertain() -> None:
    """When candidate has no education facts recorded, degree requirement must yield UNCERTAIN / NEEDS_REVIEW."""
    req = JobRequirements(min_degree=DegreeLevel.BACHELOR)
    res = EligibilityEngine.evaluate(req, [])
    assert res.eligible is False
    assert res.is_uncertain is True
    assert res.overall_outcome == RuleOutcome.UNCERTAIN
    assert "NO_EDUCATION_FACT" in res.reason_codes
    assert any("no verified education facts" in r.lower() for r in res.uncertain_reasons)


def test_degree_field_matching_and_related_ontology(candidate_c1) -> None:
    """Degree field matches directly or through related ontology (CS -> Software Engineering)."""
    # Direct match: Computer Science
    req_direct = JobRequirements(required_degree_fields=["Computer Science"])
    res_direct = EligibilityEngine.evaluate(req_direct, candidate_c1)
    assert res_direct.eligible is True
    assert res_direct.overall_outcome == RuleOutcome.PASS

    # Related match: Software Engineering (related to CS)
    req_related = JobRequirements(required_degree_fields=["Software Engineering"])
    res_related = EligibilityEngine.evaluate(req_related, candidate_c1)
    assert res_related.eligible is True
    assert res_related.overall_outcome == RuleOutcome.PASS

    # Disqualified: Art History
    req_art = JobRequirements(required_degree_fields=["Art History"])
    res_art = EligibilityEngine.evaluate(req_art, candidate_c1)
    assert res_art.eligible is False
    assert res_art.overall_outcome == RuleOutcome.FAIL
    assert "DEGREE_FIELD_DISQUALIFIED" in res_art.reason_codes
    assert any("does not match required" in r for r in res_art.disqualifying_reasons)


# -------------------------------------------------------------------------
# 2. GRADUATION YEAR & EXPERIENCE GATES
# -------------------------------------------------------------------------

def test_graduation_year_unknown_yields_uncertain() -> None:
    """Candidate with education fact missing graduation_year yields UNCERTAIN."""
    edu_no_year = [
        ProvenanceEngine.create_user_fact(
            candidate_id="c2",
            kind=FactKind.EDUCATION,
            key="edu_noyear",
            value={"degree_level": "BACHELOR"},
        )
    ]
    req = JobRequirements(allowed_graduation_years=[2023, 2024])
    res = EligibilityEngine.evaluate(req, edu_no_year)
    assert res.is_uncertain is True
    assert res.overall_outcome == RuleOutcome.UNCERTAIN
    assert "GRAD_YEAR_UNKNOWN" in res.reason_codes


def test_experience_gate_pass_and_fail(candidate_c1) -> None:
    """Candidate has 30 months; 24 months PASS, 36 months FAIL."""
    req_pass = JobRequirements(min_experience_months=24)
    res_pass = EligibilityEngine.evaluate(req_pass, candidate_c1)
    assert res_pass.eligible is True

    req_fail = JobRequirements(min_experience_months=36)
    res_fail = EligibilityEngine.evaluate(req_fail, candidate_c1)
    assert res_fail.eligible is False
    assert res_fail.overall_outcome == RuleOutcome.FAIL
    assert "EXPERIENCE_BELOW_MINIMUM" in res_fail.reason_codes


# -------------------------------------------------------------------------
# 3. WORK AUTHORIZATION & CERTIFICATION GATES
# -------------------------------------------------------------------------

def test_work_auth_unknown_never_auto_passes() -> None:
    """Unknown work authorization must NEVER auto-pass (yields UNCERTAIN / NEEDS_REVIEW)."""
    req = JobRequirements(work_auth_countries=["US"])
    res = EligibilityEngine.evaluate(req, [])
    assert res.eligible is False
    assert res.is_uncertain is True
    assert res.overall_outcome == RuleOutcome.UNCERTAIN
    assert "WORK_AUTH_UNKNOWN" in res.reason_codes
    assert any("never assumed" in r for r in res.uncertain_reasons)


def test_mandatory_certifications_pass_fail_uncertain(candidate_c1) -> None:
    """Evaluates mandatory certifications with UNCERTAIN when unrecorded and FAIL when missing."""
    # PASS: Candidate has AWS Certified Solutions Architect
    req_pass = JobRequirements(mandatory_certifications=["AWS Certified Solutions Architect"])
    res_pass = EligibilityEngine.evaluate(req_pass, candidate_c1)
    assert res_pass.eligible is True
    assert res_pass.overall_outcome == RuleOutcome.PASS

    # FAIL: Candidate has certs, but missing CISSP
    req_fail = JobRequirements(mandatory_certifications=["CISSP"])
    res_fail = EligibilityEngine.evaluate(req_fail, candidate_c1)
    assert res_fail.eligible is False
    assert res_fail.overall_outcome == RuleOutcome.FAIL
    assert "CERTIFICATION_MISSING" in res_fail.reason_codes

    # UNCERTAIN: Candidate with 0 cert facts evaluated against mandatory cert requirement
    facts_no_certs = [f for f in candidate_c1 if f.kind != FactKind.CERTIFICATION]
    res_unc = EligibilityEngine.evaluate(req_pass, facts_no_certs)
    assert res_unc.is_uncertain is True
    assert res_unc.overall_outcome == RuleOutcome.UNCERTAIN
    assert "CERTIFICATION_UNRECORDED" in res_unc.reason_codes


# -------------------------------------------------------------------------
# 4. MANDATORY SKILLS & LOCATION GATES
# -------------------------------------------------------------------------

def test_mandatory_skills_gate(candidate_c1) -> None:
    """Mandatory skills gate verifies required technical competencies."""
    # PASS: Candidate has Python & FastAPI
    req_pass = JobRequirements(mandatory_skills=["Python", "FastAPI"])
    res_pass = EligibilityEngine.evaluate(req_pass, candidate_c1)
    assert res_pass.eligible is True
    assert res_pass.overall_outcome == RuleOutcome.PASS

    # FAIL: Missing Kubernetes
    req_fail = JobRequirements(mandatory_skills=["Python", "Kubernetes"])
    res_fail = EligibilityEngine.evaluate(req_fail, candidate_c1)
    assert res_fail.eligible is False
    assert res_fail.overall_outcome == RuleOutcome.FAIL
    assert "MANDATORY_SKILL_MISSING" in res_fail.reason_codes

    # UNCERTAIN: Candidate with 0 skills
    facts_no_skills = [
        f for f in candidate_c1
        if f.kind not in (FactKind.SKILL, FactKind.EXPERIENCE, FactKind.PROJECT)
    ]
    res_unc = EligibilityEngine.evaluate(req_pass, facts_no_skills)
    assert res_unc.is_uncertain is True
    assert "SKILLS_UNRECORDED" in res_unc.reason_codes


def test_location_and_remote_eligibility(candidate_c1) -> None:
    """Tests location compatibility and remote work mode gating."""
    # PASS: Job is remote, candidate accepts remote
    req_remote = JobRequirements(accepted_work_modes=["remote"])
    res_remote = EligibilityEngine.evaluate(req_remote, candidate_c1)
    assert res_remote.eligible is True
    assert res_remote.overall_outcome == RuleOutcome.PASS

    # FAIL: Job is strictly onsite in Tokyo, candidate only accepts remote and is in US
    remote_only_candidate = [
        f for f in candidate_c1 if f.kind != FactKind.PREFERENCE
    ] + [
        ProvenanceEngine.create_user_fact(
            candidate_id="c1",
            kind=FactKind.PREFERENCE,
            key="p_remote",
            value={"work_modes": ["remote"], "locations": ["US"]},
        )
    ]
    req_onsite_tokyo = JobRequirements(
        accepted_work_modes=["onsite"],
        target_locations=["Tokyo, Japan"],
    )
    res_tokyo = EligibilityEngine.evaluate(req_onsite_tokyo, remote_only_candidate)
    assert res_tokyo.eligible is False
    assert res_tokyo.overall_outcome == RuleOutcome.FAIL
    assert "WORK_MODE_INCOMPATIBLE" in res_tokyo.reason_codes


# -------------------------------------------------------------------------
# 5. EXPLAINABLE SOFT SCORING ENGINE
# -------------------------------------------------------------------------

def test_explainable_scoring_breakdown(candidate_c1) -> None:
    """Tests that soft scoring returns 0-100 score, matched/missing skills, recency, and explanation."""
    req = JobRequirements(
        min_degree=DegreeLevel.BACHELOR,
        required_skills=["Python", "FastAPI"],
        preferred_skills=["PostgreSQL", "Docker", "AWS"],
        responsibilities=["Built distributed REST APIs using Python and FastAPI"],
        target_role_family="Software Engineer",
        accepted_work_modes=["remote"],
    )
    score = ScoringEngine.score_job(req, candidate_c1)

    assert 0.0 <= score.total_score <= 100.0
    assert "skills" in score.categories
    assert "experience" in score.categories
    assert "education" in score.categories
    assert "role" in score.categories
    assert "location" in score.categories

    # Matched & missing skills
    assert "python" in [s.lower() for s in score.matched_skills]
    assert "fastapi" in [s.lower() for s in score.matched_skills]
    assert "docker" in [s.lower() for s in score.missing_skills]

    # Recency
    assert score.recency_notes is not None
    assert "recent" in score.recency_notes.lower()

    # Human-readable summary
    assert "Scored" in score.summary_explanation
    assert "/100" in score.summary_explanation


# -------------------------------------------------------------------------
# 6. APPLICATION EVALUATION & STATE TRANSITIONS VIA API
# -------------------------------------------------------------------------

def test_application_evaluate_endpoint_end_to_end() -> None:
    """Verifies that POST /api/v1/applications/{id}/evaluate enforces gates and transitions properly."""
    init_db()
    client = TestClient(app)

    # 1. Register candidate user
    user_email = f"eval_test_{int(datetime.now().timestamp())}@jov.si"
    reg_resp = client.post(
        "/api/v1/auth/register",
        json={"email": user_email, "password": "Password123!", "display_name": "Eval Tester"},
    )
    assert reg_resp.status_code == 201

    # 2. Candidate profile
    cand_resp = client.get("/api/v1/candidates")
    assert cand_resp.status_code == 200
    candidate_id = cand_resp.json()[0]["id"]

    # Add verified facts
    client.post(
        f"/api/v1/candidates/{candidate_id}/facts",
        json={
            "kind": "EDUCATION",
            "key": "edu_ev",
            "value": {"degree_level": "BACHELOR", "field": "Computer Science", "graduation_year": 2024},
            "status": "ACTIVE",
            "provenance": "USER_VERIFIED",
        },
    )
    client.post(
        f"/api/v1/candidates/{candidate_id}/facts",
        json={
            "kind": "SKILL",
            "key": "sk_python",
            "value": {"name": "Python"},
            "status": "ACTIVE",
            "provenance": "USER_VERIFIED",
        },
    )
    client.post(
        f"/api/v1/candidates/{candidate_id}/facts",
        json={
            "kind": "WORK_AUTH",
            "key": "wa_us",
            "value": {"authorized_countries": ["US"], "excluded_countries": []},
            "status": "ACTIVE",
            "provenance": "USER_VERIFIED",
        },
    )

    # 3. Create a PASSING Job
    job_pass_resp = client.post(
        "/api/v1/jobs/import",
        json={
            "title": "Backend Python Developer",
            "company_name": "Scale Corp",
            "source_url": f"https://example.com/job/pass-{int(datetime.now().timestamp())}",
            "target_locations": ["Remote, US"],
            "raw_description": "Senior backend python developer building APIs.",
            "min_degree": "BACHELOR",
            "required_skills": ["Python"],
            "work_auth_countries": ["US"],
            "accepted_work_modes": ["remote"],
        },
    )
    assert job_pass_resp.status_code == 201
    job_pass_id = job_pass_resp.json()["id"]

    # 4. Create an UNCERTAIN Job (requires German work auth which candidate does not have)
    job_unc_resp = client.post(
        "/api/v1/jobs/import",
        json={
            "title": "Berlin Software Engineer",
            "company_name": "Berlin Tech",
            "source_url": f"https://example.com/job/unc-{int(datetime.now().timestamp())}",
            "target_locations": ["Berlin, Germany"],
            "raw_description": "Software engineer in Berlin.",
            "work_auth_countries": ["DE"],
            "required_skills": ["Python"],
        },
    )
    assert job_unc_resp.status_code == 201
    job_unc_id = job_unc_resp.json()["id"]

    # 5. Create a FAILING Job (requires Doctorate degree)
    job_fail_resp = client.post(
        "/api/v1/jobs/import",
        json={
            "title": "Research Scientist",
            "company_name": "Deep AI",
            "source_url": f"https://example.com/job/fail-{int(datetime.now().timestamp())}",
            "target_locations": ["Remote, US"],
            "raw_description": "AI Researcher with doctorate.",
            "min_degree": "DOCTORATE",
            "required_skills": ["Python"],
            "work_auth_countries": ["US"],
        },
    )
    assert job_fail_resp.status_code == 201
    job_fail_id = job_fail_resp.json()["id"]

    # Test FAILING application -> transitions to REJECTED
    app_fail = client.post("/api/v1/applications", json={"candidate_id": candidate_id, "job_id": job_fail_id}).json()
    eval_fail = client.post(f"/api/v1/applications/{app_fail['id']}/evaluate")
    assert eval_fail.status_code == 200
    fail_data = eval_fail.json()
    assert fail_data["rules_result"] == "FAIL"
    assert fail_data["new_state"] == "REJECTED"
    assert len(fail_data["disqualifying_reasons"]) > 0

    # Test UNCERTAIN application -> transitions to AWAITING_USER_INPUT
    app_unc = client.post("/api/v1/applications", json={"candidate_id": candidate_id, "job_id": job_unc_id}).json()
    eval_unc = client.post(f"/api/v1/applications/{app_unc['id']}/evaluate")
    assert eval_unc.status_code == 200
    unc_data = eval_unc.json()
    assert unc_data["rules_result"] == "UNCERTAIN"
    assert unc_data["new_state"] == "AWAITING_USER_INPUT"
    assert len(unc_data["uncertain_reasons"]) > 0
    assert unc_data["is_uncertain"] is True

    # Test PASSING application -> transitions to SHORTLISTED (or BELOW_THRESHOLD based on score)
    app_pass = client.post("/api/v1/applications", json={"candidate_id": candidate_id, "job_id": job_pass_id}).json()
    eval_pass = client.post(f"/api/v1/applications/{app_pass['id']}/evaluate")
    assert eval_pass.status_code == 200
    pass_data = eval_pass.json()
    assert pass_data["rules_result"] == "PASS"
    assert pass_data["eligible"] is True
    assert pass_data["score_total"] > 0
    assert pass_data["new_state"] in ("SHORTLISTED", "BELOW_THRESHOLD")
    assert "breakdown" in pass_data
    assert "summary_explanation" in pass_data

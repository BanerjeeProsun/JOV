"""Unit tests for Scorer properties and invariants (Blueprint v2.0 Section 7 & 16)."""

import pytest
from jovsi.domain.models import DegreeLevel, FactKind, JobRequirements
from jovsi.domain.provenance import ProvenanceEngine
from jovsi.domain.scoring import ScoringEngine


@pytest.fixture
def candidate_facts():
    return [
        ProvenanceEngine.create_user_fact("c1", FactKind.SKILL, "py", {"name": "Python"}),
        ProvenanceEngine.create_user_fact("c1", FactKind.SKILL, "fastapi", {"name": "FastAPI"}),
        ProvenanceEngine.create_user_fact("c1", FactKind.SKILL, "sql", {"name": "PostgreSQL"}),
        ProvenanceEngine.create_user_fact(
            "c1",
            FactKind.EXPERIENCE,
            "exp1",
            {
                "title": "Backend Engineer",
                "description": "Architected distributed API microservices with Python and FastAPI",
                "skills": ["Python", "FastAPI"],
            },
        ),
        ProvenanceEngine.create_user_fact(
            "c1",
            FactKind.EDUCATION,
            "edu1",
            {"degree_level": "BACHELOR", "field": "Computer Science", "graduation_year": 2023},
        ),
    ]


@pytest.fixture
def job_requirements():
    return JobRequirements(
        min_degree=DegreeLevel.BACHELOR,
        required_skills=["Python", "FastAPI"],
        preferred_skills=["PostgreSQL", "Docker"],
        responsibilities=["Architect distributed API microservices with Python"],
        target_role_family="Backend Engineer",
        accepted_work_modes=["remote"],
    )


def test_scorer_determinism(candidate_facts, job_requirements) -> None:
    """Scorer is a pure function: same inputs give identical outputs."""
    score1 = ScoringEngine.score_job(job_requirements, candidate_facts)
    score2 = ScoringEngine.score_job(job_requirements, candidate_facts)
    assert score1.total_score == score2.total_score
    assert score1.categories == score2.categories


def test_scorer_monotonicity_add_skill(candidate_facts, job_requirements) -> None:
    """Adding a matching verified skill never lowers the score."""
    initial = ScoringEngine.score_job(job_requirements, candidate_facts)
    # Add matching preferred skill 'Docker'
    more_facts = candidate_facts + [
        ProvenanceEngine.create_user_fact("c1", FactKind.SKILL, "docker", {"name": "Docker"})
    ]
    higher = ScoringEngine.score_job(job_requirements, more_facts)
    assert higher.total_score >= initial.total_score


def test_scorer_monotonicity_remove_skill(candidate_facts, job_requirements) -> None:
    """Removing a required skill never raises the score."""
    initial = ScoringEngine.score_job(job_requirements, candidate_facts)
    # Remove 'FastAPI' skill
    fewer_facts = [f for f in candidate_facts if f.key != "fastapi"]
    lower = ScoringEngine.score_job(job_requirements, fewer_facts)
    assert lower.total_score <= initial.total_score


def test_scorer_unrelated_facts_no_change(candidate_facts, job_requirements) -> None:
    """Adding unrelated facts does not alter the score."""
    initial = ScoringEngine.score_job(job_requirements, candidate_facts)
    unrelated = candidate_facts + [
        ProvenanceEngine.create_user_fact("c1", FactKind.SKILL, "cooking", {"name": "French Cooking"})
    ]
    after = ScoringEngine.score_job(job_requirements, unrelated)
    assert after.total_score == initial.total_score


def test_category_bounds_and_maxima(candidate_facts, job_requirements) -> None:
    """Every category's earned points never exceed its maximum, sum of category maxima is 100."""
    score = ScoringEngine.score_job(job_requirements, candidate_facts)
    assert sum(c.available_points for c in score.categories.values()) <= 100.0
    for name, cat in score.categories.items():
        assert cat.earned_points <= cat.available_points
        assert cat.earned_points >= 0.0


def test_renormalisation_and_low_confidence() -> None:
    """When job has minimal data, points are renormalised and low confidence is flagged."""
    minimal_req = JobRequirements(
        required_skills=["Python"],
        accepted_work_modes=[],  # No location data
    )
    score = ScoringEngine.score_job(
        minimal_req,
        [ProvenanceEngine.create_user_fact("c1", FactKind.SKILL, "py", {"name": "Python"})],
    )
    # Only skills (35 pts) available, which is < 50
    assert score.is_low_confidence is True
    # 35/35 earned renormalises to 100.0
    assert score.total_score == 100.0

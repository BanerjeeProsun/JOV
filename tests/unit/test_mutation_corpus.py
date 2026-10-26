"""Acceptance Gate G1: 40-Mutation Corpus Test Suite.

Proves that any unsupported skill, number, date, seniority claim, or job-text contamination
is caught and rejected by FactualConsistencyValidator, while the clean resume passes.
"""

import copy
import pytest
from jovsi.domain.models import (
    Fact,
    FactKind,
    FactProvenance,
    FactStatus,
    ResumeBullet,
    ResumeSection,
    StructuredResume,
)
from jovsi.domain.provenance import ProvenanceEngine
from jovsi.domain.validators import FactualConsistencyValidator


@pytest.fixture
def clean_setup():
    facts = [
        ProvenanceEngine.create_user_fact(
            "c1", FactKind.CONTACT, "email", {"email": "ada@example.com", "phone": "+1234567890"}
        ),
        ProvenanceEngine.create_user_fact(
            "c1", FactKind.EDUCATION, "edu", {"degree_level": "BACHELOR", "field": "Mathematics", "graduation_year": 2022}
        ),
        ProvenanceEngine.create_user_fact(
            "c1", FactKind.SKILL, "py", {"name": "Python"}
        ),
        ProvenanceEngine.create_user_fact(
            "c1", FactKind.SKILL, "sql", {"name": "SQL"}
        ),
        ProvenanceEngine.create_user_fact(
            "c1",
            FactKind.EXPERIENCE,
            "exp1",
            {
                "title": "Software Developer",
                "company": "Babbage Labs",
                "description": "Developed numerical algorithms for analytical engine with Python",
                "skills": ["Python", "SQL"],
            },
        ),
    ]

    clean_resume = StructuredResume(
        candidate_name="Ada Lovelace",
        email="ada@example.com",
        phone="+1234567890",
        sections=[
            ResumeSection(
                title="Skills",
                bullets=[
                    ResumeBullet(text="Python", fact_ids=[facts[2].id]),
                    ResumeBullet(text="SQL", fact_ids=[facts[3].id]),
                ],
            ),
            ResumeSection(
                title="Experience",
                bullets=[
                    ResumeBullet(
                        text="Developed numerical algorithms for analytical engine with Python",
                        fact_ids=[facts[4].id],
                    )
                ],
            ),
        ],
    )

    job_desc = "We are seeking a talented developer to build modern scalable cloud computing platforms."

    return facts, clean_resume, job_desc


def test_clean_resume_passes(clean_setup) -> None:
    facts, clean_resume, job_desc = clean_setup
    report = FactualConsistencyValidator.validate_resume(clean_resume, facts, job_desc)
    assert report.is_valid is True
    assert len(report.violations) == 0


# 40 Deliberate Mutations
MUTATIONS = [
    # 1-10: Invented skills in skills section
    ("SKILL_INV_1", lambda r, f: r.sections[0].bullets.append(ResumeBullet(text="Kubernetes", fact_ids=[f[2].id]))),
    ("SKILL_INV_2", lambda r, f: r.sections[0].bullets.append(ResumeBullet(text="Rust", fact_ids=[f[2].id]))),
    ("SKILL_INV_3", lambda r, f: r.sections[0].bullets.append(ResumeBullet(text="Solidity", fact_ids=[f[2].id]))),
    ("SKILL_INV_4", lambda r, f: r.sections[0].bullets.append(ResumeBullet(text="TensorFlow", fact_ids=[f[2].id]))),
    ("SKILL_INV_5", lambda r, f: r.sections[0].bullets.append(ResumeBullet(text="GraphQL", fact_ids=[f[2].id]))),
    ("SKILL_INV_6", lambda r, f: r.sections[0].bullets.append(ResumeBullet(text="Ruby", fact_ids=[f[2].id]))),
    ("SKILL_INV_7", lambda r, f: r.sections[0].bullets.append(ResumeBullet(text="C++", fact_ids=[f[2].id]))),
    ("SKILL_INV_8", lambda r, f: r.sections[0].bullets.append(ResumeBullet(text="Java", fact_ids=[f[2].id]))),
    ("SKILL_INV_9", lambda r, f: r.sections[0].bullets.append(ResumeBullet(text="AWS", fact_ids=[f[2].id]))),
    ("SKILL_INV_10", lambda r, f: r.sections[0].bullets.append(ResumeBullet(text="Kafka", fact_ids=[f[2].id]))),

    # 11-15: Inflated / unverified numbers in experience bullet
    ("NUM_INFL_1", lambda r, f: r.sections[1].bullets.append(ResumeBullet(text="Increased performance by 99%", fact_ids=[f[4].id]))),
    ("NUM_INFL_2", lambda r, f: r.sections[1].bullets.append(ResumeBullet(text="Scaled architecture across 500 servers", fact_ids=[f[4].id]))),
    ("NUM_INFL_3", lambda r, f: r.sections[1].bullets.append(ResumeBullet(text="Managed team of 25 engineers", fact_ids=[f[4].id]))),
    ("NUM_INFL_4", lambda r, f: r.sections[1].bullets.append(ResumeBullet(text="Reduced latency by 45%", fact_ids=[f[4].id]))),
    ("NUM_INFL_5", lambda r, f: r.sections[1].bullets.append(ResumeBullet(text="Built 12 independent microservices", fact_ids=[f[4].id]))),

    # 16-20: Unverified seniority / superlative words
    ("SENIOR_1", lambda r, f: r.sections[1].bullets.append(ResumeBullet(text="Senior developer who built algorithms", fact_ids=[f[4].id]))),
    ("SENIOR_2", lambda r, f: r.sections[1].bullets.append(ResumeBullet(text="Lead engineer on analytical engine", fact_ids=[f[4].id]))),
    ("SENIOR_3", lambda r, f: r.sections[1].bullets.append(ResumeBullet(text="Principal architect of algorithm suite", fact_ids=[f[4].id]))),
    ("SENIOR_4", lambda r, f: r.sections[1].bullets.append(ResumeBullet(text="Expert in all software systems", fact_ids=[f[4].id]))),
    ("SENIOR_5", lambda r, f: r.sections[1].bullets.append(ResumeBullet(text="Recognized as best contributor", fact_ids=[f[4].id]))),

    # 21-25: Structural & Citation Violations
    ("STRUCT_1", lambda r, f: r.sections[1].bullets.append(ResumeBullet.model_construct(text="Uncited statement", fact_ids=[]))),
    ("STRUCT_2", lambda r, f: r.sections[1].bullets.append(ResumeBullet(text="Statement with non-existent fact", fact_ids=["fake-id-999"]))),
    ("STRUCT_3", lambda r, f: (
        f.append(ProvenanceEngine.propose_extracted_fact("c1", FactKind.SKILL, "k", {"name": "k"}, "doc")),
        r.sections[1].bullets.append(ResumeBullet(text="Statement with proposed unverified fact", fact_ids=[f[-1].id]))
    )),
    ("STRUCT_4", lambda r, f: (
        f.append(ProvenanceEngine.reject_proposed_fact(ProvenanceEngine.propose_extracted_fact("c1", FactKind.SKILL, "k", {"name": "k"}, "doc"))),
        r.sections[1].bullets.append(ResumeBullet(text="Statement with rejected fact", fact_ids=[f[-1].id]))
    )),
    ("STRUCT_5", lambda r, f: (
        f.append(f[2].model_copy(update={"id": "superseded-fact-id", "status": FactStatus.SUPERSEDED})),
        r.sections[1].bullets.append(ResumeBullet(text="Statement with superseded fact", fact_ids=["superseded-fact-id"]))
    )),

    # 26-30: Contact info mismatches
    ("CONTACT_1", lambda r, f: setattr(r, "email", "wrong@example.com")),
    ("CONTACT_2", lambda r, f: setattr(r, "email", "ada.hacked@example.com")),
    ("CONTACT_3", lambda r, f: setattr(r, "phone", "+19999999999")),
    ("CONTACT_4", lambda r, f: setattr(r, "phone", "+1234567891")),  # one digit off
    ("CONTACT_5", lambda r, f: setattr(r, "phone", "")),

    # 31-35: Verbatim Job text contamination (> 6 words copied verbatim)
    ("CONTAM_1", lambda r, f: r.sections[1].bullets.append(ResumeBullet(text="We are seeking a talented developer to build modern scalable cloud computing platforms", fact_ids=[f[4].id]))),
    ("CONTAM_2", lambda r, f: r.sections[1].bullets.append(ResumeBullet(text="Seeking a talented developer to build modern scalable", fact_ids=[f[4].id]))),
    ("CONTAM_3", lambda r, f: r.sections[1].bullets.append(ResumeBullet(text="A talented developer to build modern scalable cloud", fact_ids=[f[4].id]))),
    ("CONTAM_4", lambda r, f: r.sections[1].bullets.append(ResumeBullet(text="Talented developer to build modern scalable cloud computing", fact_ids=[f[4].id]))),
    ("CONTAM_5", lambda r, f: r.sections[1].bullets.append(ResumeBullet(text="Developer to build modern scalable cloud computing platforms", fact_ids=[f[4].id]))),

    # 36-40: Additional unverified entities and titles
    ("ENTITY_1", lambda r, f: r.sections[1].bullets.append(ResumeBullet(text="Director of software engineering at labs", fact_ids=[f[4].id]))),
    ("ENTITY_2", lambda r, f: r.sections[1].bullets.append(ResumeBullet(text="Managed team across multiple organizations", fact_ids=[f[4].id]))),
    ("ENTITY_3", lambda r, f: r.sections[1].bullets.append(ResumeBullet(text="Spearheaded company-wide initiatives", fact_ids=[f[4].id]))),
    ("ENTITY_4", lambda r, f: r.sections[0].bullets.append(ResumeBullet(text="Haskell", fact_ids=[f[2].id]))),
    ("ENTITY_5", lambda r, f: r.sections[0].bullets.append(ResumeBullet(text="Assembly", fact_ids=[f[2].id]))),
]


assert len(MUTATIONS) == 40, f"Expected exactly 40 mutations, got {len(MUTATIONS)}"


@pytest.mark.parametrize("mutation_id, mutator", MUTATIONS)
def test_all_40_mutations_are_caught(clean_setup, mutation_id, mutator) -> None:
    facts, clean_resume, job_desc = clean_setup
    mutated_resume = copy.deepcopy(clean_resume)
    
    # Apply mutation
    mutator(mutated_resume, facts)
    
    # Validate against facts
    report = FactualConsistencyValidator.validate_resume(mutated_resume, facts, job_desc)
    assert report.is_valid is False, f"Mutation '{mutation_id}' was NOT caught by validator!"
    assert len(report.violations) > 0

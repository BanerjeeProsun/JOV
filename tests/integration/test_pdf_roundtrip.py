"""Integration test for PDF Generation and Text Round-trip Verification."""

from jovsi.domain.models import FactKind, JobRequirements
from jovsi.domain.provenance import ProvenanceEngine
from jovsi.services.resume import ResumeService


def test_resume_generation_and_pdf_roundtrip() -> None:
    facts = [
        ProvenanceEngine.create_user_fact(
            "c1", FactKind.CONTACT, "email", {"email": "grace@example.com", "phone": "+1987654321"}
        ),
        ProvenanceEngine.create_user_fact(
            "c1", FactKind.EDUCATION, "edu", {"degree_level": "DOCTORATE", "field": "Mathematics", "graduation_year": 1934}
        ),
        ProvenanceEngine.create_user_fact(
            "c1", FactKind.SKILL, "cobol", {"name": "COBOL"}
        ),
        ProvenanceEngine.create_user_fact(
            "c1", FactKind.SKILL, "compilers", {"name": "Compilers"}
        ),
        ProvenanceEngine.create_user_fact(
            "c1",
            FactKind.EXPERIENCE,
            "exp1",
            {
                "title": "Computer Pioneer",
                "company": "US Navy",
                "description": "Developed the first compiler for programming languages",
                "skills": ["Compilers"],
            },
        ),
    ]

    req = JobRequirements(required_skills=["COBOL", "Compilers"])

    # 1. Deterministic resume generation
    resume, report = ResumeService.generate_deterministic_resume(
        candidate_name="Grace Hopper",
        facts=facts,
        requirements=req,
    )
    assert report.is_valid is True
    assert len(resume.sections) >= 3

    # 2. Render text PDF bytes
    pdf_bytes = ResumeService.render_pdf_bytes(resume)
    assert len(pdf_bytes) > 0
    assert pdf_bytes.startswith(b"%PDF")

    # 3. Round-trip check
    verified = ResumeService.verify_pdf_roundtrip(pdf_bytes, resume)
    assert verified is True

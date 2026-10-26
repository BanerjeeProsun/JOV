"""Integration and unit tests for Master Resume upload, parsing, and provenance verification."""

import io
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from jovsi.api.main import app
from jovsi.adapters.db.session import init_db, get_db
from jovsi.domain.models import FactStatus, FactProvenance
from jovsi.services.resume_parser import MasterResumeParser, ResumeParsingError


def test_master_resume_parser_text_extraction():
    sample_text = """
    Jane Doe
    jane.doe@example.com | +1 555-019-2834 | San Francisco, CA
    https://linkedin.com/in/janedoe | https://github.com/janedoe

    EDUCATION
    Master of Science in Computer Science, Stanford University, 2023

    WORK EXPERIENCE
    Senior Backend Engineer | CloudScale Inc | 2021 - 2023
    Architected high-concurrency microservices using Python, FastAPI, and PostgreSQL.
    Led migration of monolithic infrastructure to Docker and Kubernetes.

    TECHNICAL SKILLS
    Languages: Python, Go, TypeScript, SQL
    Frameworks: FastAPI, React, Django
    Infrastructure: Docker, Kubernetes, AWS, PostgreSQL, Redis
    """

    entities = MasterResumeParser.extract_structured_entities(sample_text)
    assert entities["name"] == "Jane Doe"
    assert entities["contact"]["email"] == "jane.doe@example.com"
    assert entities["contact"]["phone"] == "+1 555-019-2834"
    assert "FastAPI" in entities["skills"]
    assert "Python" in entities["skills"]
    assert "Docker" in entities["skills"]
    assert len(entities["education"]) > 0
    assert entities["education"][0]["degree_level"] == "MASTER"
    assert entities["education"][0]["graduation_year"] == 2023


def test_master_resume_docx_parsing():
    import docx
    doc = docx.Document()
    doc.add_heading("Marcus Aurelius", level=0)
    doc.add_paragraph("marcus@philosophy.org | +1 202-555-0199 | Rome, Italy")
    doc.add_heading("Education", level=1)
    doc.add_paragraph("Bachelor of Arts in Philosophy and Logic, University of Athens, 2020")
    doc.add_heading("Work Experience", level=1)
    doc.add_paragraph("Lead Systems Architect | Pax Romana Ltd | 2020 - 2023")
    doc.add_paragraph("Engineered distributed governance infrastructure with Python and Docker.")
    doc.add_heading("Skills", level=1)
    doc.add_paragraph("Python, Docker, SQL, Kubernetes, Git")

    stream = io.BytesIO()
    doc.save(stream)
    docx_bytes = stream.getvalue()

    extracted_text = MasterResumeParser.extract_text_from_bytes(docx_bytes, "marcus_resume.docx")
    assert "Marcus Aurelius" in extracted_text
    assert "marcus@philosophy.org" in extracted_text

    entities = MasterResumeParser.extract_structured_entities(extracted_text)
    assert entities["name"] == "Marcus Aurelius"
    assert entities["contact"]["email"] == "marcus@philosophy.org"
    assert "Python" in entities["skills"]
    assert "Docker" in entities["skills"]


def test_master_resume_parser_scanned_pdf_rejection():
    # An empty or near-empty text PDF should be rejected as scanned or insufficient
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    pdf_bytes = io.BytesIO()
    writer.write(pdf_bytes)
    content = pdf_bytes.getvalue()

    with pytest.raises(ResumeParsingError) as exc_info:
        MasterResumeParser.extract_text_from_bytes(content, "scanned_doc.pdf")
    assert "scanned image or contains insufficient extractable text" in str(exc_info.value)


def test_master_resume_upload_and_fact_confirmation_flow(tmp_path):
    db_file = tmp_path / "resume_test.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    init_db(engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    # 1. Create candidate
    r_cand = client.post("/api/v1/candidates", json={"display_name": "New Candidate", "timezone": "Asia/Kolkata"})
    assert r_cand.status_code == 201
    cand_id = r_cand.json()["id"]

    # Check status before upload
    r_stat0 = client.get(f"/api/v1/candidates/{cand_id}/master-resume")
    assert r_stat0.status_code == 200
    assert r_stat0.json()["has_master_resume"] is False

    # 2. Upload text resume
    resume_content = """
    Alex Mercer
    alex.mercer@protonmail.com | +1 415-555-2671 | Seattle, WA
    https://github.com/alexmercer

    EDUCATION
    Bachelor of Science in Mathematics and Computer Science, University of Washington, 2022

    EXPERIENCE
    Distributed Systems Engineer | Apex Systems | 2022 - 2024
    Designed robust asynchronous queue workers in Python and Go with Redis and PostgreSQL.

    SKILLS
    Python, Go, FastAPI, PostgreSQL, Redis, Docker, Git
    """
    files = {"file": ("alex_mercer_resume.txt", io.BytesIO(resume_content.encode("utf-8")), "text/plain")}
    r_upload = client.post(f"/api/v1/candidates/{cand_id}/resume/upload", files=files)
    assert r_upload.status_code == 201
    data = r_upload.json()
    assert data["filename"] == "alex_mercer_resume.txt"
    assert data["entities"]["name"] == "Alex Mercer"
    assert data["total_facts_extracted"] > 0

    # 3. Verify extracted facts are PROPOSED and not usable yet
    doc_id = data["document_id"]
    r_facts = client.get(f"/api/v1/candidates/{cand_id}/facts")
    assert r_facts.status_code == 200
    facts_list = r_facts.json()
    assert all(f["status"] == "PROPOSED" for f in facts_list)
    assert all(f["is_usable"] is False for f in facts_list)

    # 4. Confirm one fact individually
    first_fact_id = facts_list[0]["id"]
    r_conf = client.post(f"/api/v1/facts/{first_fact_id}/confirm")
    assert r_conf.status_code == 200
    assert r_conf.json()["status"] == "ACTIVE"
    assert r_conf.json()["is_usable"] is True

    # 5. Confirm remaining facts via confirm-all
    r_conf_all = client.post(f"/api/v1/candidates/{cand_id}/confirm-all-facts")
    assert r_conf_all.status_code == 200
    updated_facts = r_conf_all.json()
    assert all(f["status"] == "ACTIVE" for f in updated_facts)
    assert all(f["is_usable"] is True for f in updated_facts)

    # 6. Verify master resume status
    r_stat = client.get(f"/api/v1/candidates/{cand_id}/master-resume")
    assert r_stat.status_code == 200
    stat_data = r_stat.json()
    assert stat_data["has_master_resume"] is True
    assert stat_data["active_facts"] == len(updated_facts)
    assert stat_data["proposed_facts"] == 0

    # 7. Test download
    r_dl = client.get(f"/api/v1/documents/{doc_id}/download")
    assert r_dl.status_code == 200
    assert b"alex.mercer@protonmail.com" in r_dl.content

    app.dependency_overrides.clear()

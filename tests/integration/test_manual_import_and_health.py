"""Integration tests for Manual Import, URL Ingestion, Restricted Board Policies, and Health Telemetry."""

from unittest.mock import MagicMock, patch
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from jovsi.adapters.db.models import JobDB, JobLocationDB
from jovsi.adapters.db.session import init_db, get_db
from jovsi.api.main import app
from jovsi.config import settings


@pytest.fixture
def test_client_and_db(tmp_path):
    db_file = tmp_path / "manual_import_test.db"
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
    yield client, TestingSession
    app.dependency_overrides.clear()


def test_import_job_from_greenhouse_url(test_client_and_db):
    client, TestingSession = test_client_and_db

    mock_gh_data = {
        "title": "Principal Systems Engineer",
        "location": {"name": "Austin, TX"},
        "content": "<p>Build high-performance distributed edge systems with <strong>Rust</strong> and <strong>Linux</strong>.</p>",
    }
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_gh_data

    # Mock DNS resolution for boards.greenhouse.io to public IP
    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("104.18.2.1", 443))]):
        with patch("jovsi.services.manual_import.httpx.Client.get", return_value=mock_resp):
            payload = {"url": "https://boards.greenhouse.io/cloudflare/jobs/998877"}
            resp = client.post("/api/v1/jobs/import/url", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["title_norm"] == "Principal Systems Engineer"
            assert data["company_norm"] == "Cloudflare"
            assert data["source"] == "greenhouse"

            # Check that job_locations was populated
            with TestingSession() as db:
                loc_rows = db.scalars(select(JobLocationDB).where(JobLocationDB.job_id == data["id"])).all()
                assert len(loc_rows) >= 1
                assert loc_rows[0].country_code == "US"
                assert loc_rows[0].admin1_code == "TX"
                assert loc_rows[0].city_id == "city_us_austin"


def test_import_job_from_generic_webpage_jsonld(test_client_and_db):
    client, TestingSession = test_client_and_db

    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": "JobPosting",
            "title": "Senior Backend Architect",
            "hiringOrganization": {
                "@type": "Organization",
                "name": "Stripe"
            },
            "jobLocation": {
                "@type": "Place",
                "address": {
                    "@type": "PostalAddress",
                    "addressLocality": "Dublin",
                    "addressCountry": "IE"
                }
            },
            "description": "<p>Design core financial ledger infrastructure using Python, Go, and PostgreSQL.</p>"
        }
        </script>
    </head>
    <body><h1>Job details</h1></body>
    </html>
    """

    mock_fetch_resp = MagicMock(spec=httpx.Response)
    mock_fetch_resp.status_code = 200
    mock_fetch_resp.text = html_content

    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("151.101.1.1", 443))]):
        with patch("jovsi.services.manual_import.SSRFSafeFetcher.fetch", return_value=mock_fetch_resp):
            payload = {"url": "https://careers.stripe.com/jobs/senior-backend-architect-123"}
            resp = client.post("/api/v1/jobs/import/url", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["title_norm"] == "Senior Backend Architect"
            assert data["company_norm"] == "Stripe"
            assert data["source"] == "web_import"

            # Check location indexing
            with TestingSession() as db:
                loc_rows = db.scalars(select(JobLocationDB).where(JobLocationDB.job_id == data["id"])).all()
                assert len(loc_rows) >= 1
                assert loc_rows[0].country_code == "IE"
                assert loc_rows[0].city_id == "city_ie_dublin"


def test_import_restricted_board_url_returns_actionable_error(test_client_and_db):
    client, _ = test_client_and_db

    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("108.174.10.10", 443))]):
        # Attempt to import LinkedIn job URL directly
        payload = {"url": "https://www.linkedin.com/jobs/view/3920192837"}
        resp = client.post("/api/v1/jobs/import/url", json=payload)
        assert resp.status_code == 422
        err = resp.json()
        assert "detail" in err
        assert "restricted by Linkedin's Terms of Service" in err["detail"]
        assert "paste the job description text directly" in err["detail"]


def test_manual_text_import_sanitizes_and_indexes_locations(test_client_and_db):
    client, TestingSession = test_client_and_db

    payload = {
        "source": "manual_import",
        "source_url": "https://example.com/careers/lead-dev",
        "company_name": "Flipkart",
        "title": "Lead Software Engineer",
        "raw_description": (
            "We are hiring a Lead Engineer in Bengaluru, Karnataka, India. "
            "<script>alert('pwned')</script> Experience with Python, Java, and Redis required."
        ),
        "target_locations": ["Bengaluru, Karnataka, India"],
        "required_skills": ["Python", "Java", "Redis"],
    }

    resp = client.post("/api/v1/jobs/import", json=payload)
    assert resp.status_code == 201
    job_data = resp.json()
    assert "<script>" not in job_data["description_clean"]
    assert "alert('pwned')" not in job_data["description_clean"]
    assert "Experience with Python" in job_data["description_clean"]

    with TestingSession() as db:
        loc_rows = db.scalars(select(JobLocationDB).where(JobLocationDB.job_id == job_data["id"])).all()
        assert len(loc_rows) >= 1
        assert loc_rows[0].country_code == "IN"
        assert loc_rows[0].admin1_code == "KA"
        assert loc_rows[0].city_id == "city_in_bengaluru"


def test_deep_links_endpoint(test_client_and_db):
    client, _ = test_client_and_db

    resp = client.get("/api/v1/jobs/deep-links?query=Golang&location=Berlin")
    assert resp.status_code == 200
    links = resp.json()
    assert len(links) >= 6

    li_item = next(item for item in links if item["id"] == "linkedin")
    assert "keywords=Golang" in li_item["url"]
    assert "location=Berlin" in li_item["url"]
    assert li_item["policy_status"] == "BA"

    indeed_item = next(item for item in links if item["id"] == "indeed")
    assert "q=Golang" in indeed_item["url"]
    assert "l=Berlin" in indeed_item["url"]


def test_sources_health_endpoint(test_client_and_db):
    client, _ = test_client_and_db

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {}

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.get.return_value = mock_resp

    with patch("jovsi.services.job_discovery.httpx.Client", return_value=mock_client):
        resp = client.get("/api/v1/jobs/sources/health")
        assert resp.status_code == 200
        health = resp.json()
        assert len(health) >= 8

        providers = [h["provider"] for h in health]
        assert "greenhouse" in providers
        assert "lever" in providers
        assert "ashby" in providers
        assert "smartrecruiters" in providers
        assert "jobicy" in providers
        assert "arbeitnow" in providers
        assert "adzuna" in providers
        assert "remotive" in providers
        assert "manual" in providers

        # Adzuna without credentials must be UNCONFIGURED
        adzuna = next(h for h in health if h["provider"] == "adzuna")
        assert adzuna["status"] == "UNCONFIGURED"
        assert "CREDENTIALS" in adzuna["error"]

        # Manual must be HEALTHY
        manual = next(h for h in health if h["provider"] == "manual")
        assert manual["status"] == "HEALTHY"

"""Integration tests for Source Registry, real ATS connectors, and dynamic prober."""

from unittest.mock import MagicMock, patch
import pytest
import httpx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from jovsi.api.main import app
from jovsi.adapters.db.session import init_db, get_db
from jovsi.services.job_discovery import (
    AshbyConnector,
    SmartRecruitersConnector,
    SourceRegistryService,
)


@pytest.fixture
def test_client_and_db(tmp_path):
    db_file = tmp_path / "sources_test.db"
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


def test_registered_sources_returns_real_providers(test_client_and_db):
    client, _ = test_client_and_db
    resp = client.get("/api/v1/jobs/sources")
    assert resp.status_code == 200
    sources = resp.json()
    assert len(sources) >= 6
    provider_ids = [s["id"] for s in sources]
    assert "greenhouse" in provider_ids
    assert "lever" in provider_ids
    assert "ashby" in provider_ids
    assert "smartrecruiters" in provider_ids
    assert "jobicy" in provider_ids
    assert "manual" in provider_ids

    # Verify employer counts are populated from DB
    greenhouse_src = next(s for s in sources if s["id"] == "greenhouse")
    assert greenhouse_src["employer_count"] >= 4


def test_list_and_add_employer_source(test_client_and_db):
    client, _ = test_client_and_db

    # 1. List seeded employers
    resp = client.get("/api/v1/jobs/sources/employers")
    assert resp.status_code == 200
    employers = resp.json()
    assert len(employers) >= 10
    names = [e["employer_name"] for e in employers]
    assert "Cloudflare" in names
    assert "Ramp" in names
    assert "Linear" in names

    # 2. Add a new employer
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "jobs": [
            {"id": "j1", "title": "Staff Engineer", "location": "San Francisco, CA"}
        ]
    }

    with patch("httpx.Client.get", return_value=mock_resp):
        new_emp = {
            "provider": "ashby",
            "employer_name": "OpenAI",
            "board_identifier": "openai",
        }
        r_add = client.post("/api/v1/jobs/sources/employers", json=new_emp)
        assert r_add.status_code == 201
        data = r_add.json()
        assert data["employer_name"] == "OpenAI"
        assert data["board_identifier"] == "openai"
        assert data["status"] == "verified_active"
        assert data["last_job_count"] == 1
        assert data["last_probed_at"] is not None


def test_probe_employer_source(test_client_and_db):
    client, TestingSession = test_client_and_db

    # Get one employer
    r_list = client.get("/api/v1/jobs/sources/employers?provider=greenhouse")
    assert r_list.status_code == 200
    first_id = r_list.json()[0]["id"]

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "jobs": [
            {"id": 101, "title": "Systems Engineer", "location": {"name": "Austin, TX"}}
        ]
    }

    with patch("httpx.Client.get", return_value=mock_resp):
        r_probe = client.post(f"/api/v1/jobs/sources/{first_id}/probe")
        assert r_probe.status_code == 200
        data = r_probe.json()
        assert data["status"] == "verified_active"
        assert data["last_job_count"] == 1


def test_ashby_and_smartrecruiters_connectors():
    # Test Ashby connector parsing
    ashby = AshbyConnector()
    mock_ashby_resp = MagicMock(spec=httpx.Response)
    mock_ashby_resp.status_code = 200
    mock_ashby_resp.json.return_value = {
        "jobs": [
            {
                "id": "ashby-99",
                "title": "Backend Python Engineer",
                "location": "Remote - US",
                "jobUrl": "https://jobs.ashbyhq.com/test/ashby-99",
                "descriptionPlain": "Build robust FastAPI services with PostgreSQL and Redis.",
            }
        ]
    }

    with patch("httpx.Client.get", return_value=mock_ashby_resp):
        res = ashby.search(query="Python", company="test", limit=5)
        assert len(res) == 1
        assert res[0]["source"] == "ashby"
        assert res[0]["title"] == "Backend Python Engineer"
        assert "FastAPI" in res[0]["required_skills"]

    # Test SmartRecruiters connector parsing
    sr = SmartRecruitersConnector()
    mock_sr_resp = MagicMock(spec=httpx.Response)
    mock_sr_resp.status_code = 200
    mock_sr_resp.json.return_value = {
        "content": [
            {
                "id": "sr-100",
                "name": "Senior Software Architect",
                "location": {"city": "New York", "region": "NY", "country": "US"},
            }
        ]
    }

    with patch("httpx.Client.get", return_value=mock_sr_resp):
        res = sr.search(query="", company="visa", limit=5)
        assert len(res) == 1
        assert res[0]["source"] == "smartrecruiters"
        assert res[0]["title"] == "Senior Software Architect"
        assert "New York" in res[0]["location"]

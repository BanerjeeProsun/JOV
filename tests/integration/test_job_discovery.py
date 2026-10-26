"""Tests for Job Discovery Service and API endpoints."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from jovsi.api.main import app
from jovsi.adapters.db.session import init_db, get_db
from jovsi.services.job_discovery import JobDiscoveryService, GreenhouseConnector, LeverConnector


def test_registered_sources_endpoint():
    client = TestClient(app)
    resp = client.get("/api/v1/jobs/sources")
    assert resp.status_code == 200
    sources = resp.json()
    assert len(sources) >= 3
    source_ids = [s["id"] for s in sources]
    assert "greenhouse" in source_ids
    assert "lever" in source_ids
    assert "jobicy" in source_ids


def test_discover_jobs_service_greenhouse():
    # Test greenhouse search for cloudflare board with limit=3
    connector = GreenhouseConnector()
    results = connector.search(query="", company="cloudflare", limit=3)
    assert isinstance(results, list)
    if len(results) > 0:
        first = results[0]
        assert first["source"] == "greenhouse"
        assert "cloudflare" in first["source_url"].lower()
        assert len(first["title"]) > 0


def test_discover_jobs_api_endpoint(tmp_path):
    db_file = tmp_path / "discover_test.db"
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

    # 1. Discover jobs from greenhouse
    resp = client.post("/api/v1/jobs/discover", json={"source": "greenhouse", "company": "cloudflare", "limit": 3})
    assert resp.status_code == 200
    data = resp.json()
    assert "source_status" in data
    assert "greenhouse" in data["source_status"]
    assert data["total_found"] >= 0

    app.dependency_overrides.clear()

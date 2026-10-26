"""Contract tests for Aggregator Connectors (Jobicy, Arbeitnow, Adzuna, Remotive) and Deep Links."""

from unittest.mock import MagicMock, patch
import httpx
import pytest

from jovsi.config import settings
from jovsi.services.deep_links import DeepLinksService
from jovsi.services.job_discovery import (
    AdzunaConnector,
    ArbeitnowConnector,
    JobicyConnector,
    RemotiveConnector,
)


# Recorded contract response fixtures
JOBICY_FIXTURE = {
    "jobs": [
        {
            "id": 12345,
            "url": "https://jobicy.com/jobs/12345-senior-python-engineer",
            "jobTitle": "Senior Python Backend Engineer",
            "companyName": "Acme Cloud Corp",
            "jobGeo": "Remote - USA Only",
            "jobDescription": "<p>We are seeking a <strong>Senior Python Backend Engineer</strong> with deep FastAPI, Docker, and AWS experience.</p>",
            "pubDate": "2026-10-25T12:00:00Z",
            "jobType": "Full-Time",
        },
        {
            "id": 12346,
            "url": "https://jobicy.com/jobs/12346-frontend-engineer",
            "jobTitle": "React TypeScript Engineer",
            "companyName": "DesignWorks",
            "jobGeo": "Anywhere",
            "jobDescription": "<p>Build modern React and TypeScript web applications.</p>",
            "pubDate": "2026-10-24T10:00:00Z",
            "jobType": "Contract",
        },
    ]
}

ARBEITNOW_FIXTURE = {
    "data": [
        {
            "slug": "staff-platform-engineer-berlin-100",
            "company_name": "SoundCloud",
            "title": "Staff Platform Engineer",
            "description": "<p>Manage Kubernetes clusters, Terraform infrastructure, and Go microservices in Berlin or Remote.</p>",
            "remote": True,
            "url": "https://www.arbeitnow.com/view/staff-platform-engineer-100",
            "tags": ["Kubernetes", "Go", "Docker", "DevOps"],
            "job_types": ["Full-Time"],
            "location": "Berlin, Germany",
            "created_at": 1729000000,
        },
        {
            "slug": "frontend-dev-munich-200",
            "company_name": "BMW Tech",
            "title": "Senior Vue Developer",
            "description": "<p>Onsite role in Munich working with Vue and TypeScript.</p>",
            "remote": False,
            "url": "https://www.arbeitnow.com/view/senior-vue-developer-200",
            "tags": ["Vue", "TypeScript"],
            "job_types": ["Full-Time"],
            "location": "Munich, Germany",
            "created_at": 1729100000,
        },
    ],
    "links": {"next": None},
    "meta": {"current_page": 1},
}

ADZUNA_FIXTURE = {
    "results": [
        {
            "id": "adzuna-9001",
            "title": "Lead Software Engineer - Python",
            "description": "Lead engineering teams building Python, PostgreSQL, and AWS systems.",
            "redirect_url": "https://www.adzuna.com/land/ad/9001",
            "company": {"display_name": "Fintech Solutions Ltd"},
            "location": {"display_name": "London, UK", "area": ["UK", "London"]},
            "salary_min": 85000,
            "salary_max": 110000,
        }
    ]
}

REMOTIVE_FIXTURE = {
    "jobs": [
        {
            "id": 88001,
            "url": "https://remotive.com/remote-jobs/software-dev/fullstack-88001",
            "title": "Fullstack Python & React Engineer",
            "company_name": "Automattic",
            "candidate_required_location": "Worldwide",
            "description": "<p>Work from anywhere. Python, React, PostgreSQL.</p>",
            "tags": ["python", "react", "remote"],
        }
    ]
}


def test_jobicy_connector_contract():
    connector = JobicyConnector()
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = JOBICY_FIXTURE

    with patch("httpx.Client.get", return_value=mock_resp):
        # 1. Search without query
        results = connector.search(limit=5)
        assert len(results) == 2
        item0 = results[0]
        assert item0["source"] == "jobicy"
        assert item0["title"] == "Senior Python Backend Engineer"
        assert item0["company_name"] == "Acme Cloud Corp"
        assert "Python" in item0["required_skills"]
        assert item0["accepted_work_modes"] == ["remote"]

        # 2. Filter with query
        py_results = connector.search(query="Python", limit=5)
        assert len(py_results) == 1
        assert py_results[0]["company_name"] == "Acme Cloud Corp"


def test_arbeitnow_connector_contract():
    connector = ArbeitnowConnector()
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = ARBEITNOW_FIXTURE

    with patch("httpx.Client.get", return_value=mock_resp):
        # 1. Search without query
        results = connector.search(limit=5)
        assert len(results) == 2
        item0 = results[0]
        assert item0["source"] == "arbeitnow"
        assert item0["company_name"] == "SoundCloud"
        assert item0["title"] == "Staff Platform Engineer"
        assert item0["location"] == "Berlin, Germany"
        assert "Kubernetes" in item0["required_skills"]
        assert item0["accepted_work_modes"] == ["remote"]

        # 2. Filter by query matching tag
        k8s_results = connector.search(query="Kubernetes", limit=5)
        assert len(k8s_results) == 1
        assert k8s_results[0]["company_name"] == "SoundCloud"

        # 3. Filter by location
        munich_results = connector.search(location="Munich", limit=5)
        assert len(munich_results) == 1
        assert munich_results[0]["company_name"] == "BMW Tech"


def test_adzuna_connector_unconfigured_behavior():
    connector = AdzunaConnector()
    with patch.object(settings, "ADZUNA_APP_ID", None), patch.object(settings, "ADZUNA_API_KEY", None):
        # When credentials not configured, must return empty list gracefully without throwing
        results = connector.search(query="engineer", limit=5)
        assert results == []


def test_adzuna_connector_configured_contract():
    connector = AdzunaConnector()
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = ADZUNA_FIXTURE

    with patch.object(settings, "ADZUNA_APP_ID", "mock_app_id"), patch.object(settings, "ADZUNA_API_KEY", "mock_key"):
        with patch("httpx.Client.get", return_value=mock_resp):
            results = connector.search(query="Python", location="London, UK", limit=5)
            assert len(results) == 1
            item = results[0]
            assert item["source"] == "adzuna"
            assert item["company_name"] == "Fintech Solutions Ltd"
            assert item["title"] == "Lead Software Engineer - Python"
            assert item["location"] == "London, UK"
            assert "Python" in item["required_skills"]


def test_remotive_connector_contract():
    connector = RemotiveConnector()
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = REMOTIVE_FIXTURE

    with patch("httpx.Client.get", return_value=mock_resp):
        results = connector.search(query="Python", limit=5)
        assert len(results) == 1
        item = results[0]
        assert item["source"] == "remotive"
        assert item["company_name"] == "Automattic"
        assert item["title"] == "Fullstack Python & React Engineer"
        assert item["accepted_work_modes"] == ["remote"]


def test_deep_links_service_restricted_boards():
    links = DeepLinksService.generate_links(query="Python Developer", location="Bengaluru")
    assert len(links) >= 6

    ids = [l["id"] for l in links]
    assert "linkedin" in ids
    assert "indeed" in ids
    assert "naukri" in ids
    assert "wellfound" in ids
    assert "internshala" in ids
    assert "foundit" in ids

    # Check LinkedIn URL formatting
    li = next(l for l in links if l["id"] == "linkedin")
    assert "keywords=Python+Developer" in li["url"]
    assert "location=Bengaluru" in li["url"]
    assert li["policy_status"] == "BA"
    assert "Anti-scraping" in li["policy_reason"]

    # Check Naukri slug format
    naukri = next(l for l in links if l["id"] == "naukri")
    assert "naukri.com/python-developer-jobs-in-bengaluru" in naukri["url"]

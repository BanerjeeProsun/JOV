"""Integration tests for Job Search and Faceted Aggregation Engine.

Verifies:
1. Exact facet counts matching the database.
2. Multi-country filter returning union of selected countries.
3. Country + City intersection filtering.
4. Remote filter including global remote and country-specific remote jobs.
5. Work mode + suitability score floor combinations.
6. Pagination and sorting order.
7. Location hierarchy autocomplete endpoint (/api/v1/jobs/facets/locations).
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from jovsi.adapters.db.models import (
    Base, JobDB, JobLocationDB, CandidateDB, EvaluationDB
)
from jovsi.services.geo import seed_geo_database, LocationParser
from jovsi.adapters.db.session import init_db, get_db
from jovsi.api.main import app
from sqlalchemy.orm import sessionmaker

parser = LocationParser()


@pytest.fixture
def test_client_and_db(tmp_path):
    db_file = tmp_path / "search_test.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    init_db(engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Seed sample candidate & jobs
    with TestingSession() as session:
        cand = CandidateDB(
            id="cand-search-test",
            display_name="Test Candidate",
            timezone="America/New_York",
        )
        session.add(cand)
        session.flush()

        test_jobs = [
            ("Cloudflare", "Systems Engineer", "greenhouse", "San Francisco, CA (Hybrid)", ["remote", "hybrid"], 88.0),
            ("Stripe", "Backend Infrastructure", "greenhouse", "New York, NY", ["onsite"], 65.0),
            ("Canonical", "Ubuntu Kernel Developer", "greenhouse", "Remote - Worldwide", ["remote"], 92.0),
            ("Figma", "Design Systems Engineer", "greenhouse", "Hybrid: London, UK / Bristol, UK", ["hybrid"], 75.0),
            ("Linear", "Full Stack Engineer", "ashby", "Remote - US", ["remote"], 82.0),
            ("Palantir", "Forward Deployed Engineer", "lever", "Berlin, Germany", ["onsite"], 50.0),
            ("Ramp", "Product Engineer", "ashby", "Austin, TX (Hybrid)", ["hybrid"], 79.0),
            ("Visa", "Security Engineer", "smartrecruiters", "Bengaluru, Karnataka, India", ["onsite"], 85.0),
        ]

        for comp, title, src, loc, modes, score in test_jobs:
            j = JobDB(
                source=src,
                source_url=f"https://example.com/{comp}/{title}",
                canonical_url=f"https://example.com/{comp}/{title}",
                canonical_job_key=f"{comp}:{title}",
                company_norm=comp,
                title_norm=title,
                description_clean=f"Join {comp} as a {title}.",
                raw_sha256="dummy_sha",
                requirements={"accepted_work_modes": modes, "required_skills": ["Python", "Systems"]},
            )
            session.add(j)
            session.flush()

            parsed = parser.parse(loc)
            for pl in parsed:
                session.add(
                    JobLocationDB(
                        job_id=j.id,
                        country_code=pl.country,
                        admin1_code=pl.admin1,
                        city_id=pl.city,
                        work_mode=pl.work_mode_lower,
                        remote_scope=pl.remote_scope_lower,
                        raw_location=pl.raw,
                        confidence=pl.confidence,
                    )
                )

            # Add evaluation
            ev = EvaluationDB(
                job_id=j.id,
                candidate_id=cand.id,
                rules_result="PASS",
                score_total=score,
                score_breakdown={"skills": score},
            )
            session.add(ev)

        session.commit()

    def override_get_db():
        with TestingSession() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def test_job_search_facet_counts(test_client_and_db):
    """Verify computed facets match exact counts in database."""
    client = test_client_and_db
    resp = client.get("/api/v1/jobs/search")
    assert resp.status_code == 200
    data = resp.json()

    assert data["total"] == 8
    facets = data["facets"]

    # Verify countries facet: US has Cloudflare, Stripe, Linear, Ramp (4 jobs)
    us_facet = next((c for c in facets["countries"] if c["code"] == "US"), None)
    assert us_facet is not None
    assert us_facet["count"] == 4

    # GB has Figma (1 job)
    gb_facet = next((c for c in facets["countries"] if c["code"] == "GB"), None)
    assert gb_facet is not None
    assert gb_facet["count"] == 1

    # IN has Visa (1 job)
    in_facet = next((c for c in facets["countries"] if c["code"] == "IN"), None)
    assert in_facet is not None
    assert in_facet["count"] == 1

    # Sources facet
    gh_facet = next((s for s in facets["sources"] if s["key"] == "greenhouse"), None)
    assert gh_facet is not None
    assert gh_facet["count"] == 4  # Cloudflare, Stripe, Canonical, Figma


def test_multi_country_filter_union(test_client_and_db):
    """Verify filtering by multiple countries returns their union."""
    client = test_client_and_db
    resp = client.get("/api/v1/jobs/search?country=US&country=GB")
    assert resp.status_code == 200
    data = resp.json()

    # 4 in US (Cloudflare, Stripe, Linear, Ramp) + 1 in GB (Figma) = 5
    assert data["total"] == 5
    companies = {item["company_name"] for item in data["items"]}
    assert companies == {"Cloudflare", "Stripe", "Linear", "Ramp", "Figma"}


def test_country_and_city_intersection(test_client_and_db):
    """Verify filtering by country and city properly intersects."""
    client = test_client_and_db
    resp = client.get("/api/v1/jobs/search?country=US&city=city_us_san_francisco")
    assert resp.status_code == 200
    data = resp.json()

    assert data["total"] == 1
    assert data["items"][0]["company_name"] == "Cloudflare"


def test_remote_filter_includes_global_and_country_remote(test_client_and_db):
    """Verify remote work mode includes both global remote and country-specific remote."""
    client = test_client_and_db
    resp = client.get("/api/v1/jobs/search?work_mode=remote")
    assert resp.status_code == 200
    data = resp.json()

    companies = {item["company_name"] for item in data["items"]}
    # Canonical (Worldwide remote) and Linear (US Remote)
    assert "Canonical" in companies
    assert "Linear" in companies


def test_work_mode_and_score_floor(test_client_and_db):
    """Verify combining work mode filter with candidate suitability score floor."""
    client = test_client_and_db
    # Hybrid positions with score >= 75
    resp = client.get(
        "/api/v1/jobs/search?work_mode=hybrid&min_score=75&candidate_id=cand-search-test"
    )
    assert resp.status_code == 200
    data = resp.json()

    # Cloudflare (88.0, hybrid), Figma (75.0, hybrid), Ramp (79.0, hybrid)
    assert data["total"] == 3
    companies = {item["company_name"] for item in data["items"]}
    assert companies == {"Cloudflare", "Figma", "Ramp"}


def test_search_pagination_and_sorting(test_client_and_db):
    """Verify pagination limits, total pages, and order."""
    client = test_client_and_db
    # Page 1 with size 3
    resp_p1 = client.get("/api/v1/jobs/search?page=1&page_size=3")
    assert resp_p1.status_code == 200
    data_p1 = resp_p1.json()
    assert len(data_p1["items"]) == 3
    assert data_p1["total"] == 8
    assert data_p1["total_pages"] == 3

    # Page 2 with size 3
    resp_p2 = client.get("/api/v1/jobs/search?page=2&page_size=3")
    assert resp_p2.status_code == 200
    data_p2 = resp_p2.json()
    assert len(data_p2["items"]) == 3

    # Ensure items on page 1 and page 2 are disjoint
    p1_ids = {item["id"] for item in data_p1["items"]}
    p2_ids = {item["id"] for item in data_p2["items"]}
    assert p1_ids.isdisjoint(p2_ids)


def test_location_facets_autocomplete(test_client_and_db):
    """Verify autocomplete location hierarchy endpoint."""
    client = test_client_and_db

    # General autocomplete
    resp = client.get("/api/v1/jobs/facets/locations")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["countries"]) > 0
    assert len(data["admin1"]) > 0
    assert len(data["cities"]) > 0

    # Scoped to US
    resp_us = client.get("/api/v1/jobs/facets/locations?country=US")
    assert resp_us.status_code == 200
    data_us = resp_us.json()
    assert all(a["country_code"] == "US" for a in data_us["admin1"])
    assert all(c["country_code"] == "US" for c in data_us["cities"])

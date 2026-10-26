"""Full End-to-End Playwright UI Vertical-Slice Test for JOV.si.

Tests the actual compiled React SPA frontend interacting with the FastAPI backend
and hostile mock portal through a real headless Chromium browser session.
Verifies all 8 screens, zero fabricated metrics, gate-locked approval, and Playwright submission.
"""

import threading
import time
import uuid
import pytest
import uvicorn
import httpx
from playwright.async_api import async_playwright
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from jovsi.config import settings
from jovsi.api.main import app
from jovsi.adapters.db.session import init_db, get_db
from jovsi.adapters.db.models import CandidateDB, FactDB
from mock_portal.server import reset_mock_portal


@pytest.mark.asyncio
async def test_full_ui_vertical_slice_in_browser(mock_server, tmp_path) -> None:
    # 1. Prepare isolated database
    db_file = tmp_path / "ui_test.db"
    db_url = f"sqlite:///{db_file}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    init_db(engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Seed isolated test candidate fixture for the E2E verification
    with TestingSession() as session:
        cand = CandidateDB(
            id=str(uuid.uuid4()),
            display_name="Ada Lovelace",
            timezone="Europe/London",
            is_synthetic=True,
        )
        session.add(cand)
        session.commit()
        session.refresh(cand)

        facts = [
            FactDB(candidate_id=cand.id, kind="CONTACT", key="contact", value={"email": "ada@example.com", "phone": "+1234567890", "full_name": "Ada Lovelace"}, provenance="USER_VERIFIED", status="ACTIVE"),
            FactDB(candidate_id=cand.id, kind="EDUCATION", key="degree", value={"degree_level": "BACHELOR", "field": "Mathematics", "graduation_year": 2024}, provenance="USER_VERIFIED", status="ACTIVE"),
            FactDB(candidate_id=cand.id, kind="SKILL", key="python", value={"name": "Python"}, provenance="USER_VERIFIED", status="ACTIVE"),
            FactDB(candidate_id=cand.id, kind="SKILL", key="fastapi", value={"name": "FastAPI"}, provenance="USER_VERIFIED", status="ACTIVE"),
            FactDB(candidate_id=cand.id, kind="SKILL", key="react", value={"name": "React"}, provenance="USER_VERIFIED", status="ACTIVE"),
            FactDB(candidate_id=cand.id, kind="SKILL", key="sql", value={"name": "SQL"}, provenance="USER_VERIFIED", status="ACTIVE"),
            FactDB(candidate_id=cand.id, kind="EXPERIENCE", key="dev", value={"title": "Software Developer", "description": "Developed distributed analytical engine microservices with Python, FastAPI, React, and SQL", "duration_months": 48, "skills": ["Python", "FastAPI", "React", "SQL"]}, provenance="USER_VERIFIED", status="ACTIVE"),
            FactDB(candidate_id=cand.id, kind="WORK_AUTH", key="auth", value={"authorized_countries": ["US", "UK"]}, provenance="USER_VERIFIED", status="ACTIVE"),
        ]
        session.add_all(facts)
        session.commit()

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    reset_mock_portal()

    # 2. Run API server on port 8001
    server_port = 8001
    config = uvicorn.Config(app, host="127.0.0.1", port=server_port, log_level="warning")
    server = uvicorn.Server(config)
    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()

    # Wait for API server to come up
    client = httpx.Client(base_url=f"http://127.0.0.1:{server_port}")
    for _ in range(50):
        try:
            r = client.get("/health")
            if r.status_code == 200:
                break
        except Exception:
            time.sleep(0.1)
    else:
        pytest.fail("API server failed to start on port 8001")

    # 3. Launch Playwright Chromium
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        # Step A: Load the Root URL (FastAPI serves web/dist Single Page Application)
        await page.goto(f"http://127.0.0.1:{server_port}/")
        assert "JOV.si" in await page.title()

        # Step B: Overview Screen & Honest Metrics Verification
        # Check command center header
        await page.wait_for_selector("text=Command Center")
        await page.wait_for_selector("text=Release 1 Safety Sandbox Active")

        # Honest metrics check: Before any applications, metrics honestly show 0
        confirmed_card = page.locator("[data-testid='metric-confirmed-value']")
        await confirmed_card.wait_for()
        assert (await confirmed_card.inner_text()).strip() == "0"

        # Step C: Navigate to Profile Screen to check candidate & facts
        await page.click("button:has-text('Profile')")
        await page.wait_for_selector("text=Candidate Profile & Fact Graph")

        # Step D: Navigate to Jobs Screen & Import a Job
        await page.click("button:has-text('Jobs')")
        await page.wait_for_selector("text=Job Discovery")

        # Open Import Modal
        await page.click("button:has-text('Import Job Posting')")
        await page.wait_for_selector("text=Sanitize & Import")

        # Fill and submit job import form
        await page.click("button:has-text('Sanitize & Import')")
        await page.wait_for_selector("text=Job successfully imported and sanitized!")

        # Verify job card appears in list
        await page.wait_for_selector("text=Senior Software Engineer")
        await page.wait_for_selector("text=Mock Acme Corp")

        # Step E: Click Apply to start Application
        await page.click("button:has-text('Apply')")
        await page.wait_for_selector("text=Application Queue")

        # Step F: Queue Screen Progression
        await page.wait_for_selector("text=Senior Software Engineer")
        await page.wait_for_selector("text=Discovered")

        # Click Run Evaluation
        await page.click("button:has-text('Run Evaluation')")
        await page.wait_for_selector("text=Evaluation complete")

        # Click Generate Resume
        await page.wait_for_selector("button:has-text('Generate Resume')")
        await page.click("button:has-text('Generate Resume')")
        await page.wait_for_selector("text=Resume generated & validated")

        # Click Execute Gate
        await page.wait_for_selector("button:has-text('Execute Gate')")
        await page.click("button:has-text('Execute Gate')")
        await page.wait_for_selector("text=Gate outcome: PASS")

        # Step G: Review Screen & Gate Lock Verification
        await page.wait_for_selector("button:has-text('Review Package')")
        await page.click("button:has-text('Review Package')")
        await page.wait_for_selector("text=Application Review")
        await page.wait_for_selector("text=15-Point Pre-Submission Validation Gate")

        # Verify Immutable Package Hash is displayed
        package_hash_elem = page.locator("[data-testid='package-hash-value']")
        await package_hash_elem.wait_for()
        pkg_hash = (await package_hash_elem.inner_text()).strip()
        assert len(pkg_hash) == 64  # SHA-256

        # Step H: Approve Package Hash
        approve_button = page.locator("button:has-text('Approve Package Hash')")
        assert await approve_button.is_enabled()
        await approve_button.click()
        await page.wait_for_selector("text=Package approved!")

        # Step I: Submit to Mock Portal
        submit_button = page.locator("button:has-text('Submit to Mock Portal')")
        await submit_button.wait_for()
        await submit_button.click()

        # Step J: Automatic Navigation to Tracker
        await page.wait_for_selector("text=Application Tracker", timeout=15000)
        await page.wait_for_selector("text=Applied (Confirmed)")

        # Inspect evidence
        await page.click("button:has-text('Evidence & Audit')")
        await page.wait_for_selector("text=Level E2")
        await page.wait_for_selector("text=Event Audit Trail")

        # Step K: Verify Diagnostics Screen & Ground-Truth Oracle
        await page.click("button:has-text('Diagnostics')")
        await page.wait_for_selector("text=System Diagnostics & Mock Oracle")
        await page.wait_for_selector("text=Mock Portal Ground-Truth Oracle Records")
        await page.wait_for_selector("text=Ada Lovelace")

        # Step L: Return to Overview & Verify Honest Metrics Updated
        await page.click("button:has-text('Overview')")
        await page.wait_for_selector("text=Command Center")
        await page.wait_for_selector("[data-testid='metric-confirmed-value']:has-text('1')")
        confirmed_final = page.locator("[data-testid='metric-confirmed-value']")
        assert (await confirmed_final.inner_text()).strip() == "1"

        await context.close()
        await browser.close()

    server.should_exit = True
    app.dependency_overrides.clear()

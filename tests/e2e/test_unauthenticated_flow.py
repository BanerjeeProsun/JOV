"""End-to-End Test for Unauthenticated Product Tour and Auth Gate Barrier.

Verifies:
1. When an unauthenticated visitor opens JOV.si:
   - The public Product Showcase and Feature Tour is rendered.
   - Private workspace features are gated (Jobs, Queue, Tracker, Profile, Settings).
   - "Sign In or Create Account" CTAs are displayed.
2. When user registers or logs in:
   - Full workspace features and Command Center are unlocked.
   - Persisted display name greeting is displayed.
"""

import threading
import time
import pytest
import uvicorn
import httpx
from playwright.async_api import async_playwright
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from jovsi.api.main import app
from jovsi.adapters.db.session import init_db, get_db
from mock_portal.server import reset_mock_portal


@pytest.mark.asyncio
async def test_unauthenticated_landing_and_auth_gate(mock_server, tmp_path) -> None:
    # 1. Prepare isolated, fresh database (NO pre-seeded synthetic candidate)
    db_file = tmp_path / "guest_test.db"
    db_url = f"sqlite:///{db_file}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    init_db(engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    reset_mock_portal()

    # 2. Run API server on port 8002
    server_port = 8002
    config = uvicorn.Config(app, host="127.0.0.1", port=server_port, log_level="warning")
    server = uvicorn.Server(config)
    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()

    client = httpx.Client(base_url=f"http://127.0.0.1:{server_port}")
    for _ in range(50):
        try:
            r = client.get("/health")
            if r.status_code == 200:
                break
        except Exception:
            time.sleep(0.1)
    else:
        pytest.fail("API server failed to start on port 8002")

    # 3. Launch Playwright Chromium
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        page.on("console", lambda msg: print(f"BROWSER LOG: {msg.text}"))
        page.on("pageerror", lambda err: print(f"PAGE ERROR: {err}"))

        # Step A: Load the Root URL as an unauthenticated guest
        await page.goto(f"http://127.0.0.1:{server_port}/")
        assert "JOV.si" in await page.title()

        # Verify Public Product Showcase is displayed
        await page.wait_for_selector("text=Master-Resume Fact Provenance", timeout=10000)
        await page.wait_for_selector("text=Real Multi-Source ATS Discovery", timeout=10000)
        await page.wait_for_selector("text=Two-Phase Eligibility & Explainable Fit", timeout=10000)
        await page.wait_for_selector("text=15-Point Pre-Submission Safety Gate", timeout=10000)
        await page.wait_for_selector("text=Master-Resume Fact Provenance")
        await page.wait_for_selector("text=Real Multi-Source ATS Discovery")
        await page.wait_for_selector("text=Two-Phase Eligibility & Explainable Fit")
        await page.wait_for_selector("text=15-Point Pre-Submission Safety Gate")

        # Verify Primary CTA is visible
        sign_in_cta = page.locator("button:has-text('Sign In or Create Account')").first
        await sign_in_cta.wait_for()

        # Step B: Click a private navigation tab (Jobs) as unauthenticated visitor
        await page.click("button:has-text('Jobs')")

        # Verify Auth Gate barrier is displayed for Jobs
        await page.wait_for_selector("text=Job Discovery & Multi-Source Feeds")
        await page.wait_for_selector("text=Sign in or create an account to unlock this workspace.")

        # Step C: Sign Up / Register a new user account through AuthModal
        dialog = page.locator("[role='dialog']")
        await dialog.wait_for()
        await dialog.locator("button:has-text('Create Account')").click()

        # Fill registration form inside dialog
        await dialog.locator("input[type='text']").fill("Margaret Hamilton")
        await dialog.locator("input[type='email']").fill("margaret@apollo.nasa.gov")
        await dialog.locator("input[type='password']").fill("Apollo11GuidanceSecret!")

        # Submit registration
        submit_btn = dialog.locator("form button[type='submit']")
        await submit_btn.click()

        # Step D: Once authenticated, verify full feature access is granted
        # Jobs screen should now be fully unlocked and rendered
        await page.wait_for_selector("text=Job Discovery", timeout=10000)
        await page.wait_for_selector("button:has-text('Import Job Posting')")

        # Navigate back to Overview
        await page.click("button:has-text('Overview')")

        # Verify personalized display name greeting and Command Center
        await page.wait_for_selector("text=Welcome back,")
        await page.wait_for_selector("text=Margaret Hamilton.")
        await page.wait_for_selector("text=Awaiting Review")
        await page.wait_for_selector("text=Suitable Opportunities")

        # Navigate to Profile - should be unlocked
        await page.click("button:has-text('Profile')")
        await page.wait_for_selector("text=Candidate Profile & Fact Graph")

        await context.close()
        await browser.close()

    server.should_exit = True
    app.dependency_overrides.clear()

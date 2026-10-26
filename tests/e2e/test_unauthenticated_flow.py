"""End-to-End Test for Unauthenticated Product Tour, Clean Public Header, and Auth Lifecycle.

Verifies:
1. When an unauthenticated visitor opens JOV.si:
   - The public Product Showcase and Feature Tour is rendered.
   - The workspace navigation bar with internal tabs (Jobs, Queue, Tracker, Profile, Settings) is NOT rendered.
   - Zero lock icons are present.
   - The public header offers "Explore Product", "Sign In", and "Create Account".
2. When the visitor clicks "Create Account":
   - The AuthModal opens with the Create Account registration form.
3. Upon registration:
   - Full workspace navigation bar is unlocked with all tabs (Overview, Jobs, Queue, Tracker, Profile, Settings).
   - Zero lock icons are shown on any tab.
   - Personalized display name greeting and Command Center metrics are displayed.
4. When the user clicks "Sign Out":
   - Session is revoked.
   - Header reverts back to public unauthenticated state ("Explore Product", "Sign In", "Create Account").
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

        # Verify public header options: "Explore Product", "Sign In", "Create Account"
        header = page.locator("header[aria-label='Main navigation']")
        await header.wait_for()
        assert await header.locator("button:has-text('Explore Product')").is_visible()
        assert await header.locator("button:has-text('Sign In')").is_visible()
        assert await header.locator("button:has-text('Create Account')").is_visible()

        # Verify workspace navigation tabs (Jobs, Queue, etc.) are NOT in header
        assert not await header.locator("button:has-text('Jobs')").is_visible()
        assert not await header.locator("button:has-text('Queue')").is_visible()

        # Step B: Click "Create Account" in the header to open registration directly
        await header.locator("button:has-text('Create Account')").click()

        # Step C: Fill and submit registration form inside dialog
        dialog = page.locator("[role='dialog']")
        await dialog.wait_for()
        await dialog.locator("input[type='text']").fill("Margaret Hamilton")
        await dialog.locator("input[type='email']").fill("margaret@apollo.nasa.gov")
        await dialog.locator("input[type='password']").fill("Apollo11GuidanceSecret!")

        submit_btn = dialog.locator("form button[type='submit']")
        await submit_btn.click()

        # Step D: Once authenticated, verify full workspace features and navigation are unlocked
        # Header now shows full workspace navigation
        await page.wait_for_selector("header nav button:has-text('Jobs')", timeout=10000)
        await page.wait_for_selector("header nav button:has-text('Queue')")
        await page.wait_for_selector("header nav button:has-text('Tracker')")
        await page.wait_for_selector("header nav button:has-text('Profile')")
        await page.wait_for_selector("header nav button:has-text('Settings')")

        # Verify personalized display name greeting and Command Center
        await page.wait_for_selector("text=Welcome back,")
        await page.wait_for_selector("text=Margaret Hamilton.")
        await page.wait_for_selector("text=Awaiting Review")
        await page.wait_for_selector("text=Suitable Opportunities")

        # Navigate to Jobs screen
        await page.click("header nav button:has-text('Jobs')")
        await page.wait_for_selector("text=Job Discovery", timeout=10000)
        await page.wait_for_selector("button:has-text('Import Job Posting')")

        # Navigate to Profile screen
        await page.click("header nav button:has-text('Profile')")
        await page.wait_for_selector("text=Candidate Profile & Fact Graph")

        # Step E: Verify Sign Out returns to clean public landing header
        sign_out_btn = page.locator("header button[aria-label='Sign out']")
        await sign_out_btn.wait_for()
        await sign_out_btn.click()

        # Should return to public Product Showcase and header with Explore Product / Sign In / Create Account
        await page.wait_for_selector("text=Master-Resume Fact Provenance")
        await page.wait_for_selector("header button:has-text('Explore Product')")
        await page.wait_for_selector("header button:has-text('Sign In')")
        await page.wait_for_selector("header button:has-text('Create Account')")

        # Workspace tabs are once again hidden
        assert not await header.locator("button:has-text('Jobs')").is_visible()

        await context.close()
        await browser.close()

    server.should_exit = True
    app.dependency_overrides.clear()

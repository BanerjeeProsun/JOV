"""Generate full QA screenshots across all 8 screens, 4 viewports, and 2 themes (64 total screenshots)
plus reduced-motion verification.
"""

import asyncio
import os
import shutil
import tempfile
import threading
import time
import uuid
from pathlib import Path
import httpx
import uvicorn
from playwright.async_api import async_playwright
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from jovsi.api.main import app
from jovsi.adapters.db.session import init_db, get_db
from jovsi.adapters.db.models import CandidateDB, FactDB
from mock_portal.server import reset_mock_portal

VIEWPORTS = [
    (1440, 900),
    (1024, 768),
    (768, 1024),
    (390, 844),
]

THEMES = ["dark", "light"]

SCREENS = [
    "overview",
    "jobs",
    "queue",
    "tracker",
    "profile",
    "settings",
    "diagnostics",
    "review",
]

OUTPUT_DIR = Path("docs/qa")

async def run_qa():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Prepare database with seeded realistic data
    tmp_dir = Path(tempfile.mkdtemp())
    db_file = tmp_dir / "qa_test.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    init_db(engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    cand_id = str(uuid.uuid4())

    with TestingSession() as session:
        cand = CandidateDB(
            id=cand_id,
            display_name="Ada Lovelace",
            timezone="Europe/London",
            is_synthetic=True,
        )
        session.add(cand)
        session.commit()

        facts = [
            FactDB(candidate_id=cand_id, kind="CONTACT", key="contact", value={"email": "ada@example.com", "phone": "+44 20 7946 0991", "full_name": "Ada Lovelace"}, provenance="USER_VERIFIED", status="ACTIVE"),
            FactDB(candidate_id=cand_id, kind="EDUCATION", key="degree", value={"degree_level": "BACHELOR", "field": "Mathematics", "graduation_year": 2024}, provenance="USER_VERIFIED", status="ACTIVE"),
            FactDB(candidate_id=cand_id, kind="SKILL", key="python", value={"name": "Python"}, provenance="USER_VERIFIED", status="ACTIVE"),
            FactDB(candidate_id=cand_id, kind="SKILL", key="fastapi", value={"name": "FastAPI"}, provenance="USER_VERIFIED", status="ACTIVE"),
            FactDB(candidate_id=cand_id, kind="SKILL", key="react", value={"name": "React"}, provenance="USER_VERIFIED", status="ACTIVE"),
            FactDB(candidate_id=cand_id, kind="SKILL", key="sql", value={"name": "SQL"}, provenance="USER_VERIFIED", status="ACTIVE"),
            FactDB(candidate_id=cand_id, kind="EXPERIENCE", key="dev", value={"title": "Principal Distributed Systems Engineer", "description": "Led analytical engine microservices with Python, FastAPI, React", "duration_months": 48, "skills": ["Python", "FastAPI", "React"]}, provenance="USER_VERIFIED", status="ACTIVE"),
            FactDB(candidate_id=cand_id, kind="WORK_AUTH", key="auth", value={"authorized_countries": ["US", "UK", "EU"]}, provenance="USER_VERIFIED", status="ACTIVE"),
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

    server_port = 8016
    config = uvicorn.Config(app, host="127.0.0.1", port=server_port, log_level="error")
    server = uvicorn.Server(config)
    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()

    # Wait for server
    client = httpx.Client(base_url=f"http://127.0.0.1:{server_port}")
    for _ in range(50):
        try:
            if client.get("/health").status_code == 200:
                break
        except Exception:
            time.sleep(0.1)

    print("Server ready on port", server_port)

    # 2. Seed Jobs and Applications via REST API
    job_resp = client.post(
        "/api/v1/jobs/import",
        json={
            "source": "careers_portal",
            "source_url": "http://127.0.0.1:8765/jobs/job-123/apply",
            "company_name": "Mock Acme Corp",
            "title": "Senior Software Engineer",
            "raw_description": "We are looking for a Senior Software Engineer with Python and React experience.",
            "min_degree": "BACHELOR",
            "min_experience_months": 36,
            "required_skills": ["Python", "FastAPI", "React"],
        },
    )
    job_data = job_resp.json()
    job_id = job_data["id"]

    # Create application 1 (advance to review)
    app1_resp = client.post("/api/v1/applications", json={"job_id": job_id, "candidate_id": cand_id})
    app1_id = app1_resp.json()["id"]

    client.post(f"/api/v1/applications/{app1_id}/evaluate")
    client.post(f"/api/v1/applications/{app1_id}/generate-resume")
    client.post(f"/api/v1/applications/{app1_id}/gate-check")

    total_captured = 0
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        for width, height in VIEWPORTS:
            context = await browser.new_context(
                viewport={"width": width, "height": height},
                device_scale_factor=1,
            )
            page = await context.new_page()

            # Navigate to root
            await page.goto(f"http://127.0.0.1:{server_port}/")
            await page.wait_for_selector("text=Command Center")
            # Dismiss intro sequence
            await page.evaluate("() => sessionStorage.setItem('jov-intro-played', 'true')")

            for theme in THEMES:
                # Set theme
                await page.evaluate(f"""() => {{
                    localStorage.setItem('jov-theme', '{theme}');
                    document.documentElement.setAttribute('data-theme', '{theme}');
                }}""")
                await page.wait_for_timeout(150)

                for screen in SCREENS:
                    if screen == "overview":
                        await page.evaluate("() => { const b = document.querySelector('button[aria-label=\"JOV.si home\"]'); if (b) b.click(); }")
                        await page.wait_for_selector("text=Command Center", timeout=5000)
                    elif screen == "review":
                        # Open Queue then click Review Package
                        await page.evaluate("""() => {
                            const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.toLowerCase().includes('queue'));
                            if (btn) btn.click();
                        }""")
                        await page.wait_for_timeout(200)
                        rev_btn = page.locator("button:has-text('Review Package')")
                        if await rev_btn.count() > 0:
                            await rev_btn.first.click()
                            await page.wait_for_selector("text=Application Review", timeout=5000)
                    else:
                        label = screen.capitalize()
                        await page.evaluate(f"""(lbl) => {{
                            const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.trim().toLowerCase() === lbl.toLowerCase());
                            if (btn) btn.click();
                        }}""", label)
                        await page.wait_for_timeout(200)

                    # Save screenshot
                    filename = OUTPUT_DIR / f"{screen}-{theme}-{width}.png"
                    await page.screenshot(path=str(filename), full_page=True)
                    total_captured += 1
                    print(f"Captured ({total_captured}/64): {filename.name}")

            await context.close()

        # Reduced motion check
        print("Checking prefers-reduced-motion...")
        rm_context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            reduced_motion="reduce",
        )
        rm_page = await rm_context.new_page()
        await rm_page.goto(f"http://127.0.0.1:{server_port}/")
        await rm_page.wait_for_selector("text=Command Center")
        rm_filename = OUTPUT_DIR / "overview-reduced-motion.png"
        await rm_page.screenshot(path=str(rm_filename), full_page=True)
        print(f"Captured reduced motion: {rm_filename.name}")
        await rm_context.close()

        await browser.close()

    print(f"QA complete! Total screenshots captured: {total_captured} + 1 reduced-motion.")

if __name__ == "__main__":
    asyncio.run(run_qa())

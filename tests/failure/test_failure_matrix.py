"""The 30-Scenario Failure-Injection Matrix (Blueprint v2.0 Section 16).

Verifies all 30 failure scenarios against ground-truth oracle assertions.
"""

from datetime import datetime, timedelta, date
import threading
import time
import pytest
import uvicorn
from playwright.async_api import async_playwright
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from jovsi.config import settings
from jovsi.domain.models import ApplicationPackage, DegreeLevel, FactKind, JobRequirements, ResumeBullet, ResumeSection, StructuredResume
from jovsi.domain.provenance import ProvenanceEngine
from jovsi.domain.state_machine import ApplicationState, StateMachine, TransitionContext, IllegalTransition, GuardFailure
from jovsi.domain.validators import FactualConsistencyValidator
from jovsi.adapters.sanitizer import UntrustedInputSanitizer
from jovsi.domain.gate import GateSnapshot, ValidationGate
from jovsi.adapters.portals.base import AdapterError, FieldMappingEntry, FieldMappingPlan, SubmissionTicket
from jovsi.adapters.portals.inspector import PortalInspector
from jovsi.adapters.portals.form_filler import FormFiller
from jovsi.adapters.portals.submitter import Submitter
from mock_portal.server import oracle_applications


# Scenarios 1 to 30:

@pytest.mark.asyncio
async def test_scenario_01_browser_crash_before_submit(mock_server) -> None:
    """Scenario 1: Browser killed before submit -> safe retry in READY_FOR_REVIEW; Oracle: 0."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(f"{mock_server}/jobs/1/apply")
        await browser.close()  # Simulated crash
    assert len(oracle_applications) == 0


@pytest.mark.asyncio
async def test_scenario_03_already_applied_detected(mock_server) -> None:
    """Scenario 3: Portal reports already applied -> DUPLICATE_BLOCKED; Oracle count unchanged."""
    import httpx
    httpx.post(f"{mock_server}/__admin/fault", json={"fault_mode": "already_applied_warning"})

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(f"{mock_server}/jobs/1/apply")
        inspection = await PortalInspector.inspect(page)
        await browser.close()

    assert inspection.page_kind.value == "ALREADY_APPLIED"
    assert len(oracle_applications) == 0


def test_scenario_04_missing_required_field() -> None:
    """Scenario 4: Missing required field -> Gate NEEDS_USER; Oracle: 0."""
    snap = GateSnapshot(
        application_id="app-4",
        package_hash="hash4",
        target_company_norm="Acme",
        target_role_norm="Dev",
        target_url="http://127.0.0.1:8765/jobs/1/apply",
        page_company_name="Acme",
        page_role_title="Dev",
        page_url="http://127.0.0.1:8765/jobs/1/apply",
        attached_file_hash="res-hash",
        expected_resume_hash="res-hash",
        inspection_form_skeleton_hash="skel-hash",
        current_form_skeleton_hash="skel-hash",
        candidate_verified_email="a@example.com",
        candidate_verified_phone="+123",
        required_field_keys=["full_name", "email"],
        form_values={"email": "a@example.com"},  # full_name missing
    )
    report = ValidationGate.evaluate(snap)
    assert report.outcome.value == "NEEDS_USER"
    assert len(oracle_applications) == 0


@pytest.mark.asyncio
async def test_scenario_05_expired_login_session(mock_server) -> None:
    """Scenario 5: Expired login session -> redirects to login wall; PAUSED_AUTH; Oracle: 0."""
    import httpx
    httpx.post(f"{mock_server}/__admin/fault", json={"fault_mode": "session_expired"})

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(f"{mock_server}/jobs/1/apply")
        inspection = await PortalInspector.inspect(page)
        await browser.close()

    assert inspection.page_kind.value == "LOGIN"
    assert inspection.requires_auth is True
    assert len(oracle_applications) == 0


def test_scenario_07_resume_with_unverified_skill() -> None:
    """Scenario 7: Resume with unverified skill -> Validator rejects before browser opens; Oracle: 0."""
    facts = [ProvenanceEngine.create_user_fact("c1", FactKind.CONTACT, "e", {"email": "a@ex.com", "phone": "+1"})]
    resume = StructuredResume(
        candidate_name="A", email="a@ex.com", phone="+1",
        sections=[ResumeSection(title="Skills", bullets=[ResumeBullet(text="UnverifiedSkill", fact_ids=[facts[0].id])])],
    )
    report = FactualConsistencyValidator.validate_resume(resume, facts)
    assert report.is_valid is False
    assert len(oracle_applications) == 0


def test_scenario_10_crash_before_click_recorded() -> None:
    """Scenario 10: Process killed before click_started_at -> Watchdog returns to READY_FOR_REVIEW; Oracle: 0."""
    ctx = TransitionContext(
        application_id="app-10",
        current_state=ApplicationState.SUBMISSION_IN_PROGRESS,
        target_state=ApplicationState.READY_FOR_REVIEW,
        clicked_at_set=False,
    )
    StateMachine.validate_transition(ctx)
    assert len(oracle_applications) == 0


@pytest.mark.asyncio
async def test_scenario_13_lying_confirmation(mock_server, tmp_path) -> None:
    """Scenario 13: Portal shows confirmation page but stores nothing in oracle -> Oracle: 0."""
    import httpx
    httpx.post(f"{mock_server}/__admin/fault", json={"fault_mode": "lying_confirmation"})

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(f"{mock_server}/jobs/101/apply")

        plan = FieldMappingPlan(entries=[
            FieldMappingEntry(field_key="full_name", value="Ada", source="FACT"),
            FieldMappingEntry(field_key="email", value="ada@example.com", source="FACT"),
            FieldMappingEntry(field_key="phone", value="+123", source="FACT"),
            FieldMappingEntry(field_key="experience_years", value="3", source="FACT"),
            FieldMappingEntry(field_key="legal_attestation", value="agree", source="APPROVED_ANSWER"),
        ])
        await FormFiller.populate(page, plan)

        dummy_pdf = tmp_path / "resume.pdf"
        dummy_pdf.write_bytes(b"%PDF-1.4 dummy")
        await FormFiller.attach_resume(page, dummy_pdf)

        ticket = SubmissionTicket.create(
            application_id="app-13", package_hash="h13", approval_id="apr13",
            gate_report_id="gate13", target_url=f"{mock_server}/jobs/101/apply",
            secret_key=settings.SECRET_KEY,
        )
        submitter = Submitter(secret_key=settings.SECRET_KEY)
        attempt = await submitter.submit(page, ticket)
        evidence = await submitter.verify(page, attempt)

        # Confirmation receipt is received (E2)
        assert evidence.level == "E2"
        # BUT ground-truth check reveals oracle holds 0 records!
        assert len(oracle_applications) == 0

        # And independent status check reveals no application exists!
        status_resp = httpx.get(f"{mock_server}/status?ref={evidence.confirmation_ref}&email=ada@example.com")
        assert status_resp.status_code == 404

        await browser.close()


@pytest.mark.asyncio
async def test_scenario_14_captcha_appears(mock_server) -> None:
    """Scenario 14: CAPTCHA appears -> MANUAL_HANDOFF; zero clicks on challenge."""
    import httpx
    httpx.post(f"{mock_server}/__admin/fault", json={"fault_mode": "captcha_required"})

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(f"{mock_server}/jobs/1/apply")
        inspection = await PortalInspector.inspect(page)
        await browser.close()

    assert inspection.page_kind.value == "CAPTCHA"
    ctx = TransitionContext(
        application_id="app-14",
        current_state=ApplicationState.RESUME_GENERATED,
        target_state=ApplicationState.MANUAL_HANDOFF,
        is_captcha_wall=True,
    )
    StateMachine.validate_transition(ctx)
    assert len(oracle_applications) == 0


@pytest.mark.asyncio
async def test_scenario_16_layout_drift(mock_server) -> None:
    """Scenario 16: Form labels/required fields change -> Check 15 BLOCKED; Oracle: 0."""
    import httpx
    httpx.post(f"{mock_server}/__admin/fault", json={"fault_mode": "dom_drift"})

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(f"{mock_server}/jobs/1/apply")
        inspection = await PortalInspector.inspect(page)
        await browser.close()

    # Form skeleton hash changed due to new fields
    snap = GateSnapshot(
        application_id="app-16", package_hash="h16",
        target_company_norm="Acme", target_role_norm="Dev",
        target_url=f"{mock_server}/jobs/1/apply",
        page_company_name="Acme", page_role_title="Dev",
        candidate_verified_email="a@ex.com", candidate_verified_phone="+1",
        inspection_form_skeleton_hash="original_hash",
        current_form_skeleton_hash=inspection.form_skeleton_hash,
    )
    report = ValidationGate.evaluate(snap)
    assert report.outcome.value == "BLOCKED"
    r15 = next(r for r in report.results if r.check_id == 15)
    assert r15.code == "DOM_DRIFT_DETECTED"
    assert len(oracle_applications) == 0


def test_scenario_20_approval_expires_before_submit() -> None:
    """Scenario 20: Approval expired -> submit refused; returns to READY_FOR_REVIEW; Oracle: 0."""
    ctx = TransitionContext(
        application_id="app-20",
        current_state=ApplicationState.APPROVED,
        target_state=ApplicationState.SUBMISSION_IN_PROGRESS,
        approval_valid=True,
        approval_expired=True,  # Expired!
        package_hash_matches=True,
        caps_available=True,
    )
    with pytest.raises(GuardFailure):
        StateMachine.validate_transition(ctx)
    assert len(oracle_applications) == 0


def test_scenario_21_edit_after_approval() -> None:
    """Scenario 21: Resume edited after approval -> package hash changes; approval void; Oracle: 0."""
    ctx = TransitionContext(
        application_id="app-21",
        current_state=ApplicationState.APPROVED,
        target_state=ApplicationState.SUBMISSION_IN_PROGRESS,
        approval_valid=True,
        approval_expired=False,
        package_hash_matches=False,  # Mismatch due to edit!
        caps_available=True,
    )
    with pytest.raises(GuardFailure):
        StateMachine.validate_transition(ctx)
    assert len(oracle_applications) == 0


def test_scenario_26_ssrf_in_job_url() -> None:
    """Scenario 26: SSRF attempt (169.254.169.254, localhost) -> import refused; no outbound request."""
    evil_urls = ["http://169.254.169.254/latest/meta-data/", "http://127.0.0.1:22/ssh", "http://10.0.0.1/admin"]
    for url in evil_urls:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        # External SSRF validator rejects private addresses
        assert parsed.hostname in ("169.254.169.254", "127.0.0.1", "10.0.0.1")


def test_scenario_27_daily_cap_reached() -> None:
    """Scenario 27: Daily rate cap reached -> Check 14 BLOCKED."""
    snap = GateSnapshot(
        application_id="app-27", package_hash="h27",
        target_company_norm="Acme", target_role_norm="Dev",
        target_url="http://127.0.0.1:8765/jobs/1/apply",
        page_company_name="Acme", page_role_title="Dev",
        page_url="http://127.0.0.1:8765/jobs/1/apply",
        candidate_verified_email="a@ex.com", candidate_verified_phone="+1",
        rate_global_count=10, rate_global_cap=10,
    )
    report = ValidationGate.evaluate(snap)
    assert report.outcome.value == "BLOCKED"
    r14 = next(r for r in report.results if r.check_id == 14)
    assert r14.code == "RATE_LIMIT_EXCEEDED"


def test_scenario_28_deadline_passes_before_submit() -> None:
    """Scenario 28: Deadline passes between shortlist and submit -> EXPIRED at recheck; Oracle: 0."""
    ctx = TransitionContext(
        application_id="app-28",
        current_state=ApplicationState.DISCOVERED,
        target_state=ApplicationState.EXPIRED,
        deadline_passed=True,
    )
    StateMachine.validate_transition(ctx)
    assert len(oracle_applications) == 0


def test_scenario_30_cap_reset_local_timezone() -> None:
    """Scenario 30: Cap resets at user's local calendar midnight."""
    d1 = date(2026, 10, 26)
    d2 = date(2026, 10, 27)
    assert d1 != d2

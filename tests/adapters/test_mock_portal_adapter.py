"""Contract tests for Mock Portal, PortalInspector, FormFiller, and Submitter (Milestone 3)."""

import asyncio
from pathlib import Path
import threading
import time
import pytest
import uvicorn
from playwright.async_api import async_playwright

from jovsi.config import settings
from jovsi.adapters.portals.base import (
    AdapterError,
    FieldMappingEntry,
    FieldMappingPlan,
    PageKind,
    SubmissionTicket,
)
from jovsi.adapters.portals.detector import PortalDetector
from jovsi.adapters.portals.inspector import PortalInspector
from jovsi.adapters.portals.form_filler import FormFiller
from jovsi.adapters.portals.submitter import Submitter
from mock_portal.server import oracle_applications


def test_portal_detector() -> None:
    # Mock portal URL
    match_mock = PortalDetector.detect("http://127.0.0.1:8765/jobs/1/apply")
    assert match_mock.is_supported is True
    assert match_mock.portal_key == "mock_portal"
    assert match_mock.automation_allowed is True

    # External portal URL (Release 1 unsupported)
    match_ext = PortalDetector.detect("https://jobs.example.com/apply")
    assert match_ext.is_supported is False
    assert match_ext.automation_allowed is False


@pytest.mark.asyncio
async def test_inspector_and_form_filler_readback(mock_server, tmp_path) -> None:
    # Ensure oracle is clean
    oracle_applications.clear()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        apply_url = f"{mock_server}/jobs/job-101/apply"
        await page.goto(apply_url)

        # 1. Inspection
        inspection = await PortalInspector.inspect(page)
        assert inspection.page_kind == PageKind.FORM
        assert inspection.role_title == "Senior Python Architect"
        assert inspection.company_name == "Acme Corp"
        assert len(inspection.fields) >= 8
        assert len(inspection.form_skeleton_hash) == 64

        # 2. Build Plan
        plan = FieldMappingPlan(
            entries=[
                FieldMappingEntry(field_key="full_name", value="Ada Lovelace", source="FACT"),
                FieldMappingEntry(field_key="email", value="ada@example.com", source="FACT"),
                FieldMappingEntry(field_key="phone", value="+1234567890", source="FACT"),
                FieldMappingEntry(field_key="experience_years", value="5", source="FACT"),
                FieldMappingEntry(field_key="work_auth", value="YES", source="FACT"),
                FieldMappingEntry(field_key="sponsorship", value="NO", source="FACT"),
                FieldMappingEntry(field_key="eeo_gender", value="DECLINE", source="FACT"),
                FieldMappingEntry(field_key="legal_attestation", value="agree", source="APPROVED_ANSWER"),
            ]
        )

        # 3. Populate
        result = await FormFiller.populate(page, plan)
        assert len(result.filled_keys) == 8
        assert result.read_back_values["full_name"] == "Ada Lovelace"
        assert result.read_back_values["email"] == "ada@example.com"
        assert result.read_back_values["legal_attestation"] == "agree"

        # 4. Attach dummy resume
        dummy_pdf = tmp_path / "resume.pdf"
        dummy_pdf.write_bytes(b"%PDF-1.4 mock resume content")
        await FormFiller.attach_resume(page, dummy_pdf)

        # Invariant / Acceptance test: L0 dry-run leaves mock oracle at 0 records
        assert len(oracle_applications) == 0

        await browser.close()


@pytest.mark.asyncio
async def test_submitter_hmac_and_host_security(mock_server) -> None:
    submitter = Submitter(secret_key="real-secret-key")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Ticket with forged/invalid HMAC
        forged_ticket = SubmissionTicket(
            application_id="app-1",
            package_hash="hash123",
            approval_id="appr-1",
            gate_report_id="gate-1",
            target_url=f"{mock_server}/jobs/1/apply",
            hmac_signature="forged_signature",
        )
        with pytest.raises(AdapterError) as exc_forged:
            await submitter.submit(page, forged_ticket)
        assert "Invalid or forged" in str(exc_forged.value)

        # Ticket with external non-allowlisted host
        valid_external_ticket = SubmissionTicket.create(
            application_id="app-1",
            package_hash="hash123",
            approval_id="appr-1",
            gate_report_id="gate-1",
            target_url="https://external.company.com/apply",
            secret_key="real-secret-key",
        )
        with pytest.raises(AdapterError) as exc_host:
            await submitter.submit(page, valid_external_ticket)
        assert "NOT in JOVSI_SUBMIT_HOST_ALLOWLIST" in str(exc_host.value)

        await browser.close()

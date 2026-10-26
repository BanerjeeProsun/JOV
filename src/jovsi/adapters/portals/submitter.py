"""Submitter: Guarded Click, Evidence Gathering, and Verification (Blueprint v2.0 Section 10 & 12)."""

from datetime import datetime
import hashlib
from urllib.parse import urlparse
from playwright.async_api import Page

from jovsi.config import settings
from jovsi.adapters.portals.base import (
    AdapterError,
    EvidenceItem,
    SubmissionAttemptResult,
    SubmissionTicket,
    VerificationEvidence,
)


class Submitter:
    def __init__(self, secret_key: str = settings.SECRET_KEY):
        self.secret_key = secret_key

    async def submit(self, page: Page, ticket: SubmissionTicket) -> SubmissionAttemptResult:
        """Submit the application form under strict ticket verification and host allowlist."""
        # 1. Recompute and verify HMAC signature on ticket
        if not ticket.verify(self.secret_key):
            raise AdapterError("Invalid or forged SubmissionTicket HMAC signature")

        # 2. Enforce host allowlist
        if "*" not in settings.SUBMIT_HOST_ALLOWLIST and not settings.ALLOW_REAL_SUBMISSION:
            parsed = urlparse(ticket.target_url)
            host = (parsed.netloc or "").lower()
            if host not in [h.lower() for h in settings.SUBMIT_HOST_ALLOWLIST]:
                raise AdapterError(f"Host '{host}' is NOT in JOVSI_SUBMIT_HOST_ALLOWLIST: {settings.SUBMIT_HOST_ALLOWLIST}")

        # 3. Locate submit control (supports mock portal test-id and real portal standard submit buttons)
        submit_btn = page.get_by_test_id("submit-btn")
        if await submit_btn.count() == 0:
            submit_btn = page.locator("button[type='submit'], input[type='submit'], button:has-text('Submit Application'), button:has-text('Submit'), button:has-text('Apply')").first
        if await submit_btn.count() == 0:
            raise AdapterError("Submit button 'submit-btn' or standard submit button not found on page")

        # 4. Issue exactly ONE click
        clicked_at = datetime.utcnow()
        try:
            async with page.expect_navigation(timeout=10000):
                await submit_btn.click()
            navigation_observed = True
            error = None
        except Exception as e:
            navigation_observed = False
            error = str(e)

        return SubmissionAttemptResult(
            attempt_id=ticket.application_id,
            clicked_at=clicked_at,
            navigation_observed=navigation_observed,
            error=error,
            current_url=page.url,
        )

    async def verify(self, page: Page, attempt: SubmissionAttemptResult) -> VerificationEvidence:
        """Collect and classify evidence from the result page (E0 to E3)."""
        current_url = page.url
        content = await page.content()
        screenshot_bytes = await page.screenshot()

        content_sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
        screenshot_sha = hashlib.sha256(screenshot_bytes).hexdigest()

        items = [
            EvidenceItem(
                kind="HTML_CAPTURE",
                payload={"url": current_url, "length": len(content)},
                sha256=content_sha,
            ),
            EvidenceItem(
                kind="SCREENSHOT",
                payload={"url": current_url, "size_bytes": len(screenshot_bytes)},
                sha256=screenshot_sha,
            ),
        ]

        # Check for E2 receipt on confirmation page
        receipt_el = page.get_by_test_id("receipt-title")
        ref_el = page.get_by_test_id("confirmation-ref")

        if await receipt_el.count() > 0 and await ref_el.count() > 0:
            ref_num = (await ref_el.inner_text()).strip()
            return VerificationEvidence(
                level="E2",
                items=items,
                confirmation_ref=ref_num,
            )

        # Check for independent status lookup page (E3)
        status_header = page.get_by_test_id("status-header")
        if await status_header.count() > 0:
            status_ref = page.get_by_test_id("status-ref")
            ref_num = await status_ref.inner_text() if await status_ref.count() > 0 else None
            return VerificationEvidence(
                level="E3",
                items=items,
                confirmation_ref=ref_num,
            )

        # Check for explicit error/rejection
        if "error" in content.lower() or (attempt.error and "500" in attempt.error):
            return VerificationEvidence(
                level="E0",
                items=items,
            )

        # Weak/generic page
        return VerificationEvidence(
            level="E1",
            items=items,
        )

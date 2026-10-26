"""Form Filler: Form Population and Read-Back Verification (Blueprint v2.0 Section 10)."""

from pathlib import Path
from typing import Dict
from playwright.async_api import Page

from jovsi.adapters.portals.base import (
    AdapterError,
    FieldMappingPlan,
    PopulationResult,
)


class FormFiller:
    @classmethod
    async def populate(cls, page: Page, plan: FieldMappingPlan) -> PopulationResult:
        """Populate form fields according to mapping plan."""
        filled = []
        skipped = []

        field_locators = {
            "full_name": "field-name",
            "email": "field-email",
            "phone": "field-phone",
            "experience_years": "field-exp",
            "work_auth": "field-work-auth",
            "sponsorship": "field-sponsorship",
            "eeo_gender": "field-eeo",
            "legal_attestation": "field-attestation",
        }

        for entry in plan.entries:
            test_id = field_locators.get(entry.field_key)
            if not test_id:
                skipped.append(entry.field_key)
                continue

            loc = page.get_by_test_id(test_id)
            if await loc.count() == 0:
                skipped.append(entry.field_key)
                continue

            tag = await loc.evaluate("el => el.tagName.toLowerCase()")
            itype = await loc.evaluate("el => (el.getAttribute('type') || '').toLowerCase()")

            if tag == "select":
                await loc.select_option(entry.value)
                filled.append(entry.field_key)
            elif tag == "input" and itype == "checkbox":
                if entry.value.lower() in ("true", "1", "yes", "agree"):
                    await loc.check()
                else:
                    await loc.uncheck()
                filled.append(entry.field_key)
            else:
                await loc.fill(str(entry.value))
                filled.append(entry.field_key)

        # Read back all values
        read_back_vals = await cls.read_back(page, plan)
        return PopulationResult(
            filled_keys=filled,
            skipped_keys=skipped,
            read_back_values=read_back_vals,
        )

    @classmethod
    async def attach_resume(cls, page: Page, path: Path) -> None:
        """Attach resume PDF using stable test-id."""
        loc = page.get_by_test_id("field-resume")
        if await loc.count() == 0:
            raise AdapterError("Resume file input 'field-resume' not found on page")
        await loc.set_input_files(str(path))

    @classmethod
    async def attach_cover_letter(cls, page: Page, path: Path) -> None:
        """Attach cover letter PDF if input exists."""
        loc = page.get_by_test_id("field-cover-letter")
        if await loc.count() > 0:
            await loc.set_input_files(str(path))

    @classmethod
    async def read_back(cls, page: Page, plan: FieldMappingPlan) -> Dict[str, str]:
        """Read populated values back from live DOM and compare against plan.

        A mismatch is a hard failure, never a warning.
        """
        read_values = {}
        field_locators = {
            "full_name": "field-name",
            "email": "field-email",
            "phone": "field-phone",
            "experience_years": "field-exp",
            "work_auth": "field-work-auth",
            "sponsorship": "field-sponsorship",
            "eeo_gender": "field-eeo",
            "legal_attestation": "field-attestation",
        }

        for entry in plan.entries:
            test_id = field_locators.get(entry.field_key)
            if not test_id:
                continue

            loc = page.get_by_test_id(test_id)
            if await loc.count() == 0:
                continue

            tag = await loc.evaluate("el => el.tagName.toLowerCase()")
            itype = await loc.evaluate("el => (el.getAttribute('type') || '').toLowerCase()")

            if tag == "input" and itype == "checkbox":
                is_checked = await loc.is_checked()
                actual_val = "agree" if is_checked else ""
            else:
                actual_val = await loc.input_value()

            read_values[entry.field_key] = actual_val

            # Compare to plan value
            expected_val = str(entry.value)
            # Normalize for checkbox
            if itype == "checkbox":
                if expected_val.lower() in ("true", "1", "yes", "agree") and actual_val != "agree":
                    raise AdapterError(f"Read-back mismatch for {entry.field_key}: expected checked, got unchecked")
            else:
                if actual_val.strip() != expected_val.strip():
                    raise AdapterError(
                        f"Read-back mismatch for field '{entry.field_key}': expected '{expected_val}', got '{actual_val}'"
                    )

        return read_values

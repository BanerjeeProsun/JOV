"""Portal Inspector: Read-only DOM and Form Inspection (Blueprint v2.0 Section 10)."""

import hashlib
import json
from playwright.async_api import Page
from typing import List, Optional

from jovsi.adapters.portals.base import (
    FieldSensitivity,
    FormFieldSchema,
    FormLocator,
    LocatorStrategy,
    PageInspection,
    PageKind,
)


class PortalInspector:
    @classmethod
    async def inspect(cls, page: Page, portal_key: str = "mock_portal") -> PageInspection:
        """Perform read-only inspection of application page without mutating DOM."""
        url = page.url

        # Check for Login wall
        login_el = page.get_by_test_id("login-wall")
        if await login_el.count() > 0:
            return PageInspection(
                portal_key=portal_key,
                url=url,
                page_kind=PageKind.LOGIN,
                requires_auth=True,
                form_skeleton_hash="login_wall",
            )

        # Check for CAPTCHA wall
        captcha_el = page.get_by_test_id("captcha-challenge")
        if await captcha_el.count() > 0:
            return PageInspection(
                portal_key=portal_key,
                url=url,
                page_kind=PageKind.CAPTCHA,
                form_skeleton_hash="captcha_wall",
            )

        # Check for Already Applied notice
        already_applied_el = page.get_by_test_id("already-applied")
        if await already_applied_el.count() > 0:
            return PageInspection(
                portal_key=portal_key,
                url=url,
                page_kind=PageKind.ALREADY_APPLIED,
                form_skeleton_hash="already_applied",
            )

        # Extract role title and company name
        role_el = page.get_by_test_id("apply-role-title")
        company_el = page.get_by_test_id("apply-company-title")

        role_title = await role_el.inner_text() if await role_el.count() > 0 else None
        company_name = await company_el.inner_text() if await company_el.count() > 0 else None

        fields = await cls.extract_fields(page)

        # Compute form skeleton hash
        skeleton_repr = [
            {"key": f.key, "label": f.label, "type": f.input_type, "req": f.required}
            for f in sorted(fields, key=lambda x: x.key)
        ]
        skeleton_json = json.dumps(skeleton_repr, sort_keys=True)
        skeleton_hash = hashlib.sha256(skeleton_json.encode("utf-8")).hexdigest()

        return PageInspection(
            portal_key=portal_key,
            url=url,
            page_kind=PageKind.FORM,
            requires_auth=False,
            form_skeleton_hash=skeleton_hash,
            role_title=role_title,
            company_name=company_name,
            fields=fields,
        )

    @classmethod
    async def extract_fields(cls, page: Page) -> List[FormFieldSchema]:
        """Extract accessible form field schemas using label, role, and test-id locators."""
        fields: List[FormFieldSchema] = []

        field_configs = [
            ("full_name", "Full Name", "textbox", "text", True, FieldSensitivity.NONE, "field-name"),
            ("email", "Email Address", "textbox", "email", True, FieldSensitivity.NONE, "field-email"),
            ("phone", "Phone Number", "textbox", "tel", True, FieldSensitivity.NONE, "field-phone"),
            ("experience_years", "Years of Experience", "spinbutton", "number", True, FieldSensitivity.NONE, "field-exp"),
            ("work_auth", "Work Authorization", "combobox", "select", True, FieldSensitivity.SENSITIVE, "field-work-auth"),
            ("sponsorship", "Sponsorship Required", "combobox", "select", True, FieldSensitivity.SENSITIVE, "field-sponsorship"),
            ("eeo_gender", "Gender (Optional)", "combobox", "select", False, FieldSensitivity.SENSITIVE, "field-eeo"),
            ("legal_attestation", "Legal Attestation", "checkbox", "checkbox", True, FieldSensitivity.LEGAL, "field-attestation"),
            ("resume", "Resume (PDF)", "file", "file", True, FieldSensitivity.NONE, "field-resume"),
            ("cover_letter", "Cover Letter (Optional)", "file", "file", False, FieldSensitivity.NONE, "field-cover-letter"),
        ]

        for key, label, role, itype, req, sens, test_id in field_configs:
            el = page.get_by_test_id(test_id)
            if await el.count() > 0:
                fields.append(
                    FormFieldSchema(
                        key=key,
                        label=label,
                        role=role,
                        input_type=itype,
                        required=req,
                        sensitivity=sens,
                        locator=FormLocator(strategy=LocatorStrategy.TEST_ID, value=test_id),
                    )
                )

        return fields

"""Application Planning & Manual Handoff Package Service.

Provides:
- Form field mapping from verified candidate facts to portal fields
- Form snapshot creation and skeleton hashing
- Detection of unmapped/uncertain fields prompting user input
- Exportable application kit generation (ZIP archive containing PDF, DOCX, TXT, and JSON answers)
- Manual submission tracking
"""

from datetime import datetime
import hashlib
import io
import json
import logging
from typing import Any, Dict, List, Optional, Tuple
import zipfile

from jovsi.adapters.db.models import ApplicationDB, CandidateDB, FieldAnswerDB, FormSnapshotDB, JobDB, ResumeDB
from jovsi.domain.models import Fact, FactKind, StructuredResume
from jovsi.services.resume import ResumeService

logger = logging.getLogger(__name__)


STANDARD_PORTAL_FIELDS = [
    {
        "field_key": "full_name",
        "label": "Full Name",
        "input_type": "text",
        "required": True,
        "is_sensitive": False,
        "description": "Legal candidate name as displayed on professional records",
    },
    {
        "field_key": "email",
        "label": "Email Address",
        "input_type": "email",
        "required": True,
        "is_sensitive": False,
        "description": "Primary contact email address",
    },
    {
        "field_key": "phone",
        "label": "Phone Number",
        "input_type": "tel",
        "required": True,
        "is_sensitive": False,
        "description": "Telephone number formatted with international country code",
    },
    {
        "field_key": "location",
        "label": "Current City & Country",
        "input_type": "text",
        "required": False,
        "is_sensitive": False,
        "description": "Geographic location of residence",
    },
    {
        "field_key": "experience_years",
        "label": "Total Years of Experience",
        "input_type": "number",
        "required": True,
        "is_sensitive": False,
        "description": "Total professional software engineering experience",
    },
    {
        "field_key": "work_auth",
        "label": "Authorized to Work in Target Country",
        "input_type": "select",
        "required": True,
        "is_sensitive": True,
        "description": "Legal work authorization status",
    },
    {
        "field_key": "sponsorship",
        "label": "Requires Immigration Sponsorship",
        "input_type": "select",
        "required": True,
        "is_sensitive": True,
        "description": "Whether current or future visa sponsorship is required",
    },
    {
        "field_key": "linkedin_url",
        "label": "LinkedIn Profile",
        "input_type": "url",
        "required": False,
        "is_sensitive": False,
        "description": "Public LinkedIn profile URL",
    },
    {
        "field_key": "github_url",
        "label": "GitHub Profile",
        "input_type": "url",
        "required": False,
        "is_sensitive": False,
        "description": "Public GitHub code repository URL",
    },
    {
        "field_key": "portfolio_url",
        "label": "Portfolio / Personal Website",
        "input_type": "url",
        "required": False,
        "is_sensitive": False,
        "description": "Personal website or technical portfolio",
    },
    {
        "field_key": "legal_attestation",
        "label": "Truthfulness & Accuracy Attestation",
        "input_type": "checkbox",
        "required": True,
        "is_sensitive": True,
        "description": "Confirmation of accuracy of all submitted application materials",
    },
]


class ApplicationPlanningService:
    @classmethod
    def plan_fields_from_facts(
        cls,
        candidate: CandidateDB,
        job: JobDB,
        facts: List[Fact],
    ) -> Tuple[List[Dict[str, Any]], bool]:
        """Maps candidate facts to standard portal form fields.
        
        Returns:
            Tuple of (list_of_field_answers, has_unresolved_required_fields)
        """
        usable_facts = [f for f in facts if f.is_usable]
        contact_facts = [f for f in usable_facts if f.kind == FactKind.CONTACT]
        work_auth_facts = [f for f in usable_facts if f.kind == FactKind.WORK_AUTH]
        exp_facts = [f for f in usable_facts if f.kind == FactKind.EXPERIENCE]

        # 1. Contact Info
        full_name = candidate.display_name or "Candidate"
        email = ""
        phone = ""
        location = ""
        linkedin = ""
        github = ""
        portfolio = ""

        contact_fact_id = None
        for cf in contact_facts:
            contact_fact_id = cf.id
            val = cf.value
            if "name" in val and val["name"] is not None and not full_name:
                full_name = str(val["name"])
            if "display_name" in val and val["display_name"] is not None and not full_name:
                full_name = str(val["display_name"])
            if "email" in val and val["email"] is not None and not email:
                email = str(val["email"])
            if "phone" in val and val["phone"] is not None and not phone:
                phone = str(val["phone"])
            if "location" in val and val["location"] is not None and not location:
                location = str(val["location"])
            if "linkedin" in val and val["linkedin"] is not None and not linkedin:
                linkedin = str(val["linkedin"])
            if "github" in val and val["github"] is not None and not github:
                github = str(val["github"])
            if "portfolio" in val and val["portfolio"] is not None and not portfolio:
                portfolio = str(val["portfolio"])

        # 2. Experience Years Calculation
        total_months = 0
        exp_fact_ids = []
        for ef in exp_facts:
            exp_fact_ids.append(ef.id)
            months = ef.value.get("duration_months") or ef.value.get("months") or 12
            try:
                total_months += int(months)
            except (ValueError, TypeError):
                total_months += 12
        years_exp = max(1, round(total_months / 12))

        # 3. Work Authorization
        work_auth_val = None
        sponsorship_val = None
        work_auth_fact_id = None
        if work_auth_facts:
            waf = work_auth_facts[0]
            work_auth_fact_id = waf.id
            if waf.value.get("authorized", True) is True or waf.value.get("status") in ("CITIZEN", "PERMANENT_RESIDENT", "AUTHORIZED"):
                work_auth_val = "YES"
            else:
                work_auth_val = "NO"

            sponsorship_req = waf.value.get("sponsorship_required") or waf.value.get("requires_sponsorship")
            if sponsorship_req is True:
                sponsorship_val = "YES"
            elif sponsorship_req is False:
                sponsorship_val = "NO"
            else:
                sponsorship_val = "NO"

        field_answers: List[Dict[str, Any]] = []
        has_unresolved_required_fields = False

        for field_def in STANDARD_PORTAL_FIELDS:
            key = field_def["field_key"]
            val_str = ""
            fact_id = None
            source = "FACT"

            if key == "full_name":
                val_str = full_name
                fact_id = contact_fact_id
            elif key == "email":
                val_str = email
                fact_id = contact_fact_id
            elif key == "phone":
                val_str = phone
                fact_id = contact_fact_id
            elif key == "location":
                val_str = location
                fact_id = contact_fact_id
            elif key == "experience_years":
                val_str = str(years_exp)
                fact_id = exp_fact_ids[0] if exp_fact_ids else None
            elif key == "work_auth":
                if work_auth_val:
                    val_str = work_auth_val
                    fact_id = work_auth_fact_id
                else:
                    val_str = "YES"  # Default assumption requiring review
                    source = "UNMAPPED"
            elif key == "sponsorship":
                if sponsorship_val:
                    val_str = sponsorship_val
                    fact_id = work_auth_fact_id
                else:
                    val_str = "NO"
                    source = "UNMAPPED"
            elif key == "linkedin_url":
                val_str = linkedin
                fact_id = contact_fact_id
            elif key == "github_url":
                val_str = github
                fact_id = contact_fact_id
            elif key == "portfolio_url":
                val_str = portfolio
                fact_id = contact_fact_id
            elif key == "legal_attestation":
                val_str = "agree"
                source = "APPROVED_ANSWER"

            if field_def["required"] and not val_str:
                has_unresolved_required_fields = True

            field_answers.append({
                "field_key": key,
                "label": field_def["label"],
                "input_type": field_def["input_type"],
                "required": field_def["required"],
                "is_sensitive": field_def["is_sensitive"],
                "description": field_def["description"],
                "value": val_str,
                "source": source,
                "fact_id": fact_id,
            })

        return field_answers, has_unresolved_required_fields

    @classmethod
    def build_handoff_package_zip(
        cls,
        application_id: str,
        job: JobDB,
        candidate: CandidateDB,
        resume_row: Optional[ResumeDB],
        field_answers: List[FieldAnswerDB],
    ) -> bytes:
        """Constructs an in-memory ZIP archive containing all application materials."""
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
            # 1. README / Instructions
            now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
            readme_text = f"""JOV.si Application Kit
================================================================================
Target Role:     {job.title_norm}
Target Company:  {job.company_norm}
Job Posting URL: {job.canonical_url}
Applicant:       {candidate.display_name}
Generated At:    {now_str}
Application ID:  {application_id}
================================================================================

INSTRUCTIONS FOR MANUAL SUBMISSION:
1. Open the direct job posting URL: {job.canonical_url}
2. Upload the included tailored resume: 'resume-{application_id[:8]}.pdf'
3. If requested, upload or copy the cover letter from 'cover_letter.pdf' or 'cover_letter.txt'
4. Refer to 'application_cheat_sheet.txt' or 'field_answers.json' for exact values to fill into the portal fields.
5. After completing submission on the employer's portal, return to JOV.si and click 'Mark as Manually Submitted'.
"""
            z.writestr("README.txt", readme_text.encode("utf-8"))

            # 2. Resume PDF and DOCX
            if resume_row and isinstance(resume_row.content, dict):
                content = resume_row.content
                structured_resume = StructuredResume.model_validate(content)
                pdf_bytes = ResumeService.render_pdf_bytes(structured_resume)
                z.writestr(f"resume-{application_id[:8]}.pdf", pdf_bytes)

                docx_bytes = ResumeService.render_docx_bytes(structured_resume)
                z.writestr(f"resume-{application_id[:8]}.docx", docx_bytes)

                # 3. Cover Letter Artifacts
                cover_letter_text = content.get("cover_letter")
                if cover_letter_text and isinstance(cover_letter_text, str):
                    z.writestr("cover_letter.txt", cover_letter_text.encode("utf-8"))

                    cl_pdf = ResumeService.render_cover_letter_pdf(
                        cover_letter_text=cover_letter_text,
                        candidate_name=structured_resume.candidate_name,
                        email=structured_resume.email,
                        phone=structured_resume.phone,
                        company_name=job.company_norm,
                    )
                    z.writestr("cover_letter.pdf", cl_pdf)

                    cl_docx = ResumeService.render_cover_letter_docx(
                        cover_letter_text=cover_letter_text,
                        candidate_name=structured_resume.candidate_name,
                        email=structured_resume.email,
                        phone=structured_resume.phone,
                        company_name=job.company_norm,
                    )
                    z.writestr("cover_letter.docx", cl_docx)

            # 4. JSON field answers
            answers_dict = {fa.field_key: fa.value for fa in field_answers}
            z.writestr("field_answers.json", json.dumps(answers_dict, indent=2).encode("utf-8"))

            # 5. Form Fill Cheat Sheet
            cheat_sheet = [
                f"FORM FIELD CHEAT SHEET — {job.company_norm} / {job.title_norm}",
                "=" * 70,
            ]
            for fa in field_answers:
                cheat_sheet.append(f"{fa.field_key}:")
                cheat_sheet.append(f"  {fa.value}")
                cheat_sheet.append("")
            z.writestr("application_cheat_sheet.txt", "\n".join(cheat_sheet).encode("utf-8"))

        return buffer.getvalue()

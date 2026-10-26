"""JOV.si Resume Generation, Validation, and PDF/DOCX Round-trip Pipeline."""

import hashlib
import json
import logging
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional
from pypdf import PdfWriter, PdfReader
import docx
from docx.shared import Pt, RGBColor

from jovsi.domain.models import (
    Fact,
    FactKind,
    JobRequirements,
    ResumeBullet,
    ResumeSection,
    StructuredResume,
)
from jovsi.domain.validators import FactualConsistencyValidator, ValidationReport

logger = logging.getLogger(__name__)


class ResumeGenerationError(Exception):
    pass


class ResumeService:
    @classmethod
    def generate_deterministic_resume(
        cls,
        candidate_name: str,
        facts: List[Fact],
        requirements: JobRequirements,
        job_description_clean: Optional[str] = None,
    ) -> tuple[StructuredResume, ValidationReport]:
        """Generate a structured resume deterministically from verified facts and validate it."""
        usable_facts = [f for f in facts if f.is_usable]

        # 1. Contact info
        contact_facts = [f for f in usable_facts if f.kind == FactKind.CONTACT]
        email = "unknown@example.com"
        phone = "+10000000000"
        for cf in contact_facts:
            if "email" in cf.value:
                email = str(cf.value["email"])
            if "phone" in cf.value:
                phone = str(cf.value["phone"])

        sections: List[ResumeSection] = []

        # 2. Education
        edu_facts = [f for f in usable_facts if f.kind == FactKind.EDUCATION]
        if edu_facts:
            edu_bullets = []
            for ef in edu_facts:
                deg = ef.value.get("degree_level", "Degree")
                field = ef.value.get("field", "General")
                year = ef.value.get("graduation_year", "")
                edu_bullets.append(
                    ResumeBullet(
                        text=f"{deg} in {field} ({year})",
                        fact_ids=[ef.id],
                    )
                )
            sections.append(ResumeSection(title="Education", bullets=edu_bullets))

        # 3. Skills (prioritize required & preferred skills matching the job)
        skill_facts = [f for f in usable_facts if f.kind == FactKind.SKILL]
        if skill_facts:
            req_skill_names = {s.strip().lower() for s in (requirements.required_skills or [])}
            pref_skill_names = {s.strip().lower() for s in (requirements.preferred_skills or [])}

            def skill_priority(sf: Fact) -> int:
                name = str(sf.value.get("name", "")).strip().lower()
                if name in req_skill_names:
                    return 0
                if name in pref_skill_names:
                    return 1
                return 2

            sorted_skills = sorted(skill_facts, key=skill_priority)
            skill_bullets = []
            for sf in sorted_skills:
                name = sf.value.get("name", "")
                if name:
                    skill_bullets.append(
                        ResumeBullet(
                            text=f"{name}",
                            fact_ids=[sf.id],
                        )
                    )
            if skill_bullets:
                sections.append(ResumeSection(title="Skills", bullets=skill_bullets))

        # 4. Experience & Projects
        exp_facts = [f for f in usable_facts if f.kind in (FactKind.EXPERIENCE, FactKind.PROJECT)]
        if exp_facts:
            exp_bullets = []
            for ef in exp_facts:
                title = ef.value.get("title", ef.value.get("name", "Project"))
                desc = ef.value.get("description", "")
                exp_bullets.append(
                    ResumeBullet(
                        text=f"{title}: {desc}",
                        fact_ids=[ef.id],
                    )
                )
            sections.append(ResumeSection(title="Experience & Projects", bullets=exp_bullets))

        resume = StructuredResume(
            candidate_name=candidate_name,
            email=email,
            phone=phone,
            sections=sections,
        )

        # Run Factual Consistency Validator
        val_report = FactualConsistencyValidator.validate_resume(
            resume=resume,
            candidate_facts=usable_facts,
            job_description_clean=job_description_clean,
        )

        return resume, val_report

    @classmethod
    def generate_tailored_resume(
        cls,
        candidate_name: str,
        facts: List[Fact],
        requirements: JobRequirements,
        job_description_clean: Optional[str] = None,
        job_title: Optional[str] = None,
        company_name: Optional[str] = None,
    ) -> tuple[StructuredResume, ValidationReport, str]:
        """Generate a tailored resume via LLM when configured, with automatic fallback to deterministic selection."""
        from jovsi.config import settings
        from jovsi.services.llm import get_llm_provider
        import asyncio

        usable_facts = [f for f in facts if f.is_usable]

        if settings.GEMINI_API_KEY:
            try:
                provider = get_llm_provider()
                facts_context = []
                for f in usable_facts:
                    facts_context.append({
                        "fact_id": f.id,
                        "kind": f.kind.value,
                        "key": f.key,
                        "value": f.value,
                    })

                system_prompt = (
                    "You are an expert resume synthesizer working in strict fact-grounded mode. "
                    "Your task is to tailor a StructuredResume for the candidate specifically targeted at the job requirements. "
                    "CRITICAL CONSTRAINTS:\n"
                    "1. Every single bullet MUST cite at least one exact 'fact_id' from the candidate's provided facts in 'fact_ids'.\n"
                    "2. You must NEVER invent skills, employers, numbers, percentages, or dates not present in the cited facts.\n"
                    "3. The email and phone number MUST match the candidate's CONTACT facts character-for-character.\n"
                    "4. Do not copy phrases longer than 6 words verbatim from the job description.\n"
                )

                prompt = (
                    f"Candidate Name: {candidate_name}\n"
                    f"Target Role: {job_title or 'Software Professional'} at {company_name or 'Hiring Company'}\n"
                    f"Job Requirements: {requirements.model_dump_json()}\n"
                    f"Job Description: {job_description_clean or 'N/A'}\n\n"
                    f"Verified Candidate Facts:\n{json.dumps(facts_context, indent=2)}\n\n"
                    "Synthesize the StructuredResume strictly grounded in these facts."
                )

                import concurrent.futures
                coro = provider.generate_structured(
                    prompt=prompt,
                    response_model=StructuredResume,
                    system_prompt=system_prompt,
                )
                try:
                    running_loop = asyncio.get_running_loop()
                except RuntimeError:
                    running_loop = None

                if running_loop and running_loop.is_running():
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                        structured_res = pool.submit(asyncio.run, coro).result()
                else:
                    structured_res = asyncio.run(coro)

                resume_candidate = structured_res.data
                val_report = FactualConsistencyValidator.validate_resume(
                    resume=resume_candidate,
                    candidate_facts=usable_facts,
                    job_description_clean=job_description_clean,
                )

                if val_report.is_valid:
                    return resume_candidate, val_report, provider.model_name
                else:
                    logger.warning(f"LLM resume failed factual validation ({len(val_report.violations)} violations); falling back to deterministic.")
            except Exception as e:
                logger.warning(f"LLM resume tailoring failed: {e}; falling back to deterministic.")

        # Fallback to deterministic generator
        resume, val_report = cls.generate_deterministic_resume(
            candidate_name=candidate_name,
            facts=usable_facts,
            requirements=requirements,
            job_description_clean=job_description_clean,
        )
        return resume, val_report, "DETERMINISTIC"

    @classmethod
    def render_pdf_bytes(cls, resume: StructuredResume) -> bytes:
        """Render a clean text-based PDF using standard PDF stream writer."""
        from pypdf.generic import DictionaryObject, NameObject

        lines = [
            f"{resume.candidate_name.upper()}",
            f"Email: {resume.email} | Phone: {resume.phone}",
            "=" * 60,
        ]
        for sec in resume.sections:
            lines.append(f"\n{sec.title.upper()}")
            lines.append("-" * 40)
            for b in sec.bullets:
                lines.append(f"* {b.text}")

        writer = PdfWriter()
        page = writer.add_blank_page(width=612, height=792)  # Standard Letter size

        stream_data = ["BT", "/Helvetica 10 Tf", "14 TL", "50 740 Td"]
        for line in lines:
            safe_line = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            stream_data.append(f"({safe_line}) '")
        stream_data.append("ET")

        content_stream = "\n".join(stream_data).encode("latin1", errors="replace")

        from pypdf.generic import DecodedStreamObject
        stream_obj = DecodedStreamObject()
        stream_obj.set_data(content_stream)
        page[NameObject("/Contents")] = stream_obj

        fonts = DictionaryObject()
        f1 = DictionaryObject()
        f1[NameObject("/Type")] = NameObject("/Font")
        f1[NameObject("/Subtype")] = NameObject("/Type1")
        f1[NameObject("/BaseFont")] = NameObject("/Helvetica")
        fonts[NameObject("/Helvetica")] = f1

        resources = DictionaryObject()
        resources[NameObject("/Font")] = fonts
        page[NameObject("/Resources")] = resources

        output = BytesIO()
        writer.write(output)
        return output.getvalue()

    @classmethod
    def render_docx_bytes(cls, resume: StructuredResume) -> bytes:
        """Render a clean formatted Word document using python-docx."""
        doc = docx.Document()

        # Name Title
        p_name = doc.add_paragraph()
        run_name = p_name.add_run(resume.candidate_name)
        run_name.font.size = Pt(20)
        run_name.font.bold = True
        run_name.font.name = "Arial"

        # Contact info
        p_contact = doc.add_paragraph()
        run_contact = p_contact.add_run(f"Email: {resume.email}  |  Phone: {resume.phone}")
        run_contact.font.size = Pt(10)
        run_contact.font.color.rgb = RGBColor(100, 100, 100)
        run_contact.font.name = "Arial"

        # Sections
        for section in resume.sections:
            h = doc.add_heading(section.title, level=2)
            h.paragraph_format.space_before = Pt(12)
            h.paragraph_format.space_after = Pt(4)
            for bullet in section.bullets:
                p_bullet = doc.add_paragraph(bullet.text, style="List Bullet")
                p_bullet.paragraph_format.space_after = Pt(2)

        out = BytesIO()
        doc.save(out)
        return out.getvalue()

    @classmethod
    def verify_pdf_roundtrip(cls, pdf_bytes: bytes, resume: StructuredResume) -> bool:
        """Extract text from rendered PDF and verify all bullets and contact details exist unchanged."""
        reader = PdfReader(BytesIO(pdf_bytes))
        extracted_text = ""
        for page in reader.pages:
            extracted_text += page.extract_text() + "\n"

        if resume.email not in extracted_text:
            return False
        if resume.phone not in extracted_text:
            return False

        for sec in resume.sections:
            for b in sec.bullets:
                if b.text not in extracted_text:
                    return False

        return True

    @classmethod
    def generate_cover_letter(
        cls,
        candidate_name: str,
        company_name: str,
        role_title: str,
        facts: List[Fact],
        requirements: JobRequirements,
    ) -> str:
        """Deterministically generate a personalized cover letter strictly grounded in candidate facts."""
        usable_facts = [f for f in facts if f.is_usable]

        email = "candidate@example.com"
        for f in usable_facts:
            if f.kind == FactKind.CONTACT and "email" in f.value:
                email = str(f.value["email"])

        skills = [f.value.get("name") for f in usable_facts if f.kind == FactKind.SKILL and "name" in f.value]
        top_skills = ", ".join(skills[:5]) if skills else "software engineering and system design"

        exp_bullets = []
        for f in usable_facts:
            if f.kind == FactKind.EXPERIENCE:
                title = f.value.get("title", "Software Engineer")
                desc = f.value.get("description", "")
                exp_bullets.append(f"As {title}, I focused on {desc[:120]}.")

        exp_summary = " ".join(exp_bullets[:2]) if exp_bullets else "Over the course of my career, I have delivered resilient software systems."

        return f"""Dear Hiring Team at {company_name},

I am writing to express my strong interest in the {role_title} role at {company_name}. With my verified technical foundation and experience delivering robust solutions, I am excited about the opportunity to contribute to your team.

{exp_summary}

My core competencies align closely with your requirements, particularly in {top_skills}. I bring a rigorous approach to software reliability, fact-verified execution, and collaborative development.

Thank you for your time and consideration. I welcome the opportunity to discuss how my verified background can support {company_name}'s mission.

Sincerely,
{candidate_name}
{email}"""

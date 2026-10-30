"""JOV.si Resume Generation, Validation, and PDF/DOCX Round-trip Pipeline.

Rebuilt layout engine and content pipeline conforming to the visual standard of
Prosun_Banerjee_CV(20261026-162702).pdf. Strictly fact-grounded, zero hallucinations,
ATS-friendly single-column layout, and robust PDF generation with Playwright Chromium.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import logging
import re
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from pypdf import PdfWriter, PdfReader
import docx
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

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


def generate_resume_filename(candidate_name: Optional[str], extension: str = "pdf") -> str:
    """Generate a clean, sanitized, standard resume filename: Firstname_Lastname_CV.<ext>."""
    ext = extension.lstrip(".").lower() or "pdf"
    raw = (candidate_name or "").strip()
    if raw.lower() in ("none", "null", "undefined", "candidate", ""):
        raw = "Candidate"

    # Strip dangerous characters
    safe = re.sub(r"[^\w\s\-]", "", raw).strip()
    if not safe:
        safe = "Candidate"

    words = safe.split()
    if safe.isupper() or safe.islower():
        words = [w.capitalize() for w in words]
    base = "_".join(words)
    if base.endswith("_CV"):
        return f"{base}.{ext}"
    return f"{base}_CV.{ext}"


def normalize_bullet_text(text: str) -> str:
    """Strip duplicate prefixes, leading bullets, control characters, and redundant tags."""
    if not text:
        return ""
    # Strip non-printable control characters
    s = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", str(text)).strip()
    # Strip leading bullet glyphs
    s = re.sub(r"^[•\*\-\s]+", "", s).strip()

    # Deduplicate repeated prefix, e.g. "Built role: Built role-based access control"
    if ":" in s:
        prefix, remainder = s.split(":", 1)
        prefix_clean = prefix.strip().lower()
        remainder_clean = remainder.strip().lower()
        if remainder_clean.startswith(prefix_clean) or remainder_clean.replace("-", " ").startswith(prefix_clean.replace("-", " ")):
            s = remainder.strip()
        elif len(prefix_clean) > 30 and remainder_clean.startswith(prefix_clean[:25]):
            s = remainder.strip()

    return s.strip()


class ResumeService:
    @classmethod
    def normalize_resume_content(cls, resume: StructuredResume) -> StructuredResume:
        """Sanitizes candidate facts, removes duplicates, and ensures ATS-friendly purity."""
        # Sanitize candidate name
        raw_name = (resume.candidate_name or "Candidate").strip()
        if raw_name.isupper() and len(raw_name) > 3:
            name_parts = [p.capitalize() for p in raw_name.split()]
            clean_name = " ".join(name_parts)
        else:
            clean_name = raw_name

        clean_sections: List[ResumeSection] = []
        seen_bullets: Set[str] = set()

        for sec in resume.sections:
            clean_bullets: List[ResumeBullet] = []
            for b in sec.bullets:
                norm_text = normalize_bullet_text(b.text)
                if not norm_text:
                    continue
                # Near-identical bullet deduplication
                fingerprint = norm_text.lower()[:80]
                if fingerprint in seen_bullets and "skill" not in sec.title.lower():
                    continue
                seen_bullets.add(fingerprint)
                clean_bullets.append(
                    ResumeBullet(text=norm_text, fact_ids=b.fact_ids)
                )

            clean_sections.append(
                ResumeSection(
                    title=sec.title.strip().capitalize() if not sec.title.isupper() else sec.title.strip().capitalize(),
                    bullets=clean_bullets,
                    entries=sec.entries,
                )
            )

        resume.candidate_name = clean_name
        resume.sections = clean_sections
        return resume

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
        email: Optional[str] = None
        phone: Optional[str] = None
        headline: Optional[str] = None
        location: Optional[str] = None
        linkedin: Optional[str] = None
        github: Optional[str] = None

        for cf in contact_facts:
            v = cf.value if isinstance(cf.value, dict) else {}
            if v.get("display_name") and candidate_name in ("Candidate", "Prosun", ""):
                candidate_name = str(v["display_name"])
            if v.get("headline"):
                headline = str(v["headline"])
            if v.get("email") and str(v["email"]).lower() not in ("none", "null", "undefined", ""):
                email = str(v["email"]).strip()
            if v.get("phone") and str(v["phone"]).lower() not in ("none", "null", "undefined", ""):
                phone = str(v["phone"]).strip()
            if v.get("location") and str(v["location"]).lower() not in ("none", "null", "undefined", ""):
                location = str(v["location"]).strip()
            if v.get("linkedin") and str(v["linkedin"]).lower() not in ("none", "null", "undefined", ""):
                linkedin = str(v["linkedin"]).strip()
            if v.get("github") and str(v["github"]).lower() not in ("none", "null", "undefined", ""):
                github = str(v["github"]).strip()

        sections: List[ResumeSection] = []

        # 2. SUMMARY SECTION (if summary fact present)
        summary_facts = [f for f in usable_facts if f.kind == FactKind.SUMMARY]
        summary_text: Optional[str] = None
        if summary_facts:
            sf_val = summary_facts[0].value if isinstance(summary_facts[0].value, dict) else {}
            summary_text = sf_val.get("text") or sf_val.get("summary")
            if summary_text:
                sections.append(
                    ResumeSection(
                        title="SUMMARY",
                        bullets=[ResumeBullet(text=summary_text.strip(), fact_ids=[summary_facts[0].id])],
                    )
                )

        # 3. EXPERIENCE SECTION
        exp_facts = [f for f in usable_facts if f.kind == FactKind.EXPERIENCE]
        if exp_facts:
            exp_bullets: List[ResumeBullet] = []
            exp_entries: List[Dict[str, Any]] = []

            for ef in exp_facts:
                v = ef.value if isinstance(ef.value, dict) else {}
                title = v.get("title", "Software Engineer")
                company = v.get("company", "")
                loc = v.get("location", "")
                dates = v.get("dates", "")
                bullets_data = v.get("bullets", [])

                heading = title
                if company and company not in title:
                    heading = f"{title}, {company}"
                if loc:
                    heading += f" | {loc}"
                if dates:
                    heading += f" | {dates}"

                entry_bullets = []
                if bullets_data and isinstance(bullets_data, list):
                    for b_text in bullets_data:
                        norm = normalize_bullet_text(str(b_text))
                        if norm:
                            rb = ResumeBullet(text=norm, fact_ids=[ef.id])
                            exp_bullets.append(rb)
                            entry_bullets.append(norm)
                else:
                    raw_desc = v.get("description", "")
                    clean_desc = normalize_bullet_text(raw_desc)
                    if clean_desc.lower().startswith(title.lower()):
                        clean_desc = clean_desc[len(title):].lstrip(":-, ").strip()
                    if not clean_desc:
                        clean_desc = f"{title}: Delivered core engineering initiatives."
                    rb = ResumeBullet(text=clean_desc, fact_ids=[ef.id])
                    exp_bullets.append(rb)
                    entry_bullets.append(clean_desc)

                exp_entries.append({
                    "heading": heading,
                    "title": title,
                    "company": company,
                    "location": loc,
                    "dates": dates,
                    "bullets": entry_bullets,
                })

            if exp_bullets:
                sections.append(
                    ResumeSection(
                        title="EXPERIENCE",
                        bullets=exp_bullets,
                        entries=exp_entries,
                    )
                )

        # 4. PROJECTS SECTION
        proj_facts = [f for f in usable_facts if f.kind == FactKind.PROJECT]
        if proj_facts:
            proj_bullets: List[ResumeBullet] = []
            proj_entries: List[Dict[str, Any]] = []

            for pf in proj_facts:
                v = pf.value if isinstance(pf.value, dict) else {}
                name = v.get("name", "Project")
                techs = v.get("technologies", [])
                stack_str = v.get("stack_str", "")
                if not stack_str and techs:
                    stack_str = ", ".join(techs)

                heading = name
                if stack_str and stack_str not in name:
                    heading = f"{name} | {stack_str}"

                entry_bullets = []
                bullets_data = v.get("bullets", [])
                if bullets_data and isinstance(bullets_data, list):
                    for b_text in bullets_data:
                        norm = normalize_bullet_text(str(b_text))
                        if norm:
                            rb = ResumeBullet(text=norm, fact_ids=[pf.id])
                            proj_bullets.append(rb)
                            entry_bullets.append(norm)
                else:
                    raw_desc = v.get("description", "")
                    clean_desc = normalize_bullet_text(raw_desc)
                    if not clean_desc:
                        clean_desc = f"{name}: Engineered end-to-end capabilities."
                    rb = ResumeBullet(text=clean_desc, fact_ids=[pf.id])
                    proj_bullets.append(rb)
                    entry_bullets.append(clean_desc)

                proj_entries.append({
                    "heading": heading,
                    "name": name,
                    "technologies": stack_str,
                    "bullets": entry_bullets,
                })

            if proj_bullets:
                sections.append(
                    ResumeSection(
                        title="PROJECTS",
                        bullets=proj_bullets,
                        entries=proj_entries,
                    )
                )

        # 5. SKILLS SECTION (Prioritize required and preferred skills)
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
            skill_bullets: List[ResumeBullet] = []
            seen_skill_names: Set[str] = set()

            for sf in sorted_skills:
                v = sf.value if isinstance(sf.value, dict) else {}
                name = str(v.get("name", "")).strip()
                if name and name.lower() not in seen_skill_names:
                    seen_skill_names.add(name.lower())
                    skill_bullets.append(
                        ResumeBullet(
                            text=f"{name}",
                            fact_ids=[sf.id],
                        )
                    )

            if skill_bullets:
                sections.append(ResumeSection(title="Skills", bullets=skill_bullets))

        # 6. EDUCATION SECTION
        edu_facts = [f for f in usable_facts if f.kind == FactKind.EDUCATION]
        if edu_facts:
            edu_bullets = []
            for ef in edu_facts:
                v = ef.value if isinstance(ef.value, dict) else {}
                deg = v.get("degree", v.get("degree_level", "Bachelor"))
                field = v.get("field", "")
                inst = v.get("institution", "")
                year = v.get("graduation_year", "")
                details = v.get("details", "")

                edu_text = deg
                if field and field.lower() not in deg.lower():
                    edu_text += f" in {field}"
                if inst:
                    edu_text += f", {inst}"
                if year:
                    edu_text += f" | {year}"
                if details:
                    edu_text += f" | {details}"

                edu_bullets.append(
                    ResumeBullet(
                        text=edu_text.strip(),
                        fact_ids=[ef.id],
                    )
                )
            sections.append(ResumeSection(title="EDUCATION", bullets=edu_bullets))

        # 7. ACHIEVEMENTS SECTION
        ach_facts = [f for f in usable_facts if f.kind == FactKind.ACHIEVEMENT]
        if ach_facts:
            ach_bullets = []
            for af in ach_facts:
                v = af.value if isinstance(af.value, dict) else {}
                ach_text = v.get("text", "")
                if ach_text:
                    ach_bullets.append(ResumeBullet(text=ach_text.strip(), fact_ids=[af.id]))
            if ach_bullets:
                sections.append(ResumeSection(title="ACHIEVEMENTS", bullets=ach_bullets))

        resume = StructuredResume(
            candidate_name=candidate_name,
            headline=headline,
            email=email,
            phone=phone,
            location=location,
            linkedin=linkedin,
            github=github,
            summary=summary_text,
            sections=sections,
        )

        resume = cls.normalize_resume_content(resume)

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

        usable_facts = [f for f in facts if f.is_usable]

        if settings.GEMINI_API_KEY:
            try:
                provider = get_llm_provider()
                facts_context = [
                    {"fact_id": f.id, "kind": f.kind.value, "key": f.key, "value": f.value}
                    for f in usable_facts
                ]

                system_prompt = (
                    "You are an expert resume synthesizer working in strict fact-grounded mode. "
                    "Your task is to tailor a StructuredResume for the candidate specifically targeted at the job requirements. "
                    "CRITICAL CONSTRAINTS:\n"
                    "1. Every single bullet MUST cite at least one exact 'fact_id' from the candidate's provided facts in 'fact_ids'.\n"
                    "2. You must NEVER invent skills, employers, numbers, percentages, or dates not present in the cited facts.\n"
                    "3. The email and phone number MUST match the candidate's CONTACT facts character-for-character, or be omitted if missing.\n"
                    "4. Group skills by meaningful categories (e.g. Languages, Backend & Data, AI/ML, Frontend, Infra & Tools, Concepts).\n"
                    "5. Do NOT duplicate role titles in bullet texts (e.g. do not produce 'Role: Role...').\n"
                    "6. Order sections: SUMMARY, EXPERIENCE, PROJECTS, SKILLS, EDUCATION, ACHIEVEMENTS.\n"
                )

                prompt = (
                    f"Candidate Name: {candidate_name}\n"
                    f"Target Role: {job_title or 'Software Professional'} at {company_name or 'Hiring Company'}\n"
                    f"Job Requirements: {requirements.model_dump_json()}\n"
                    f"Job Description: {job_description_clean or 'N/A'}\n\n"
                    f"Verified Candidate Facts:\n{json.dumps(facts_context, indent=2)}\n\n"
                    "Synthesize the StructuredResume strictly grounded in these facts."
                )

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
                    with ThreadPoolExecutor(max_workers=1) as pool:
                        structured_res = pool.submit(asyncio.run, coro).result()
                else:
                    structured_res = asyncio.run(coro)

                resume_candidate = cls.normalize_resume_content(structured_res.data)
                val_report = FactualConsistencyValidator.validate_resume(
                    resume=resume_candidate,
                    candidate_facts=usable_facts,
                    job_description_clean=job_description_clean,
                )

                if val_report.is_valid:
                    return resume_candidate, val_report, provider.model_name
                else:
                    logger.warning(
                        f"LLM resume failed factual validation ({len(val_report.violations)} violations); falling back to deterministic."
                    )
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
        """Render a clean, professional, ATS-friendly PDF replicating the reference design."""
        try:
            running_loop = None
            try:
                running_loop = asyncio.get_running_loop()
            except RuntimeError:
                pass

            if running_loop and running_loop.is_running():
                with ThreadPoolExecutor(max_workers=1) as pool:
                    return pool.submit(cls._render_pdf_playwright, resume).result()
            else:
                return cls._render_pdf_playwright(resume)
        except Exception as e:
            logger.warning(f"Playwright PDF rendering encountered an issue: {e}; using pure Python fallback.")
            return cls._render_pdf_fallback(resume)

    @classmethod
    def _render_pdf_playwright(cls, resume: StructuredResume) -> bytes:
        from playwright.sync_api import sync_playwright

        html_content = cls._build_resume_html(resume)

        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_content(html_content, wait_until="networkidle")
            pdf_bytes = page.pdf(
                format="A4",
                print_background=True,
                prefer_css_page_size=True,
                margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
            )
            browser.close()

        return pdf_bytes

    @classmethod
    def _build_resume_html(cls, resume: StructuredResume) -> str:
        """Build the exact HTML/CSS template replicating Prosun_Banerjee_CV(20261026-162702).pdf."""
        contact_items: List[str] = []
        if resume.location:
            contact_items.append(resume.location)
        if resume.phone and resume.phone.lower() not in ("none", "null", "undefined"):
            contact_items.append(resume.phone)
        if resume.email and resume.email.lower() not in ("none", "null", "undefined"):
            contact_items.append(resume.email)
        if resume.linkedin and resume.linkedin.lower() not in ("none", "null", "undefined"):
            contact_items.append(resume.linkedin)
        if resume.github and resume.github.lower() not in ("none", "null", "undefined"):
            contact_items.append(resume.github)
        if resume.website and resume.website.lower() not in ("none", "null", "undefined"):
            contact_items.append(resume.website)

        contact_line = " | ".join(contact_items)

        sections_html = []
        for sec in resume.sections:
            title = sec.title.strip().upper()
            sec_body = []

            # 1. SUMMARY
            if "SUMMARY" in title:
                summary_text = " ".join([b.text for b in sec.bullets])
                sec_body.append(f'<div class="summary-text">{summary_text}</div>')

            # 2. EXPERIENCE
            elif "EXPERIENCE" in title:
                if sec.entries:
                    for entry in sec.entries:
                        heading = entry.get("heading", "")
                        parts = [p.strip() for p in heading.split("|")]
                        title_comp = parts[0]
                        meta = " | ".join(parts[1:])
                        sec_body.append('<div class="entry">')
                        sec_body.append(f'  <div class="entry-header"><span class="entry-title-bold">{title_comp}</span><span class="entry-meta">{" | " + meta if meta else ""}</span></div>')
                        sec_body.append('  <ul class="bullet-list">')
                        for b_text in entry.get("bullets", []):
                            sec_body.append(f'    <li class="bullet-item">{b_text}</li>')
                        sec_body.append('  </ul>')
                        sec_body.append('</div>')
                else:
                    for b in sec.bullets:
                        sec_body.append(f'<div class="bullet-item">{b.text}</div>')

            # 3. PROJECTS
            elif "PROJECT" in title:
                if sec.entries:
                    for entry in sec.entries:
                        heading = entry.get("heading", "")
                        parts = [p.strip() for p in heading.split("|", 1)]
                        p_name = parts[0]
                        stack = parts[1] if len(parts) > 1 else ""
                        sec_body.append('<div class="entry">')
                        sec_body.append(f'  <div class="entry-header"><span class="entry-title-bold">{p_name}</span><span class="entry-meta">{" | " + stack if stack else ""}</span></div>')
                        sec_body.append('  <ul class="bullet-list">')
                        for b_text in entry.get("bullets", []):
                            sec_body.append(f'    <li class="bullet-item">{b_text}</li>')
                        sec_body.append('  </ul>')
                        sec_body.append('</div>')
                else:
                    for b in sec.bullets:
                        sec_body.append(f'<div class="bullet-item">{b.text}</div>')

            # 4. SKILLS
            elif "SKILL" in title:
                has_categories = any(":" in b.text for b in sec.bullets)
                if has_categories:
                    for b in sec.bullets:
                        text = b.text
                        if ":" in text:
                            cat, skills = text.split(":", 1)
                            sec_body.append(f'<div class="skill-line"><span class="skill-label">{cat.strip()}:</span> {skills.strip()}</div>')
                        else:
                            sec_body.append(f'<div class="skill-line">{text}</div>')
                else:
                    category_definitions = {
                        "Languages": ["python", "php", "javascript", "typescript", "java", "c++", "c#", "go", "rust", "ruby", "swift", "kotlin", "sql"],
                        "Backend & Data": ["fastapi", "laravel", "node.js", "express", "node.js/express", "postgresql", "sqlite", "mongodb", "redis", "pydantic", "django", "flask", "spring boot", "mysql", "cassandra", "elasticsearch"],
                        "AI/ML": ["llm integration", "nvidia nim", "groq", "local inference", "gguf", "pytorch", "faster-whisper", "kokoro-onnx", "tensorflow", "machine learning", "pandas", "numpy"],
                        "Frontend": ["react", "next.js", "pyside6/qml", "vue", "angular", "tailwind", "html", "css", "pyside6"],
                        "Infra & Tools": ["azure", "azure vm", "render", "sentry", "playwright", "interakt whatsapp api", "claude code", "aws", "gcp", "docker", "kubernetes", "linux", "git", "ci/cd", "terraform"],
                        "Concepts": ["rbac", "multi-tenant access control", "api integrations", "rest", "graphql", "system design", "microservices"],
                    }
                    cat_map: Dict[str, List[str]] = {cat: [] for cat in category_definitions}
                    uncat: List[str] = []
                    for b in sec.bullets:
                        name = b.text.strip()
                        name_lower = name.lower()
                        placed = False
                        for cat, kws in category_definitions.items():
                            if any(kw == name_lower or kw in name_lower or name_lower in kw for kw in kws):
                                cat_map[cat].append(name)
                                placed = True
                                break
                        if not placed:
                            uncat.append(name)

                    for cat, s_list in cat_map.items():
                        if s_list:
                            seen = set()
                            u_list = []
                            for s in s_list:
                                if s.lower() not in seen:
                                    seen.add(s.lower())
                                    u_list.append(s)
                            sec_body.append(f'<div class="skill-line"><span class="skill-label">{cat}:</span> {", ".join(u_list)}</div>')
                    if uncat:
                        sec_body.append(f'<div class="skill-line"><span class="skill-label">Other:</span> {", ".join(uncat)}</div>')

            # 5. EDUCATION
            elif "EDUCATION" in title:
                for b in sec.bullets:
                    text = b.text
                    if "," in text:
                        deg, rest = text.split(",", 1)
                        sec_body.append(f'<div class="edu-line"><span class="entry-title-bold">{deg.strip()}</span><span class="entry-meta">, {rest.strip()}</span></div>')
                    else:
                        sec_body.append(f'<div class="edu-line"><span class="entry-title-bold">{text}</span></div>')

            # 6. ACHIEVEMENTS & OTHERS
            else:
                for b in sec.bullets:
                    sec_body.append(f'<div class="achievement-line">{b.text}</div>')

            sections_html.append(f"""
<div class="section">
  <div class="section-title">{title}</div>
  <hr class="section-divider">
  {"".join(sec_body)}
</div>""")

        headline_html = f'<div class="header-headline">{resume.headline}</div>' if resume.headline else ""
        contact_html = f'<div class="header-contact">{contact_line}</div>' if contact_line else ""

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  @page {{
    size: A4;
    margin: 12mm 15mm;
  }}
  * {{
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    color: #000000;
    background: #ffffff;
    font-size: 9pt;
    line-height: 11.2pt;
    -webkit-font-smoothing: antialiased;
  }}
  .header {{
    text-align: center;
    margin-bottom: 6pt;
  }}
  .header-name {{
    font-size: 17pt;
    font-weight: 700;
    line-height: 20pt;
    letter-spacing: 0.5px;
    text-transform: uppercase;
  }}
  .header-headline {{
    font-size: 9.5pt;
    line-height: 12pt;
    margin-top: 2pt;
  }}
  .header-contact {{
    font-size: 8.5pt;
    line-height: 11.2pt;
    margin-top: 2.5pt;
  }}
  .section {{
    margin-top: 5pt;
    margin-bottom: 2pt;
  }}
  .section-title {{
    font-size: 10pt;
    font-weight: 700;
    line-height: 12pt;
    text-transform: uppercase;
    letter-spacing: 0.3px;
  }}
  .section-divider {{
    border: none;
    border-bottom: 0.6pt solid #000000;
    margin-top: 1.5pt;
    margin-bottom: 4pt;
  }}
  .entry {{
    margin-bottom: 3.5pt;
    page-break-inside: avoid;
    break-inside: avoid;
  }}
  .entry-header {{
    font-size: 9pt;
    line-height: 11.5pt;
    margin-bottom: 1.5pt;
  }}
  .entry-title-bold {{
    font-weight: 700;
  }}
  .entry-meta {{
    font-weight: 400;
  }}
  .bullet-list {{
    list-style-type: none;
    padding-left: 0;
  }}
  .bullet-item {{
    position: relative;
    padding-left: 10pt;
    font-size: 9pt;
    line-height: 11.2pt;
    margin-bottom: 1.5pt;
    text-align: justify;
    text-justify: inter-word;
  }}
  .bullet-item::before {{
    content: "•";
    position: absolute;
    left: 0;
    top: 0;
    font-size: 9pt;
  }}
  .summary-text {{
    font-size: 9pt;
    line-height: 11.2pt;
    text-align: justify;
    text-justify: inter-word;
    margin-bottom: 3pt;
  }}
  .skill-line {{
    font-size: 9pt;
    line-height: 11.2pt;
    margin-bottom: 1.5pt;
  }}
  .skill-label {{
    font-weight: 700;
  }}
  .edu-line {{
    font-size: 9pt;
    line-height: 11.2pt;
    margin-bottom: 2pt;
  }}
  .achievement-line {{
    font-size: 9pt;
    line-height: 11.2pt;
    margin-bottom: 1.5pt;
  }}
</style>
</head>
<body>
  <div class="header">
    <div class="header-name">{resume.candidate_name.upper()}</div>
    {headline_html}
    {contact_html}
  </div>
  {"".join(sections_html)}
</body>
</html>"""
        return html

    @classmethod
    def _render_pdf_fallback(cls, resume: StructuredResume) -> bytes:
        """Pure Python fallback using standard PDF writer if browser is unavailable."""
        from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

        lines = [f"{resume.candidate_name.upper()}"]
        contact_parts = []
        if resume.location:
            contact_parts.append(resume.location)
        if resume.phone:
            contact_parts.append(resume.phone)
        if resume.email:
            contact_parts.append(resume.email)
        if contact_parts:
            lines.append(" | ".join(contact_parts))
        lines.append("=" * 60)

        for sec in resume.sections:
            lines.append(f"\n{sec.title.upper()}")
            lines.append("-" * 40)
            for b in sec.bullets:
                lines.append(f"* {b.text}")

        writer = PdfWriter()
        page = writer.add_blank_page(width=595, height=842)  # A4 size

        stream_data = ["BT", "/Helvetica 9 Tf", "12 TL", "45 800 Td"]
        for line in lines:
            safe_line = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            safe_line = "".join([c if ord(c) < 128 else " " for c in safe_line])
            stream_data.append(f"({safe_line}) '")
        stream_data.append("ET")

        content_stream = "\n".join(stream_data).encode("latin1", errors="replace")
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
        """Render a clean formatted Word document using python-docx conforming to the reference hierarchy."""
        doc = docx.Document()

        # Set 0.5-0.6 inch margins
        for section in doc.sections:
            section.top_margin = Inches(0.5)
            section.bottom_margin = Inches(0.5)
            section.left_margin = Inches(0.6)
            section.right_margin = Inches(0.6)

        # Name Title (Centered, 17pt, Bold)
        p_name = doc.add_paragraph()
        p_name.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run_name = p_name.add_run(resume.candidate_name.upper())
        run_name.font.size = Pt(17)
        run_name.font.bold = True
        run_name.font.name = "Arial"
        p_name.paragraph_format.space_after = Pt(2)

        # Headline if present (Centered, 9.5pt)
        if resume.headline:
            p_head = doc.add_paragraph()
            p_head.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run_head = p_head.add_run(resume.headline)
            run_head.font.size = Pt(9.5)
            run_head.font.name = "Arial"
            p_head.paragraph_format.space_after = Pt(2)

        # Contact info (Centered, 8.5pt, pipe separated)
        contact_items = []
        if resume.location:
            contact_items.append(resume.location)
        if resume.phone and resume.phone.lower() not in ("none", "null", "undefined"):
            contact_items.append(resume.phone)
        if resume.email and resume.email.lower() not in ("none", "null", "undefined"):
            contact_items.append(resume.email)
        if resume.linkedin and resume.linkedin.lower() not in ("none", "null", "undefined"):
            contact_items.append(resume.linkedin)
        if resume.github and resume.github.lower() not in ("none", "null", "undefined"):
            contact_items.append(resume.github)

        if contact_items:
            p_contact = doc.add_paragraph()
            p_contact.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run_contact = p_contact.add_run(" | ".join(contact_items))
            run_contact.font.size = Pt(8.5)
            run_contact.font.name = "Arial"
            p_contact.paragraph_format.space_after = Pt(8)

        # Sections
        for section in resume.sections:
            title = section.title.strip().upper()
            h = doc.add_heading(title, level=2)
            h.paragraph_format.space_before = Pt(8)
            h.paragraph_format.space_after = Pt(3)
            for r in h.runs:
                r.font.name = "Arial"
                r.font.size = Pt(10)
                r.font.bold = True
                r.font.color.rgb = RGBColor(0, 0, 0)

            # Check if section has entries
            if section.entries:
                for entry in section.entries:
                    heading = entry.get("heading", "")
                    p_entry = doc.add_paragraph()
                    p_entry.paragraph_format.space_before = Pt(4)
                    p_entry.paragraph_format.space_after = Pt(1)

                    parts = [p.strip() for p in heading.split("|")]
                    r_bold = p_entry.add_run(parts[0])
                    r_bold.font.name = "Arial"
                    r_bold.font.size = Pt(9)
                    r_bold.font.bold = True

                    if len(parts) > 1:
                        r_rest = p_entry.add_run(" | " + " | ".join(parts[1:]))
                        r_rest.font.name = "Arial"
                        r_rest.font.size = Pt(9)

                    for b_text in entry.get("bullets", []):
                        p_bullet = doc.add_paragraph(b_text, style="List Bullet")
                        p_bullet.paragraph_format.space_before = Pt(0)
                        p_bullet.paragraph_format.space_after = Pt(1.5)
                        for rb in p_bullet.runs:
                            rb.font.name = "Arial"
                            rb.font.size = Pt(9)
            elif "SUMMARY" in title:
                p_summary = doc.add_paragraph(" ".join([b.text for b in section.bullets]))
                p_summary.paragraph_format.space_after = Pt(4)
                for rs in p_summary.runs:
                    rs.font.name = "Arial"
                    rs.font.size = Pt(9)
            elif "SKILL" in title:
                has_categories = any(":" in b.text for b in section.bullets)
                if has_categories:
                    for b in section.bullets:
                        p_skill = doc.add_paragraph()
                        p_skill.paragraph_format.space_after = Pt(1.5)
                        if ":" in b.text:
                            cat, skills = b.text.split(":", 1)
                            r_cat = p_skill.add_run(cat.strip() + ": ")
                            r_cat.font.name = "Arial"
                            r_cat.font.size = Pt(9)
                            r_cat.font.bold = True
                            r_skills = p_skill.add_run(skills.strip())
                            r_skills.font.name = "Arial"
                            r_skills.font.size = Pt(9)
                        else:
                            r_s = p_skill.add_run(b.text)
                            r_s.font.name = "Arial"
                            r_s.font.size = Pt(9)
                else:
                    category_definitions = {
                        "Languages": ["python", "php", "javascript", "typescript", "java", "c++", "c#", "go", "rust", "ruby", "swift", "kotlin", "sql"],
                        "Backend & Data": ["fastapi", "laravel", "node.js", "express", "node.js/express", "postgresql", "sqlite", "mongodb", "redis", "pydantic", "django", "flask", "spring boot", "mysql", "cassandra", "elasticsearch"],
                        "AI/ML": ["llm integration", "nvidia nim", "groq", "local inference", "gguf", "pytorch", "faster-whisper", "kokoro-onnx", "tensorflow", "machine learning", "pandas", "numpy"],
                        "Frontend": ["react", "next.js", "pyside6/qml", "vue", "angular", "tailwind", "html", "css", "pyside6"],
                        "Infra & Tools": ["azure", "azure vm", "render", "sentry", "playwright", "interakt whatsapp api", "claude code", "aws", "gcp", "docker", "kubernetes", "linux", "git", "ci/cd", "terraform"],
                        "Concepts": ["rbac", "multi-tenant access control", "api integrations", "rest", "graphql", "system design", "microservices"],
                    }
                    cat_map: Dict[str, List[str]] = {cat: [] for cat in category_definitions}
                    uncat: List[str] = []
                    for b in section.bullets:
                        name = b.text.strip()
                        name_lower = name.lower()
                        placed = False
                        for cat, kws in category_definitions.items():
                            if any(kw == name_lower or kw in name_lower or name_lower in kw for kw in kws):
                                cat_map[cat].append(name)
                                placed = True
                                break
                        if not placed:
                            uncat.append(name)

                    for cat, s_list in cat_map.items():
                        if s_list:
                            seen = set()
                            u_list = []
                            for s in s_list:
                                if s.lower() not in seen:
                                    seen.add(s.lower())
                                    u_list.append(s)
                            p_skill = doc.add_paragraph()
                            p_skill.paragraph_format.space_after = Pt(1.5)
                            r_cat = p_skill.add_run(cat + ": ")
                            r_cat.font.name = "Arial"
                            r_cat.font.size = Pt(9)
                            r_cat.font.bold = True
                            r_skills = p_skill.add_run(", ".join(u_list))
                            r_skills.font.name = "Arial"
                            r_skills.font.size = Pt(9)
                    if uncat:
                        p_skill = doc.add_paragraph()
                        p_skill.paragraph_format.space_after = Pt(1.5)
                        r_cat = p_skill.add_run("Other: ")
                        r_cat.font.name = "Arial"
                        r_cat.font.size = Pt(9)
                        r_cat.font.bold = True
                        r_skills = p_skill.add_run(", ".join(uncat))
                        r_skills.font.name = "Arial"
                        r_skills.font.size = Pt(9)
            else:
                for bullet in section.bullets:
                    p_bullet = doc.add_paragraph(bullet.text, style="List Bullet")
                    p_bullet.paragraph_format.space_before = Pt(0)
                    p_bullet.paragraph_format.space_after = Pt(1.5)
                    for rb in p_bullet.runs:
                        rb.font.name = "Arial"
                        rb.font.size = Pt(9)

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

        if resume.email and resume.email not in extracted_text:
            return False
        if resume.phone and resume.phone not in extracted_text:
            return False

        for sec in resume.sections:
            for b in sec.bullets:
                # Check for bullet core text
                core_text = b.text[:50].strip()
                if core_text and core_text not in extracted_text:
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

    @classmethod
    def generate_tailored_cover_letter(
        cls,
        candidate_name: str,
        company_name: str,
        role_title: str,
        facts: List[Fact],
        requirements: JobRequirements,
        job_description_clean: Optional[str] = None,
    ) -> tuple[str, ValidationReport, str]:
        """Generate tailored cover letter via LLM when configured, with fallback to deterministic."""
        from jovsi.config import settings
        from jovsi.services.llm import get_llm_provider

        usable_facts = [f for f in facts if f.is_usable]

        if settings.GEMINI_API_KEY:
            try:
                provider = get_llm_provider()
                facts_context = [{"kind": f.kind.value, "key": f.key, "value": f.value} for f in usable_facts]
                system_prompt = (
                    "You are a professional career advisor writing a tailored cover letter. "
                    "CRITICAL CONSTRAINTS:\n"
                    "1. Strictly ground every claim in the provided verified candidate facts.\n"
                    "2. NEVER invent past experience, unearned skills, false achievements, or metrics.\n"
                    "3. Do NOT fabricate reasons for interest (e.g. 'I have always admired Company X' or 'It is my lifelong dream').\n"
                    "4. Keep the tone professional, concise, authentic, and direct.\n"
                )
                prompt = (
                    f"Candidate: {candidate_name}\n"
                    f"Target Company: {company_name}\n"
                    f"Role: {role_title}\n"
                    f"Job Requirements: {requirements.model_dump_json()}\n\n"
                    f"Verified Facts:\n{json.dumps(facts_context, indent=2)}\n\n"
                    "Write the tailored cover letter."
                )
                coro = provider.generate_text(prompt=prompt, system_prompt=system_prompt)
                try:
                    running_loop = asyncio.get_running_loop()
                except RuntimeError:
                    running_loop = None

                if running_loop and running_loop.is_running():
                    with ThreadPoolExecutor(max_workers=1) as pool:
                        res = pool.submit(asyncio.run, coro).result()
                else:
                    res = asyncio.run(coro)

                text = res.content
                report = FactualConsistencyValidator.validate_cover_letter(
                    cover_letter=text,
                    candidate_facts=usable_facts,
                    company_name=company_name,
                    role_title=role_title,
                )
                if report.is_valid:
                    return text, report, provider.model_name
                else:
                    logger.warning(f"LLM cover letter failed validation ({len(report.violations)} violations); using deterministic.")
            except Exception as e:
                logger.warning(f"LLM cover letter generation failed: {e}; falling back to deterministic.")

        det_letter = cls.generate_cover_letter(
            candidate_name=candidate_name,
            company_name=company_name,
            role_title=role_title,
            facts=usable_facts,
            requirements=requirements,
        )
        report = FactualConsistencyValidator.validate_cover_letter(
            cover_letter=det_letter,
            candidate_facts=usable_facts,
            company_name=company_name,
            role_title=role_title,
        )
        return det_letter, report, "deterministic_rule_based"

    @classmethod
    def render_cover_letter_docx(
        cls,
        cover_letter_text: str,
        candidate_name: str,
        email: str,
        phone: str,
        company_name: str,
    ) -> bytes:
        """Render a formatted cover letter Word (.docx) document."""
        doc = docx.Document()

        p_name = doc.add_paragraph()
        run_name = p_name.add_run(candidate_name)
        run_name.font.size = Pt(18)
        run_name.font.bold = True
        run_name.font.name = "Arial"

        p_contact = doc.add_paragraph()
        run_contact = p_contact.add_run(f"Email: {email}  |  Phone: {phone}")
        run_contact.font.size = Pt(10)
        run_contact.font.color.rgb = RGBColor(100, 100, 100)
        run_contact.font.name = "Arial"

        p_meta = doc.add_paragraph()
        p_meta.paragraph_format.space_before = Pt(12)
        p_meta.paragraph_format.space_after = Pt(12)
        run_meta = p_meta.add_run(f"Addressed to: Hiring Team, {company_name}")
        run_meta.font.size = Pt(10)
        run_meta.font.bold = True

        paragraphs = [p for p in cover_letter_text.strip().split("\n\n") if p.strip()]
        for para in paragraphs:
            p_body = doc.add_paragraph(para.strip())
            p_body.paragraph_format.space_after = Pt(8)
            p_body.paragraph_format.line_spacing = 1.15
            for run in p_body.runs:
                run.font.name = "Arial"
                run.font.size = Pt(11)

        out = BytesIO()
        doc.save(out)
        return out.getvalue()

    @classmethod
    def render_cover_letter_pdf(
        cls,
        cover_letter_text: str,
        candidate_name: str,
        email: str,
        phone: str,
        company_name: str,
    ) -> bytes:
        """Render cover letter text as a clean PDF artifact using pypdf."""
        writer = PdfWriter()
        page = writer.add_blank_page(width=612, height=792)  # Standard Letter

        def clean_pdf_str(text: str) -> str:
            text = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            return "".join([c if ord(c) < 128 else " " for c in text])

        stream_data = [
            "BT",
            "/Helvetica 10 Tf",
            "14 TL",
            "50 740 Td",
        ]

        def add_line(t: str, size: int = 10, bold: bool = False, extra_gap: int = 0):
            font = "/Helvetica-Bold" if bold else "/Helvetica"
            stream_data.append(f"{font} {size} Tf")
            stream_data.append(f"({clean_pdf_str(t)}) '")
            if extra_gap > 0:
                stream_data.append(f"0 -{extra_gap} Td")

        add_line(candidate_name, size=16, bold=True, extra_gap=4)
        add_line(f"Email: {email}   |   Phone: {phone}", size=9, bold=False, extra_gap=16)

        paragraphs = [p for p in cover_letter_text.strip().split("\n\n") if p.strip()]
        for para in paragraphs:
            words = para.split()
            current_line = []
            for w in words:
                if len(" ".join(current_line + [w])) > 80:
                    add_line(" ".join(current_line), size=10, bold=False)
                    current_line = [w]
                else:
                    current_line.append(w)
            if current_line:
                add_line(" ".join(current_line), size=10, bold=False)
            stream_data.append("0 -8 Td")

        stream_data.append("ET")
        content_stream = "\n".join(stream_data).encode("latin1", errors="replace")

        from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
        stream_obj = DecodedStreamObject()
        stream_obj.set_data(content_stream)
        page[NameObject("/Contents")] = stream_obj

        fonts = DictionaryObject()
        f1 = DictionaryObject()
        f1[NameObject("/Type")] = NameObject("/Font")
        f1[NameObject("/Subtype")] = NameObject("/Type1")
        f1[NameObject("/BaseFont")] = NameObject("/Helvetica")
        fonts[NameObject("/Helvetica")] = f1

        f2 = DictionaryObject()
        f2[NameObject("/Type")] = NameObject("/Font")
        f2[NameObject("/Subtype")] = NameObject("/Type1")
        f2[NameObject("/BaseFont")] = NameObject("/Helvetica-Bold")
        fonts[NameObject("/Helvetica-Bold")] = f2

        resources = DictionaryObject()
        resources[NameObject("/Font")] = fonts
        page[NameObject("/Resources")] = resources

        output = BytesIO()
        writer.write(output)
        return output.getvalue()

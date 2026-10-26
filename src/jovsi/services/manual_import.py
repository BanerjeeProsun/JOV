"""Manual Job Ingestion & Extraction Engine for JOV.si.

Supports:
1. ATS URL Detection (Greenhouse, Lever, Ashby, SmartRecruiters) -> Calls official ATS APIs
   to extract 100% structured posting data.
2. Generic Webpage Ingestion -> SSRF-safe fetch, JSON-LD Schema.org `JobPosting` and OpenGraph metadata parsing.
3. Policy Compliance -> Blocks automated scraping of restricted boards (LinkedIn, Indeed, Naukri, Wellfound)
   and directs candidate to use direct text import.
4. Database Persistence -> Sanitizes descriptions, parses and indexes structured locations (`job_locations`),
   and deduplicates using canonical job keys.
"""

import html
import json
import re
import urllib.parse
from typing import Any, Dict, List, Optional
import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from jovsi.adapters.db.models import JobDB, JobLocationDB
from jovsi.adapters.sanitizer import UntrustedInputSanitizer
from jovsi.adapters.ssrf import SSRFSafeFetcher, SSRFValidationError, validate_url
from jovsi.domain.models import DegreeLevel, Job, JobRequirements, JobStatus
from jovsi.services.geo import location_parser
from jovsi.services.job_discovery import MasterSkillsDetector


class RestrictedBoardError(ValueError):
    """Raised when an automated import is attempted on an anti-bot protected board."""
    pass


class JobExtractionError(ValueError):
    """Raised when job information could not be extracted from a URL."""
    pass


class ManualImportService:
    RESTRICTED_DOMAINS = [
        "linkedin.com",
        "indeed.com",
        "naukri.com",
        "wellfound.com",
        "angellist.com",
        "cutshort.io",
        "foundit.in",
        "internshala.com",
        "hirist.com",
    ]

    @classmethod
    def extract_from_url(cls, url: str) -> Dict[str, Any]:
        """Extract structured job posting metadata from a URL."""
        if not url or not isinstance(url, str):
            raise JobExtractionError("URL must be provided.")

        # 1. Enforce SSRF safety validation
        try:
            canonical_url, hostname, _ = validate_url(url)
        except SSRFValidationError as err:
            raise JobExtractionError(f"Security validation failed: {err}")

        parsed = urllib.parse.urlsplit(canonical_url)
        host_lower = parsed.netloc.lower()

        # 2. Check for restricted platforms with active anti-bot policies
        for r_domain in cls.RESTRICTED_DOMAINS:
            if r_domain in host_lower:
                platform_name = r_domain.split(".")[0].capitalize()
                raise RestrictedBoardError(
                    f"Automated URL import is restricted by {platform_name}'s Terms of Service and anti-scraping policies. "
                    "Please paste the job description text directly into the Manual Import form."
                )

        # 3. Check for known ATS patterns
        # A. Greenhouse
        gh_match = re.search(r"boards\.greenhouse\.io/(?:embed/job_app\?token=|)([^/]+)/jobs/(\d+)", canonical_url)
        if not gh_match:
            gh_match = re.search(r"boards\.greenhouse\.io/([^/]+)/jobs/(\d+)", canonical_url)
        if gh_match:
            board = gh_match.group(1)
            job_id = gh_match.group(2)
            return cls._fetch_greenhouse_job(board, job_id, canonical_url)

        # B. Lever
        lever_match = re.search(r"jobs\.lever\.co/([^/]+)/([a-f0-9\-]+)", canonical_url, re.IGNORECASE)
        if lever_match:
            company = lever_match.group(1)
            job_id = lever_match.group(2)
            return cls._fetch_lever_job(company, job_id, canonical_url)

        # C. Ashby
        ashby_match = re.search(r"jobs\.ashbyhq\.com/([^/]+)/([a-f0-9\-]+)", canonical_url, re.IGNORECASE)
        if ashby_match:
            company = ashby_match.group(1)
            job_id = ashby_match.group(2)
            return cls._fetch_ashby_job(company, job_id, canonical_url)

        # D. SmartRecruiters
        sr_match = re.search(r"jobs\.smartrecruiters\.com/([^/]+)/([a-zA-Z0-9\-]+)", canonical_url)
        if sr_match:
            company = sr_match.group(1)
            job_id = sr_match.group(2)
            return cls._fetch_smartrecruiters_job(company, job_id, canonical_url)

        # 4. Fallback: Generic Webpage Extraction via SSRFSafeFetcher
        return cls._fetch_generic_webpage(canonical_url)

    @classmethod
    def _fetch_greenhouse_job(cls, board: str, job_id: str, original_url: str) -> Dict[str, Any]:
        api_url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{job_id}?questions=true"
        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.get(api_url)
            if resp.status_code != 200:
                raise JobExtractionError(f"Greenhouse API returned HTTP {resp.status_code} for job {job_id}.")
            data = resp.json()
            title = data.get("title", "Position")
            loc = (data.get("location") or {}).get("name", "Remote / Flexible")
            content_html = data.get("content", "") or ""
            clean_text = html.unescape(content_html)
            clean_text = re.sub(r"<[^>]+>", " ", clean_text)
            clean_text = re.sub(r"\s+", " ", clean_text).strip()

            skills = MasterSkillsDetector.detect_skills(f"{title} {clean_text}")

            return {
                "source": "greenhouse",
                "source_url": original_url,
                "canonical_url": original_url,
                "portal_key": f"greenhouse_{board}",
                "native_id": str(job_id),
                "company_name": board.capitalize(),
                "title": title,
                "location": loc,
                "raw_description": clean_text[:6000] if clean_text else f"Role: {title} at {board.capitalize()}",
                "required_skills": skills[:10],
                "accepted_work_modes": ["remote"] if "remote" in loc.lower() else ["hybrid", "onsite"],
            }
        except Exception as exc:
            raise JobExtractionError(f"Failed to extract Greenhouse posting: {exc}")

    @classmethod
    def _fetch_lever_job(cls, company: str, job_id: str, original_url: str) -> Dict[str, Any]:
        api_url = f"https://api.lever.co/v0/postings/{company}/{job_id}"
        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.get(api_url)
            if resp.status_code != 200:
                raise JobExtractionError(f"Lever API returned HTTP {resp.status_code} for job {job_id}.")
            data = resp.json()
            title = data.get("text", "Position")
            cats = data.get("categories") or {}
            loc = cats.get("location", "Remote / Flexible")
            desc = data.get("descriptionPlain") or data.get("description", "")
            skills = MasterSkillsDetector.detect_skills(f"{title} {desc}")

            return {
                "source": "lever",
                "source_url": original_url,
                "canonical_url": original_url,
                "portal_key": f"lever_{company}",
                "native_id": str(job_id),
                "company_name": company.capitalize(),
                "title": title,
                "location": loc,
                "raw_description": desc[:6000] if desc else f"Role: {title} at {company.capitalize()}",
                "required_skills": skills[:10],
                "accepted_work_modes": ["remote"] if "remote" in loc.lower() else ["hybrid", "onsite"],
            }
        except Exception as exc:
            raise JobExtractionError(f"Failed to extract Lever posting: {exc}")

    @classmethod
    def _fetch_ashby_job(cls, company: str, job_id: str, original_url: str) -> Dict[str, Any]:
        api_url = f"https://api.ashbyhq.com/posting-api/job-board/{company}"
        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.get(api_url)
            if resp.status_code != 200:
                raise JobExtractionError(f"Ashby API returned HTTP {resp.status_code}.")
            jobs = resp.json().get("jobs", [])
            match = next((j for j in jobs if str(j.get("id")) == job_id), None)
            if not match:
                raise JobExtractionError(f"Job {job_id} not found on Ashby board '{company}'.")

            title = match.get("title", "Position")
            loc = match.get("location") or "Remote / Flexible"
            desc_html = match.get("descriptionHtml") or match.get("descriptionPlain", "")
            clean_text = html.unescape(desc_html)
            clean_text = re.sub(r"<[^>]+>", " ", clean_text)
            clean_text = re.sub(r"\s+", " ", clean_text).strip()
            skills = MasterSkillsDetector.detect_skills(f"{title} {clean_text}")

            return {
                "source": "ashby",
                "source_url": original_url,
                "canonical_url": original_url,
                "portal_key": f"ashby_{company}",
                "native_id": str(job_id),
                "company_name": company.capitalize(),
                "title": title,
                "location": loc,
                "raw_description": clean_text[:6000] if clean_text else f"Role: {title} at {company.capitalize()}",
                "required_skills": skills[:10],
                "accepted_work_modes": ["remote"] if "remote" in loc.lower() else ["hybrid", "onsite"],
            }
        except Exception as exc:
            raise JobExtractionError(f"Failed to extract Ashby posting: {exc}")

    @classmethod
    def _fetch_smartrecruiters_job(cls, company: str, job_id: str, original_url: str) -> Dict[str, Any]:
        api_url = f"https://api.smartrecruiters.com/v1/companies/{company}/postings/{job_id}"
        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.get(api_url)
            if resp.status_code != 200:
                raise JobExtractionError(f"SmartRecruiters API returned HTTP {resp.status_code}.")
            data = resp.json()
            title = data.get("name", "Position")
            loc_dict = data.get("location") or {}
            loc_parts = [loc_dict.get("city"), loc_dict.get("region"), loc_dict.get("country")]
            loc = ", ".join([str(p) for p in loc_parts if p]) or "Remote / Flexible"
            job_ad = data.get("jobAd") or {}
            sections = (job_ad.get("sections") or {}).get("jobDescription") or {}
            desc_text = sections.get("text", "") or f"Role: {title} at {company.capitalize()}"
            skills = MasterSkillsDetector.detect_skills(f"{title} {desc_text}")

            return {
                "source": "smartrecruiters",
                "source_url": original_url,
                "canonical_url": original_url,
                "portal_key": f"smartrecruiters_{company}",
                "native_id": str(job_id),
                "company_name": company.capitalize(),
                "title": title,
                "location": loc,
                "raw_description": desc_text[:6000],
                "required_skills": skills[:10],
                "accepted_work_modes": ["remote"] if "remote" in loc.lower() else ["hybrid", "onsite"],
            }
        except Exception as exc:
            raise JobExtractionError(f"Failed to extract SmartRecruiters posting: {exc}")

    @classmethod
    def _fetch_generic_webpage(cls, canonical_url: str) -> Dict[str, Any]:
        """Fetch and extract metadata from generic web pages using Schema.org JSON-LD or OpenGraph."""
        try:
            resp = SSRFSafeFetcher.fetch(canonical_url, timeout=8.0, max_bytes=1_048_576)
        except SSRFValidationError as exc:
            raise JobExtractionError(f"SSRF validation blocked request: {exc}")

        if resp.status_code != 200:
            raise JobExtractionError(f"Target server returned HTTP {resp.status_code}.")

        html_text = resp.text

        # 1. Look for Schema.org JobPosting JSON-LD
        json_ld_matches = re.findall(r'<script[^>]*type=[\'"]application/ld\+json[\'"][^>]*>(.*?)</script>', html_text, re.DOTALL | re.IGNORECASE)
        for match in json_ld_matches:
            try:
                parsed_json = json.loads(match.strip())
                # Could be a single object or a list or a @graph
                candidates = []
                if isinstance(parsed_json, dict):
                    if parsed_json.get("@type") == "JobPosting":
                        candidates.append(parsed_json)
                    elif "@graph" in parsed_json and isinstance(parsed_json["@graph"], list):
                        candidates.extend([item for item in parsed_json["@graph"] if item.get("@type") == "JobPosting"])
                elif isinstance(parsed_json, list):
                    candidates.extend([item for item in parsed_json if isinstance(item, dict) and item.get("@type") == "JobPosting"])

                if candidates:
                    jp = candidates[0]
                    title = jp.get("title", "")
                    hiring_org = jp.get("hiringOrganization") or {}
                    company = hiring_org.get("name", "Company") if isinstance(hiring_org, dict) else str(hiring_org)
                    desc = jp.get("description", "")
                    clean_desc = html.unescape(desc)
                    clean_desc = re.sub(r"<[^>]+>", " ", clean_desc)
                    clean_desc = re.sub(r"\s+", " ", clean_desc).strip()

                    # Location
                    job_loc = jp.get("jobLocation") or {}
                    loc_name = "Remote / Various"
                    if isinstance(job_loc, dict):
                        addr = job_loc.get("address") or {}
                        if isinstance(addr, dict):
                            parts = [addr.get("addressLocality"), addr.get("addressRegion"), addr.get("addressCountry")]
                            loc_name = ", ".join([str(p) for p in parts if p]) or loc_name
                        elif isinstance(addr, str):
                            loc_name = addr

                    skills = MasterSkillsDetector.detect_skills(f"{title} {clean_desc}")
                    return {
                        "source": "web_import",
                        "source_url": canonical_url,
                        "canonical_url": canonical_url,
                        "portal_key": "web_jsonld",
                        "native_id": str(jp.get("identifier") or hashlib_sha1(canonical_url)[:12]),
                        "company_name": company,
                        "title": title,
                        "location": loc_name,
                        "raw_description": clean_desc[:6000] if clean_desc else f"Role: {title} at {company}",
                        "required_skills": skills[:10],
                        "accepted_work_modes": ["remote"] if "remote" in loc_name.lower() else ["hybrid", "onsite"],
                    }
            except Exception:
                continue

        # 2. Fallback: OpenGraph & Title tags
        title_match = re.search(r"<meta[^>]*property=[\"']og:title[\"'][^>]*content=[\"'](.*?)[\"']", html_text, re.IGNORECASE)
        if not title_match:
            title_match = re.search(r"<title>(.*?)</title>", html_text, re.IGNORECASE)
        page_title = html.unescape(title_match.group(1).strip()) if title_match else "Imported Position"

        # Split page title by delimiter if "Role at Company"
        comp_name = "Company"
        title_str = page_title
        for delim in [" at ", " @ ", " - ", " | "]:
            if delim in page_title:
                parts = page_title.split(delim, 1)
                title_str = parts[0].strip()
                comp_name = parts[1].strip()
                break

        desc_match = re.search(r"<meta[^>]*property=[\"']og:description[\"'][^>]*content=[\"'](.*?)[\"']", html_text, re.IGNORECASE)
        if not desc_match:
            desc_match = re.search(r"<meta[^>]*name=[\"']description[\"'][^>]*content=[\"'](.*?)[\"']", html_text, re.IGNORECASE)
        desc_text = html.unescape(desc_match.group(1).strip()) if desc_match else ""

        skills = MasterSkillsDetector.detect_skills(f"{title_str} {desc_text}")
        return {
            "source": "web_import",
            "source_url": canonical_url,
            "canonical_url": canonical_url,
            "portal_key": "web_html",
            "native_id": hashlib_sha1(canonical_url)[:12],
            "company_name": comp_name,
            "title": title_str,
            "location": "Remote / Flexible",
            "raw_description": desc_text[:6000] if desc_text else f"Imported role: {title_str} at {comp_name}",
            "required_skills": skills[:10],
            "accepted_work_modes": ["remote", "hybrid", "onsite"],
        }

    @classmethod
    def import_and_persist(cls, extracted_data: Dict[str, Any], db: Session) -> JobDB:
        """Sanitize, parse location, compute key, and persist into database."""
        raw_desc = extracted_data.get("raw_description", "")
        raw_sha256, cleaned_desc = UntrustedInputSanitizer.sanitize(raw_desc)

        company_norm = extracted_data.get("company_name", "Company").strip()
        title_norm = extracted_data.get("title", "Role").strip()
        portal_key = extracted_data.get("portal_key")
        native_id = extracted_data.get("native_id")

        canonical_key = Job.compute_canonical_key(
            company_norm=company_norm,
            title_norm=title_norm,
            portal_key=portal_key,
            native_id=native_id,
        )

        # Check existing
        existing = db.scalar(
            select(JobDB).where(
                JobDB.source == extracted_data.get("source", "manual_import"),
                JobDB.canonical_job_key == canonical_key,
            )
        )
        if existing:
            return existing

        reqs = JobRequirements(
            min_degree=DegreeLevel.BACHELOR,
            min_experience_months=24,
            required_skills=extracted_data.get("required_skills", []),
            work_auth_countries=["US", "UK", "IN"],
            accepted_work_modes=extracted_data.get("accepted_work_modes", ["remote", "hybrid", "onsite"]),
        )

        new_job = JobDB(
            source=extracted_data.get("source", "manual_import"),
            source_url=extracted_data.get("source_url", ""),
            canonical_url=extracted_data.get("canonical_url", extracted_data.get("source_url", "")),
            canonical_job_key=canonical_key,
            company_norm=company_norm,
            title_norm=title_norm,
            description_clean=cleaned_desc,
            raw_sha256=raw_sha256,
            requirements=reqs.model_dump(),
            status=JobStatus.ACTIVE.value,
        )
        db.add(new_job)
        db.commit()
        db.refresh(new_job)

        # Parse and insert into job_locations
        raw_loc = extracted_data.get("location", "Remote / Flexible")
        for pl in location_parser.parse(raw_loc):
            db.add(
                JobLocationDB(
                    job_id=new_job.id,
                    country_code=pl.country,
                    admin1_code=pl.admin1,
                    city_id=pl.city,
                    work_mode=pl.work_mode_lower,
                    remote_scope=pl.remote_scope_lower,
                    raw_location=pl.raw,
                    confidence=pl.confidence,
                )
            )
        db.commit()
        db.refresh(new_job)
        return new_job


def hashlib_sha1(text: str) -> str:
    import hashlib
    return hashlib.sha1(text.encode("utf-8")).hexdigest()

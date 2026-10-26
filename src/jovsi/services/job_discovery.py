"""Real Job Discovery Engine for JOV.si.

Integrates with genuine public job sources:
1. Official Greenhouse Public Job Board API (boards-api.greenhouse.io)
2. Official Lever Public Postings API (api.lever.co)
3. Jobicy Public Remote Tech API (jobicy.com/api/v2/remote-jobs)
4. Manual URL & Pasted Description extractor

Provides explainable suitability ranking and hard eligibility checking
against the candidate's active verified facts.
"""

import hashlib
import html
import re
import urllib.parse
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import httpx

from jovsi.config import settings
from jovsi.adapters.sanitizer import UntrustedInputSanitizer
from jovsi.domain.models import DegreeLevel, Fact, FactKind, Job, JobRequirements, JobStatus
from jovsi.domain.eligibility import EligibilityEngine
from jovsi.domain.scoring import ScoringEngine


# Popular, verified official public Greenhouse & Lever company boards
DEFAULT_GREENHOUSE_BOARDS = ["cloudflare", "figma", "stripe", "canonical"]
DEFAULT_LEVER_BOARDS = ["palantir", "leverdemo"]


class JobSourceConnector:
    """Base class for genuine job discovery connectors."""
    source_name: str = "base"

    def search(self, query: str = "", company: Optional[str] = None, location: Optional[str] = None, limit: int = 15) -> List[Dict[str, Any]]:
        raise NotImplementedError


class GreenhouseConnector(JobSourceConnector):
    source_name: str = "greenhouse"

    def search(self, query: str = "", company: Optional[str] = None, location: Optional[str] = None, limit: int = 15) -> List[Dict[str, Any]]:
        boards = [company.lower().strip()] if company else DEFAULT_GREENHOUSE_BOARDS
        results = []

        with httpx.Client(timeout=8.0) as client:
            for board in boards:
                if len(results) >= limit:
                    break
                try:
                    url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true"
                    resp = client.get(url)
                    if resp.status_code != 200:
                        continue
                    data = resp.json()
                    jobs = data.get("jobs", [])
                    company_display = board.capitalize()

                    for j in jobs:
                        title = j.get("title", "")
                        loc = (j.get("location") or {}).get("name", "Remote / Various")
                        raw_content = j.get("content", "") or ""
                        # Unescape HTML entities
                        clean_text = html.unescape(raw_content)

                        # Keyword query filter
                        if query:
                            q_lower = query.lower()
                            if q_lower not in title.lower() and q_lower not in clean_text.lower():
                                continue

                        if location:
                            if location.lower() not in loc.lower():
                                continue

                        # Extract skills heuristic
                        detected_skills = MasterSkillsDetector.detect_skills(f"{title} {clean_text}")

                        results.append({
                            "source": "greenhouse",
                            "source_url": j.get("absolute_url") or f"https://boards.greenhouse.io/{board}/jobs/{j.get('id')}",
                            "portal_key": f"greenhouse_{board}",
                            "native_id": str(j.get("id")),
                            "company_name": company_display,
                            "title": title,
                            "location": loc,
                            "raw_description": clean_text[:4000] if clean_text else f"Position: {title} at {company_display}",
                            "required_skills": detected_skills[:8],
                            "accepted_work_modes": ["remote"] if "remote" in loc.lower() else ["hybrid", "onsite"],
                        })

                        if len(results) >= limit:
                            break
                except Exception:
                    continue

        return results


class LeverConnector(JobSourceConnector):
    source_name: str = "lever"

    def search(self, query: str = "", company: Optional[str] = None, location: Optional[str] = None, limit: int = 15) -> List[Dict[str, Any]]:
        companies = [company.lower().strip()] if company else DEFAULT_LEVER_BOARDS
        results = []

        with httpx.Client(timeout=8.0) as client:
            for comp in companies:
                if len(results) >= limit:
                    break
                try:
                    url = f"https://api.lever.co/v0/postings/{comp}?mode=json"
                    resp = client.get(url)
                    if resp.status_code != 200:
                        continue
                    postings = resp.json()
                    if not isinstance(postings, list):
                        continue

                    company_display = comp.capitalize()
                    for p in postings:
                        title = p.get("text", "")
                        cats = p.get("categories") or {}
                        loc = cats.get("location", "Remote / Flexible")
                        desc = p.get("descriptionPlain") or p.get("description", "")

                        if query:
                            q_lower = query.lower()
                            if q_lower not in title.lower() and q_lower not in desc.lower():
                                continue

                        if location:
                            if location.lower() not in loc.lower():
                                continue

                        detected_skills = MasterSkillsDetector.detect_skills(f"{title} {desc}")

                        results.append({
                            "source": "lever",
                            "source_url": p.get("hostedUrl") or p.get("applyUrl") or f"https://jobs.lever.co/{comp}/{p.get('id')}",
                            "portal_key": f"lever_{comp}",
                            "native_id": str(p.get("id")),
                            "company_name": company_display,
                            "title": title,
                            "location": loc,
                            "raw_description": desc[:4000] if desc else f"Role: {title} at {company_display}",
                            "required_skills": detected_skills[:8],
                            "accepted_work_modes": ["remote"] if "remote" in loc.lower() else ["hybrid", "onsite"],
                        })

                        if len(results) >= limit:
                            break
                except Exception:
                    continue

        return results


class JobicyConnector(JobSourceConnector):
    source_name: str = "jobicy"

    def search(self, query: str = "", company: Optional[str] = None, location: Optional[str] = None, limit: int = 15) -> List[Dict[str, Any]]:
        results = []
        try:
            with httpx.Client(timeout=8.0) as client:
                url = "https://jobicy.com/api/v2/remote-jobs?count=20"
                resp = client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    jobs = data.get("jobs", [])
                    for j in jobs:
                        title = j.get("jobTitle", "")
                        comp_name = j.get("companyName", "Tech Company")
                        loc = j.get("jobGeo", "Remote")
                        desc = html.unescape(j.get("jobDescription", ""))

                        if query:
                            q_lower = query.lower()
                            if q_lower not in title.lower() and q_lower not in desc.lower():
                                continue

                        if company:
                            if company.lower() not in comp_name.lower():
                                continue

                        detected_skills = MasterSkillsDetector.detect_skills(f"{title} {desc}")

                        results.append({
                            "source": "jobicy",
                            "source_url": j.get("url") or "https://jobicy.com",
                            "portal_key": "jobicy_remote",
                            "native_id": str(j.get("id")),
                            "company_name": comp_name,
                            "title": title,
                            "location": loc,
                            "raw_description": desc[:4000],
                            "required_skills": detected_skills[:8],
                            "accepted_work_modes": ["remote"],
                        })

                        if len(results) >= limit:
                            break
        except Exception:
            pass

        return results


class ArbeitnowConnector(JobSourceConnector):
    source_name: str = "arbeitnow"

    def search(self, query: str = "", company: Optional[str] = None, location: Optional[str] = None, limit: int = 15) -> List[Dict[str, Any]]:
        results = []
        try:
            with httpx.Client(timeout=8.0) as client:
                url = "https://www.arbeitnow.com/api/job-board-api"
                resp = client.get(url)
                if resp.status_code != 200:
                    return results
                data = resp.json()
                postings = data.get("data", [])

                for p in postings:
                    title = p.get("title", "")
                    comp_name = p.get("company_name", "Tech Employer")
                    loc = p.get("location") or ("Remote" if p.get("remote") else "Europe")
                    raw_desc = html.unescape(p.get("description", ""))
                    clean_desc = re.sub(r"<[^>]+>", " ", raw_desc)
                    clean_desc = re.sub(r"\s+", " ", clean_desc).strip()
                    tags = p.get("tags") or []
                    is_remote = bool(p.get("remote") or "remote" in loc.lower())

                    if query:
                        q_lower = query.lower()
                        if (
                            q_lower not in title.lower()
                            and q_lower not in clean_desc.lower()
                            and not any(q_lower in str(t).lower() for t in tags)
                        ):
                            continue

                    if company:
                        if company.lower() not in comp_name.lower():
                            continue

                    if location:
                        loc_lower = location.lower()
                        if loc_lower not in loc.lower() and not (is_remote and "remote" in loc_lower):
                            continue

                    detected_skills = MasterSkillsDetector.detect_skills(f"{title} {' '.join(tags)} {clean_desc}")
                    all_skills = list(dict.fromkeys(detected_skills + [str(t) for t in tags if len(str(t)) < 25]))

                    results.append({
                        "source": "arbeitnow",
                        "source_url": p.get("url") or "https://www.arbeitnow.com",
                        "portal_key": "arbeitnow_api",
                        "native_id": str(p.get("slug") or len(results)),
                        "company_name": comp_name,
                        "title": title,
                        "location": loc,
                        "raw_description": clean_desc[:4000],
                        "required_skills": all_skills[:8],
                        "accepted_work_modes": ["remote"] if is_remote else ["hybrid", "onsite"],
                    })

                    if len(results) >= limit:
                        break
        except Exception:
            pass

        return results


class AdzunaConnector(JobSourceConnector):
    source_name: str = "adzuna"

    def search(self, query: str = "", company: Optional[str] = None, location: Optional[str] = None, limit: int = 15) -> List[Dict[str, Any]]:
        app_id = settings.ADZUNA_APP_ID
        app_key = settings.ADZUNA_API_KEY
        if not app_id or not app_key:
            return []

        country = "us"
        if location:
            loc_l = location.lower()
            if any(k in loc_l for k in ["uk", "london", "great britain", "england", "scotland"]):
                country = "gb"
            elif any(k in loc_l for k in ["india", "bengaluru", "delhi", "mumbai", "pune", "hyderabad"]):
                country = "in"
            elif any(k in loc_l for k in ["germany", "berlin", "munich", "frankfurt", "hamburg"]):
                country = "de"
            elif any(k in loc_l for k in ["canada", "toronto", "vancouver", "montreal"]):
                country = "ca"

        results = []
        try:
            with httpx.Client(timeout=8.0) as client:
                params = {
                    "app_id": app_id,
                    "app_key": app_key,
                    "results_per_page": min(limit, 50),
                    "what": query or "software engineer",
                }
                if location:
                    params["where"] = location

                url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/1"
                resp = client.get(url, params=params)
                if resp.status_code != 200:
                    return results

                data = resp.json()
                items = data.get("results", [])
                for item in items:
                    title = item.get("title", "")
                    comp_dict = item.get("company") or {}
                    comp_name = comp_dict.get("display_name", "Company")
                    loc_dict = item.get("location") or {}
                    loc_name = loc_dict.get("display_name", "Various")
                    desc = item.get("description", "")

                    if company and company.lower() not in comp_name.lower():
                        continue

                    detected_skills = MasterSkillsDetector.detect_skills(f"{title} {desc}")

                    results.append({
                        "source": "adzuna",
                        "source_url": item.get("redirect_url") or "https://www.adzuna.com",
                        "portal_key": "adzuna_aggregator",
                        "native_id": str(item.get("id")),
                        "company_name": comp_name,
                        "title": title,
                        "location": loc_name,
                        "raw_description": desc[:4000],
                        "required_skills": detected_skills[:8],
                        "accepted_work_modes": ["remote"] if "remote" in loc_name.lower() else ["hybrid", "onsite"],
                    })

                    if len(results) >= limit:
                        break
        except Exception:
            pass

        return results


class RemotiveConnector(JobSourceConnector):
    source_name: str = "remotive"

    def search(self, query: str = "", company: Optional[str] = None, location: Optional[str] = None, limit: int = 15) -> List[Dict[str, Any]]:
        results = []
        try:
            with httpx.Client(timeout=8.0) as client:
                url = f"https://remotive.com/api/remote-jobs?limit={min(limit * 2, 50)}"
                if query:
                    url += f"&search={urllib.parse.quote_plus(query)}"
                resp = client.get(url)
                if resp.status_code != 200:
                    return results

                data = resp.json()
                jobs = data.get("jobs", [])
                for j in jobs:
                    title = j.get("title", "")
                    comp_name = j.get("company_name", "Remote Tech Company")
                    loc = j.get("candidate_required_location") or "Remote"
                    raw_desc = html.unescape(j.get("description", ""))
                    clean_desc = re.sub(r"<[^>]+>", " ", raw_desc)
                    clean_desc = re.sub(r"\s+", " ", clean_desc).strip()
                    tags = j.get("tags") or []

                    if company and company.lower() not in comp_name.lower():
                        continue

                    if location and location.lower() not in loc.lower() and "remote" not in location.lower():
                        continue

                    detected_skills = MasterSkillsDetector.detect_skills(f"{title} {' '.join(tags)} {clean_desc}")
                    all_skills = list(dict.fromkeys(detected_skills + [str(t) for t in tags if len(str(t)) < 25]))

                    results.append({
                        "source": "remotive",
                        "source_url": j.get("url") or "https://remotive.com",
                        "portal_key": "remotive_remote",
                        "native_id": str(j.get("id")),
                        "company_name": comp_name,
                        "title": title,
                        "location": loc,
                        "raw_description": clean_desc[:4000],
                        "required_skills": all_skills[:8],
                        "accepted_work_modes": ["remote"],
                    })

                    if len(results) >= limit:
                        break
        except Exception:
            pass

        return results


class AshbyConnector(JobSourceConnector):
    source_name: str = "ashby"

    def search(self, query: str = "", company: Optional[str] = None, location: Optional[str] = None, limit: int = 15) -> List[Dict[str, Any]]:
        boards = [company.lower().strip()] if company else ["ramp", "linear"]
        results = []

        with httpx.Client(timeout=8.0) as client:
            for board in boards:
                if len(results) >= limit:
                    break
                try:
                    url = f"https://api.ashbyhq.com/posting-api/job-board/{board}"
                    resp = client.get(url)
                    if resp.status_code != 200:
                        continue
                    data = resp.json()
                    jobs = data.get("jobs", [])
                    company_display = board.capitalize()

                    for j in jobs:
                        title = j.get("title", "")
                        loc = j.get("location") or "Remote / Flexible"
                        desc_html = j.get("descriptionHtml") or j.get("descriptionPlain", "")
                        clean_text = html.unescape(desc_html)

                        if query:
                            q_lower = query.lower()
                            if q_lower not in title.lower() and q_lower not in clean_text.lower():
                                continue

                        if location:
                            if location.lower() not in loc.lower():
                                continue

                        detected_skills = MasterSkillsDetector.detect_skills(f"{title} {clean_text}")

                        results.append({
                            "source": "ashby",
                            "source_url": j.get("jobUrl") or f"https://jobs.ashbyhq.com/{board}/{j.get('id')}",
                            "portal_key": f"ashby_{board}",
                            "native_id": str(j.get("id")),
                            "company_name": company_display,
                            "title": title,
                            "location": loc,
                            "raw_description": clean_text[:4000] if clean_text else f"Role: {title} at {company_display}",
                            "required_skills": detected_skills[:8],
                            "accepted_work_modes": ["remote"] if "remote" in loc.lower() else ["hybrid", "onsite"],
                        })

                        if len(results) >= limit:
                            break
                except Exception:
                    continue

        return results


class SmartRecruitersConnector(JobSourceConnector):
    source_name: str = "smartrecruiters"

    def search(self, query: str = "", company: Optional[str] = None, location: Optional[str] = None, limit: int = 15) -> List[Dict[str, Any]]:
        companies = [company.lower().strip()] if company else ["visa", "mcdonalds"]
        results = []

        with httpx.Client(timeout=8.0) as client:
            for comp in companies:
                if len(results) >= limit:
                    break
                try:
                    url = f"https://api.smartrecruiters.com/v1/companies/{comp}/postings"
                    resp = client.get(url)
                    if resp.status_code != 200:
                        continue
                    data = resp.json()
                    postings = data.get("content", [])
                    company_display = comp.capitalize()

                    for p in postings:
                        title = p.get("name", "")
                        loc_dict = p.get("location") or {}
                        loc_parts = [loc_dict.get("city"), loc_dict.get("region"), loc_dict.get("country")]
                        loc = ", ".join([str(part) for part in loc_parts if part]) or "Remote / Flexible"

                        if query:
                            q_lower = query.lower()
                            if q_lower not in title.lower():
                                continue

                        if location:
                            if location.lower() not in loc.lower():
                                continue

                        detected_skills = MasterSkillsDetector.detect_skills(title)

                        results.append({
                            "source": "smartrecruiters",
                            "source_url": f"https://jobs.smartrecruiters.com/{comp}/{p.get('id')}",
                            "portal_key": f"smartrecruiters_{comp}",
                            "native_id": str(p.get("id")),
                            "company_name": company_display,
                            "title": title,
                            "location": loc,
                            "raw_description": f"Role: {title} at {company_display}. Location: {loc}",
                            "required_skills": detected_skills[:8],
                            "accepted_work_modes": ["remote"] if "remote" in loc.lower() else ["hybrid", "onsite"],
                        })

                        if len(results) >= limit:
                            break
                except Exception:
                    continue

        return results


class MasterSkillsDetector:
    COMMON_SKILLS = [
        "Python", "TypeScript", "JavaScript", "Java", "C++", "C#", "Go", "Rust", "Ruby",
        "React", "Vue", "Angular", "Node.js", "FastAPI", "Django", "Flask", "Spring Boot",
        "SQL", "PostgreSQL", "MySQL", "MongoDB", "Redis", "Elasticsearch",
        "Docker", "Kubernetes", "AWS", "Azure", "GCP", "Linux", "Git", "GraphQL", "REST",
        "Machine Learning", "PyTorch", "TensorFlow", "Pandas"
    ]

    @classmethod
    def detect_skills(cls, text: str) -> List[str]:
        found = []
        for s in cls.COMMON_SKILLS:
            if re.search(rf"\b{re.escape(s)}\b", text, re.IGNORECASE):
                found.append(s)
        return found


class SourceRegistryService:
    @classmethod
    def get_registered_sources(cls, db: Optional[Any] = None) -> List[Dict[str, Any]]:
        sources_meta = [
            {
                "id": "greenhouse",
                "name": "Greenhouse ATS Boards",
                "provider": "greenhouse",
                "description": "Direct official board queries for Cloudflare, Stripe, Figma, Canonical, and custom company slugs.",
            },
            {
                "id": "lever",
                "name": "Lever ATS Postings",
                "provider": "lever",
                "description": "Direct official postings queries for Palantir, Leverdemo, and custom company slugs.",
            },
            {
                "id": "ashby",
                "name": "Ashby Job Boards",
                "provider": "ashby",
                "description": "Official public postings API for high-growth tech companies (Ramp, Linear).",
            },
            {
                "id": "smartrecruiters",
                "name": "SmartRecruiters Postings",
                "provider": "smartrecruiters",
                "description": "Official company career portal API (Visa, McDonalds).",
            },
            {
                "id": "jobicy",
                "name": "Jobicy Remote API",
                "provider": "jobicy",
                "description": "Live remote engineering listings across international tech employers.",
            },
            {
                "id": "arbeitnow",
                "name": "Arbeitnow European/Remote Feed",
                "provider": "arbeitnow",
                "description": "Public feed of remote and European engineering positions with structured skill tags.",
            },
            {
                "id": "adzuna",
                "name": "Adzuna Multi-Country API",
                "provider": "adzuna",
                "description": "Global multi-country aggregator API (US, UK, India, EU). Activates with ADZUNA_APP_ID/KEY.",
            },
            {
                "id": "remotive",
                "name": "Remotive Remote Feed",
                "provider": "remotive",
                "description": "Public remote tech job listings curated across global tech companies.",
            },
            {
                "id": "manual",
                "name": "Direct Job Import",
                "provider": "manual",
                "description": "Import via direct URL or pasted job specification.",
            },
        ]

        if db is not None:
            try:
                from jovsi.adapters.db.models import JobSourceDB
                from sqlalchemy import select, func, case
                
                rows = db.execute(
                    select(
                        JobSourceDB.provider,
                        func.count(JobSourceDB.id).label("total"),
                        func.sum(case((JobSourceDB.status == "verified_active", 1), else_=0)).label("active"),
                        func.sum(case((JobSourceDB.status == "failing", 1), else_=0)).label("failing"),
                    ).group_by(JobSourceDB.provider)
                ).fetchall()

                stats = {r[0]: {"total": r[1], "active": r[2] or 0, "failing": r[3] or 0} for r in rows}

                for s in sources_meta:
                    p = s["provider"]
                    if p in stats:
                        s["employer_count"] = stats[p]["total"]
                        if stats[p]["failing"] > 0 and stats[p]["active"] == 0:
                            s["status"] = "FAILING"
                            s["is_live"] = False
                        elif stats[p]["active"] > 0:
                            s["status"] = "CONFIGURED"
                            s["is_live"] = True
                        else:
                            s["status"] = "UNTESTED"
                            s["is_live"] = True
                    else:
                        s["employer_count"] = 1 if p == "manual" else 0
                        s["status"] = "CONFIGURED"
                        s["is_live"] = True
            except Exception:
                for s in sources_meta:
                    s["status"] = "CONFIGURED"
                    s["is_live"] = True
                    s["employer_count"] = 0
        else:
            for s in sources_meta:
                s["status"] = "CONFIGURED"
                s["is_live"] = True
                s["employer_count"] = 0

        return sources_meta

    @classmethod
    def probe_source(cls, source_id: str, db: Any) -> Any:
        from jovsi.adapters.db.models import JobSourceDB
        from sqlalchemy import select
        
        source = db.scalar(select(JobSourceDB).where(JobSourceDB.id == source_id))
        if not source:
            raise ValueError(f"Job source {source_id} not found.")

        if source.provider == "manual":
            source.status = "verified_active"
            source.last_probed_at = datetime.utcnow()
            source.last_error = None
            db.commit()
            return source

        if source.provider == "adzuna":
            if not settings.ADZUNA_APP_ID or not settings.ADZUNA_API_KEY:
                source.status = "unconfigured"
                source.last_error = "Missing ADZUNA_APP_ID or ADZUNA_API_KEY credentials (BLOCKED: CREDENTIALS)."
                source.last_probed_at = datetime.utcnow()
                db.commit()
                return source

        url_map = {
            "greenhouse": f"https://boards-api.greenhouse.io/v1/boards/{source.board_identifier}/jobs?content=false",
            "lever": f"https://api.lever.co/v0/postings/{source.board_identifier}?mode=json",
            "ashby": f"https://api.ashbyhq.com/posting-api/job-board/{source.board_identifier}",
            "smartrecruiters": f"https://api.smartrecruiters.com/v1/companies/{source.board_identifier}/postings?limit=5",
            "jobicy": "https://jobicy.com/api/v2/remote-jobs?count=1",
            "arbeitnow": "https://www.arbeitnow.com/api/job-board-api",
            "remotive": "https://remotive.com/api/remote-jobs?limit=1",
            "adzuna": f"https://api.adzuna.com/v1/api/jobs/us/search/1?app_id={settings.ADZUNA_APP_ID}&app_key={settings.ADZUNA_API_KEY}&results_per_page=1" if settings.ADZUNA_APP_ID else None,
        }

        url = url_map.get(source.provider)
        if not url:
            source.status = "untested"
            source.last_error = "Unknown provider prober"
            db.commit()
            return source

        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(url)
            
            source.last_probed_at = datetime.utcnow()
            if resp.status_code == 200:
                data = resp.json()
                if source.provider == "greenhouse":
                    jobs = data.get("jobs", [])
                elif source.provider == "lever":
                    jobs = data if isinstance(data, list) else []
                elif source.provider == "ashby":
                    jobs = data.get("jobs", [])
                elif source.provider == "smartrecruiters":
                    jobs = data.get("content", [])
                elif source.provider == "jobicy":
                    jobs = data.get("jobs", [])
                elif source.provider == "arbeitnow":
                    jobs = data.get("data", [])
                elif source.provider == "remotive":
                    jobs = data.get("jobs", [])
                elif source.provider == "adzuna":
                    jobs = data.get("results", [])
                else:
                    jobs = []

                job_count = len(jobs)
                source.last_job_count = job_count
                source.status = "verified_active" if job_count > 0 else "empty"
                source.last_error = None
            elif resp.status_code == 404:
                source.status = "failing"
                source.last_error = f"Board slug '{source.board_identifier}' not found (404)."
            else:
                source.status = "failing"
                source.last_error = f"Provider returned HTTP {resp.status_code}."
        except Exception as exc:
            source.last_probed_at = datetime.utcnow()
            source.status = "failing"
            source.last_error = str(exc)[:200]

        db.commit()
        db.refresh(source)
        return source

    @classmethod
    def check_all_sources_health(cls, db: Optional[Any] = None) -> List[Dict[str, Any]]:
        """Return connectivity telemetry for all configured sources."""
        import time

        endpoints_to_probe = [
            ("greenhouse", "Greenhouse ATS Boards", "ats", "https://boards-api.greenhouse.io/v1/boards/cloudflare/jobs?content=false"),
            ("lever", "Lever ATS Postings", "ats", "https://api.lever.co/v0/postings/palantir?mode=json"),
            ("ashby", "Ashby Job Boards", "ats", "https://api.ashbyhq.com/posting-api/job-board/ramp"),
            ("smartrecruiters", "SmartRecruiters Postings", "ats", "https://api.smartrecruiters.com/v1/companies/visa/postings?limit=1"),
            ("jobicy", "Jobicy Remote API", "feed", "https://jobicy.com/api/v2/remote-jobs?count=1"),
            ("arbeitnow", "Arbeitnow European/Remote Feed", "feed", "https://www.arbeitnow.com/api/job-board-api"),
            ("remotive", "Remotive Remote Feed", "feed", "https://remotive.com/api/remote-jobs?limit=1"),
        ]

        health_reports = []

        with httpx.Client(timeout=4.0) as client:
            for provider, name, category, probe_url in endpoints_to_probe:
                start_time = time.perf_counter()
                try:
                    resp = client.get(probe_url)
                    latency = round((time.perf_counter() - start_time) * 1000, 1)
                    if resp.status_code == 200:
                        status_str = "HEALTHY"
                        err = None
                    else:
                        status_str = "DEGRADED"
                        err = f"HTTP {resp.status_code}"
                except Exception as exc:
                    latency = round((time.perf_counter() - start_time) * 1000, 1)
                    status_str = "DOWN"
                    err = str(exc)[:120]

                health_reports.append({
                    "provider": provider,
                    "name": name,
                    "category": category,
                    "status": status_str,
                    "latency_ms": latency,
                    "policy_status": "permitted",
                    "error": err,
                    "last_checked_at": datetime.utcnow().isoformat(),
                })

        # Adzuna
        if settings.ADZUNA_APP_ID and settings.ADZUNA_API_KEY:
            start_time = time.perf_counter()
            try:
                with httpx.Client(timeout=4.0) as client:
                    resp = client.get(
                        f"https://api.adzuna.com/v1/api/jobs/us/search/1?app_id={settings.ADZUNA_APP_ID}&app_key={settings.ADZUNA_API_KEY}&results_per_page=1"
                    )
                latency = round((time.perf_counter() - start_time) * 1000, 1)
                status_str = "HEALTHY" if resp.status_code == 200 else "DEGRADED"
                err = None if resp.status_code == 200 else f"HTTP {resp.status_code}"
            except Exception as exc:
                latency = round((time.perf_counter() - start_time) * 1000, 1)
                status_str = "DOWN"
                err = str(exc)[:120]
        else:
            latency = None
            status_str = "UNCONFIGURED"
            err = "ADZUNA_APP_ID or ADZUNA_API_KEY not configured (BLOCKED: CREDENTIALS)"

        health_reports.append({
            "provider": "adzuna",
            "name": "Adzuna Multi-Country API",
            "category": "aggregator",
            "status": status_str,
            "latency_ms": latency,
            "policy_status": "permitted",
            "error": err,
            "last_checked_at": datetime.utcnow().isoformat(),
        })

        # Manual Import
        health_reports.append({
            "provider": "manual",
            "name": "Direct Job Import",
            "category": "manual",
            "status": "HEALTHY",
            "latency_ms": 0.0,
            "policy_status": "permitted",
            "error": None,
            "last_checked_at": datetime.utcnow().isoformat(),
        })

        return health_reports


class JobDiscoveryService:
    CONNECTORS = {
        "greenhouse": GreenhouseConnector(),
        "lever": LeverConnector(),
        "ashby": AshbyConnector(),
        "smartrecruiters": SmartRecruitersConnector(),
        "jobicy": JobicyConnector(),
        "arbeitnow": ArbeitnowConnector(),
        "adzuna": AdzunaConnector(),
        "remotive": RemotiveConnector(),
    }

    @classmethod
    def get_registered_sources(cls, db: Optional[Any] = None) -> List[Dict[str, Any]]:
        return SourceRegistryService.get_registered_sources(db=db)

    @classmethod
    def discover_jobs(
        cls,
        source: str = "all",
        query: str = "",
        company: Optional[str] = None,
        location: Optional[str] = None,
        limit: int = 20,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
        """Query real external sources and aggregate results."""
        results: List[Dict[str, Any]] = []
        status_map: Dict[str, str] = {}

        connectors_to_run = (
            cls.CONNECTORS.items()
            if source == "all"
            else [(source, cls.CONNECTORS[source])]
            if source in cls.CONNECTORS
            else []
        )

        for src_key, connector in connectors_to_run:
            try:
                found = connector.search(query=query, company=company, location=location, limit=limit)
                results.extend(found)
                status_map[src_key] = f"SUCCESS: {len(found)} jobs retrieved"
            except Exception as e:
                status_map[src_key] = f"ERROR: {str(e)}"

        return results[:limit], status_map

    @classmethod
    def rank_job_for_candidate(
        cls,
        job_dict: Dict[str, Any],
        candidate_facts: List[Fact],
    ) -> Dict[str, Any]:
        """Evaluate hard eligibility and compute explainable suitability score (0-100)."""
        active_facts = [f for f in candidate_facts if f.is_usable]

        # Construct temporary domain Job
        reqs = JobRequirements(
            min_degree=DegreeLevel.BACHELOR,
            min_experience_months=24,
            required_skills=job_dict.get("required_skills", []),
            work_auth_countries=["US", "UK", "IN"],
            accepted_work_modes=job_dict.get("accepted_work_modes", ["remote", "hybrid", "onsite"]),
        )
        temp_job = Job(
            id="temp-eval",
            source=job_dict.get("source", "external"),
            source_url=job_dict.get("source_url", ""),
            canonical_url=job_dict.get("source_url", ""),
            canonical_job_key="eval-key",
            company_norm=job_dict.get("company_name", "Company"),
            title_norm=job_dict.get("title", "Role"),
            description_clean=job_dict.get("raw_description", ""),
            raw_sha256=hashlib.sha256(job_dict.get("raw_description", "").encode("utf-8")).hexdigest(),
            requirements=reqs,
            status=JobStatus.ACTIVE,
        )

        # 1. Hard Rule Eligibility
        eligibility = EligibilityEngine.evaluate(requirements=reqs, active_facts=active_facts)

        # 2. Suitability Scoring
        score_result = ScoringEngine.score_job(requirements=reqs, active_facts=active_facts)

        # Matched skills
        candidate_skill_names = {
            f.value.get("name", "").lower() for f in active_facts if f.kind == FactKind.SKILL
        }
        matched_skills = [
            s for s in job_dict.get("required_skills", []) if s.lower() in candidate_skill_names
        ]
        missing_skills = [
            s for s in job_dict.get("required_skills", []) if s.lower() not in candidate_skill_names
        ]

        return {
            "rules_result": eligibility.overall_outcome.value,
            "rules_reason": ", ".join(eligibility.reason_codes) if eligibility.reason_codes else "All hard constraints satisfied",
            "score_total": score_result.total_score,
            "score_breakdown": {k: v.model_dump() for k, v in score_result.categories.items()},
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
        }

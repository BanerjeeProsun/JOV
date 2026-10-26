"""Deep link generator for restricted proprietary job boards.

For job boards without usable public APIs (LinkedIn, Indeed, Naukri, Wellfound,
Internshala, Foundit), JOV.si provides deep links that open the board's own
search in a new tab with the candidate's active keyword and location filters.
"""

import urllib.parse
from typing import Any, Dict, List


RESTRICTED_BOARDS = [
    {
        "id": "linkedin",
        "name": "LinkedIn Jobs",
        "url_template": "https://www.linkedin.com/jobs/search/?keywords={query}&location={location}",
        "policy_status": "BA",
        "policy_reason": "No public job search API. Anti-scraping terms and active bot detection strictly forbid scraping.",
        "supported_alternatives": ["Direct URL/Text Import", "Deep Link Search"],
    },
    {
        "id": "indeed",
        "name": "Indeed",
        "url_template": "https://www.indeed.com/jobs?q={query}&l={location}",
        "policy_status": "BA",
        "policy_reason": "Partner-only API requiring enterprise licensing agreement. Scraping violates ToS and robots.txt.",
        "supported_alternatives": ["Direct URL/Text Import", "Deep Link Search"],
    },
    {
        "id": "naukri",
        "name": "Naukri",
        "url_template": "https://www.naukri.com/{query}-jobs-in-{location}",
        "policy_status": "BA",
        "policy_reason": "Proprietary Indian recruitment portal. No public posting API; active anti-bot systems.",
        "supported_alternatives": ["Direct URL/Text Import", "Deep Link Search"],
    },
    {
        "id": "wellfound",
        "name": "Wellfound (AngelList)",
        "url_template": "https://wellfound.com/jobs?role={query}&location={location}",
        "policy_status": "BA",
        "policy_reason": "Partner API access strictly restricted; anti-scraping enforced.",
        "supported_alternatives": ["Direct URL/Text Import", "Deep Link Search"],
    },
    {
        "id": "internshala",
        "name": "Internshala",
        "url_template": "https://internshala.com/internships/keywords-{query}/",
        "policy_status": "BA",
        "policy_reason": "Proprietary student/internship portal without public API.",
        "supported_alternatives": ["Direct URL/Text Import", "Deep Link Search"],
    },
    {
        "id": "foundit",
        "name": "Foundit (Monster)",
        "url_template": "https://www.foundit.in/srp/results?query={query}&locations={location}",
        "policy_status": "BA",
        "policy_reason": "No open public feed without commercial partner licensing.",
        "supported_alternatives": ["Direct URL/Text Import", "Deep Link Search"],
    },
]


class DeepLinksService:
    @classmethod
    def generate_links(cls, query: str = "", location: str = "") -> List[Dict[str, Any]]:
        q_clean = query.strip()
        loc_clean = location.strip()

        q_enc = urllib.parse.quote_plus(q_clean) if q_clean else "software-engineer"
        loc_enc = urllib.parse.quote_plus(loc_clean) if loc_clean else ""

        results = []
        for board in RESTRICTED_BOARDS:
            if board["id"] == "naukri":
                q_slug = urllib.parse.quote(q_clean.lower().replace(" ", "-")) if q_clean else "software-engineer"
                loc_slug = urllib.parse.quote(loc_clean.lower().replace(" ", "-")) if loc_clean else "india"
                target_url = f"https://www.naukri.com/{q_slug}-jobs-in-{loc_slug}"
            elif board["id"] == "internshala":
                q_slug = urllib.parse.quote(q_clean.lower().replace(" ", "-")) if q_clean else "software-development"
                target_url = f"https://internshala.com/internships/keywords-{q_slug}/"
            else:
                target_url = board["url_template"].format(query=q_enc, location=loc_enc)

            results.append({
                "id": board["id"],
                "name": board["name"],
                "url": target_url,
                "policy_status": board["policy_status"],
                "policy_reason": board["policy_reason"],
                "supported_alternatives": board["supported_alternatives"],
            })

        return results

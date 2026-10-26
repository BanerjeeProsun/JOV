# JOV.si — External Job Sources & Connectors Audit

Status Taxonomy:
- **FV**: Implemented and verified live with real listings
- **IU**: Implemented with contract fixtures, unverified live
- **PF**: Partially functional / hard-coded
- **MO**: Placeholder / Mock-only
- **BC**: Blocked: Credentials required
- **BA**: Blocked: Authorization / ToS restricted
- **NI**: Not implemented

---

## 1. ATS Public Job-Board Connectors

| Source / ATS | Endpoint Pattern | Auth Required | Status | Official Documentation & Policy Decision | Failure Modes & Limitations |
|---|---|---|---|---|---|
| **Greenhouse** | `https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true` | None (Public read) | **PF** | **Implement official API**. Documented public read API for jobs and offices. Supported for any valid company token. | 404 for invalid board slug; rate limits per IP (~50 req/min). |
| **Lever** | `https://api.lever.co/v0/postings/{company}?mode=json` | None (Public read) | **PF** | **Implement official API**. Documented public postings feed. Supported for valid company tokens. | Postings array empty or 404 on unconfigured token; rate limit per IP. |
| **Ashby** | `https://api.ashbyhq.com/posting-api/job-board/{name}` | None (Public read) | **NI** | **Implement official API**. Ashby provides public posting API for enabled job boards. | Board identifier must match Ashby company slug. |
| **SmartRecruiters** | `https://api.smartrecruiters.com/v1/companies/{companyIdentifier}/postings` | None (Public read) | **NI** | **Implement official API**. Public postings API returns JSON list of openings with location and department. | Pagination required (`limit`, `offset`). |
| **Workable** | `https://apply.workable.com/api/v1/widget/accounts/{account}` | None (Public read) | **NI** | **Implement official API**. Public widget endpoint returns active published vacancies. | Rate-limited by Cloudflare. |

---

## 2. Aggregator & Feed APIs

| Source / Aggregator | API Endpoint / Shape | Key Required | Status | Official Documentation & Policy Decision | Attribution & Terms |
|---|---|---|---|---|---|
| **Jobicy** | `https://jobicy.com/api/v2/remote-jobs?count=50` | None (Public free tier) | **PF** | **Implement official API**. Clean JSON feed of remote engineering jobs across US, UK, EU, India, APAC. | Free tier capped at 50 jobs per call; remote only. |
| **Adzuna** | `https://api.adzuna.com/v1/api/jobs/{country}/search/1` | App ID + Key | **BC** | **Implement official API (BC)**. Multi-country coverage (US, GB, IN, CA, AU, DE, FR). Connects when `ADZUNA_APP_ID` & `ADZUNA_API_KEY` are configured. | Requires registered API credentials. |
| **Arbeitnow** | `https://www.arbeitnow.com/api/job-board-api` | None (Public feed) | **NI** | **Implement official API**. Free open remote/European tech job board API with structured tags and locations. | Limited volume compared to global aggregators. |
| **Remotive** | `https://remotive.com/api/remote-jobs` | None (Public feed) | **NI** | **Implement official API**. Open remote jobs API with categories, locations, and salary data. | Rate limits on aggressive polling. |
| **USAJOBS** | `https://data.usajobs.gov/api/search` | Auth Key + User-Agent | **BC** | **Implement official API (BC)**. US Federal government employment opportunities with structured geo coordinates. | US only; requires developer account key. |

---

## 3. Restricted & Proprietary Job Boards (No Usable Public API)

| Board | Status | Reason & Policy Clearance | Supported Alternatives Provided in JOV.si |
|---|---|---|---|
| **LinkedIn Jobs** | **BA** | No public job search API. Anti-scraping terms and active bot detection strictly forbid scraping. | 1. Direct Job Import (Paste job URL or description)<br>2. Deep Link Search: opens `linkedin.com/jobs/search?keywords=...&location=...` |
| **Indeed** | **BA** | Partner-only API requiring enterprise agreement; scraping violates ToS and robots.txt. | 1. Direct Job Import<br>2. Deep Link Search: opens `indeed.com/jobs?q=...&l=...` |
| **Naukri** | **BA** | Proprietary Indian recruitment portal. No public posting API; active anti-bot systems. | 1. Direct Job Import<br>2. Deep Link Search: opens `naukri.com/{role}-jobs-in-{city}` |
| **Foundit (Monster)** | **BA** | No permitted open public feed without partner licensing. | 1. Direct Job Import<br>2. Deep Link Search |
| **Internshala** | **BA** | Proprietary student/internship portal without public API. | 1. Direct Job Import<br>2. Deep Link Search |
| **Wellfound (AngelList)** | **BA** | Partner API restricted; anti-scraping enforced. | 1. Direct Job Import<br>2. Deep Link Search |
| **Cutshort / Instahyre** | **BA** | Closed AI-matching platforms requiring candidate login. | 1. Direct Job Import<br>2. Deep Link Search |

---

## 4. Source Registry Architecture (`job_sources` table)

Instead of hard-coding company board slugs in Python files, JOV.si establishes a database-backed **Source Registry**:
- Schema:
  - `id`: UUID
  - `provider`: `greenhouse`, `lever`, `ashby`, `smartrecruiters`, `jobicy`, `adzuna`, `arbeitnow`, `manual`
  - `employer_name`: e.g. "Cloudflare", "Figma", "Palantir"
  - `board_identifier`: Slug used in API URL (e.g. `cloudflare`)
  - `status`: `untested`, `verified_active`, `failing`, `empty`
  - `last_probed_at`: Timestamp of latest connectivity check
  - `last_job_count`: Count of active jobs retrieved on last fetch
  - `last_error`: Sanitized error message if failed
- Dynamic Prober: When adding an employer, JOV.si probes the candidate slug across supported ATS providers (Greenhouse, Lever, Ashby, SmartRecruiters) and automatically configures the responding endpoint.

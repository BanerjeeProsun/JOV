# Job Sources, Discovery, Location, and Filters Audit

## Connector inventory

| Source | Implementation | Audit evidence | Primary status |
|---|---|---|---|
| Greenhouse | Official boards API, defaults Cloudflare/Figma/Stripe/Canonical | `job_discovery.py:41-99`; live health HTTP 200; hard-coded boards | IU/PF |
| Lever | Official postings API, defaults Palantir/Lever Demo | `job_discovery.py:102-158`; live health HTTP 200 | IU/PF |
| Ashby | Official posting API, defaults Ramp/Linear | `job_discovery.py:406-461`; mocked adapter tests + live health | IU |
| SmartRecruiters | Official company postings API, defaults Visa/McDonalds | `job_discovery.py:464-519`; mocked adapter tests + live health | IU |
| Jobicy | Public remote feed | `job_discovery.py:161-208`; live HTTP health | IU; failure swallowed |
| Arbeitnow | Public European/remote feed | `job_discovery.py:211-274`; live HTTP health | IU; failure swallowed |
| Remotive | Public remote feed | `job_discovery.py:351-403`; live HTTP health | IU; failure swallowed |
| Adzuna | API client | `job_discovery.py:277-348`; live health UNCONFIGURED | BC |
| Generic URL/JSON-LD | SSRF-safe generic page importer | `manual_import.py:248-347`; unit/integration tests | IU |
| Restricted boards | Deep-link/manual handoff, not scraping | `manual_import.py:40-75`, `deep_links.py` | IU |
| Workable/other ATS | No adapter found | repository search | NI |

HTTP health is not live job-ingestion verification: `check_all_sources_health` labels a source HEALTHY on status 200 without validating response schema or importing a record (`job_discovery.py:750-776`).

## Source-registry mismatch

`SourceRegistryService` stores/probes employers in `JobSourceDB` (`job_discovery.py:540-731`), but `JobDiscoveryService.discover_jobs` iterates the static `CONNECTORS` dictionary (`job_discovery.py:853-869`). Registered employer rows do not drive discovery. Source-management mutation endpoints are unauthenticated (`jobs.py:828-883`). Status: **PF**.

## Filter trace

| Requested filter | UI | API/backend | Result |
|---|---|---|---|
| Title/keywords | `JobDiscoveryScreen.tsx:174-217` | `jobs.py:444-453` title/company/description `ILIKE` | IU; no stemming/role-family semantics |
| Country | UI multi-select | `jobs.py:463-475` JobLocationDB | IU in facet tests |
| State/region | API supports `admin1`; UI has no visible state control in inspected screen | `jobs.py:476-480` | PF |
| City | UI multi-select | `jobs.py:481-489` | IU in facet tests; city IDs are not obvious to users |
| Remote/hybrid/onsite | UI work-mode toggles | `jobs.py:491-499` | IU for indexed jobs; live connector output is less normalized |
| Remote country scope | API supports `remote_scope`; UI state type omits it | `jobs.py:496-500`, `JobDiscoveryScreen.tsx:35-45` | PF |
| Minimum score | UI slider | EvaluationDB subquery only if `candidate_id` plus score supplied | PF; unevaluated jobs have unknown scores |
| Source | API/client supports source arrays; UI source controls are not surfaced in inspected filter rail | `jobs.py:455-460` | PF |
| Employment type, salary, compensation | no UI/API query implementation found | schema/model lacks complete fields | NI |
| Eligibility facets, sponsorship, degree, certs | eligibility engine exists, search filter does not expose them | `eligibility.py`, `jobs.py:423-746` | PF |
| Freshness/expiry/deadline | `deadline_at` exists; search filters only `status=ACTIVE` | `jobs.py:441-442` | PF; no expiry job/scheduler |

## Confirmed geography defect

The UI calls `api.discoverJobs` with `source`, `query`, `candidate_id`, and `limit`, but not `location`, countries, cities, or work mode (`JobDiscoveryScreen.tsx:269-280`). Therefore a user-selected geography controls `/jobs/search` only; “Discover Live Jobs” can fetch unrelated regions. This is the likely root cause of the previously observed irrelevant-country listings.

## Data integrity and policy

The connectors preserve `source`/`source_url`, sanitize descriptions, and use SSRF validation for generic URL import. Restricted board handling directs users to manual/deep-link workflows rather than bypassing anti-bot controls. The remaining risks are hard-coded employer coverage, silent connector exceptions, absence of freshness/deadline retrieval, and public source-registry mutation.

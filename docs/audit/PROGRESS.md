# JOV.si — Recovery Progress Tracker

**Active Baseline Git Tag**: `pre-recovery` (Commit: `cf916c3`)

---

## Milestone Status Overview

| Milestone | Title | Status | Tests Passed | Commit |
|---|---|---|---|---|
| **M0** | Recon, Inventory, Recovery Plan | **COMPLETED** | 115 / 115 | `1b98d5c` |
| **M1** | Strict Authentication, Identity & Isolation | **COMPLETED** | 124 / 124 | `753f0cf` |
| **M2** | Configuration, Secrets Hygiene, LLM Provider | **COMPLETED** | 133 / 133 | `7732d7d` |
| **M3** | Zombie-Code Removal & Mock Isolation | **COMPLETED** | 133 / 133 | `b7feb30` |
| **M4** | Master-Resume Ingestion & Profile Verification | **COMPLETED** | 133 / 133 | `d04e4ab` |
| **M5** | Source Registry & Real ATS Connectors | **COMPLETED** | 137 / 137 | `62bd27d` |
| **M6** | Normalized Schema, Geo Dataset & Parser | **COMPLETED** | 143 / 143 | `e9b4d4b` |
| **M7** | Search & Filters: Facets, URL State & UI Wiring | **COMPLETED** | 150 / 150 | `e38e8d4` |
| **M8** | Aggregator/Feed Connectors & Manual Import | **COMPLETED** | 171 / 171 | `c396c3d` |
| **M9** | Eligibility Gates & Explainable Scoring | **COMPLETED** | 181 / 181 | `d536629` |
| **M10** | Job-Specific Resume Generation & Grounding | **IN PROGRESS** | - | - |
| **M11** | Cover Letters with Provenance Grounding | **PENDING** | - | - |
| **M12** | Application Planning & Manual Handoff | **PENDING** | - | - |
| **M13** | External Authenticated-Session Workflow | **PENDING** | - | - |
| **M14** | Validation, Approval & Submission Pipeline | **PENDING** | - | - |
| **M15** | Dashboard & Settings Integration (Honest Greetings) | **PENDING** | - | - |
| **M16** | Security Hardening Pass | **PENDING** | - | - |
| **M17** | End-to-End Acceptance & Final Report | **PENDING** | - | - |

---

## Current Session Details

### Milestone 0: Recon, Inventory, Recovery Plan
- **Scope**: Perform repository recon, execute existing test suites, audit all modules/routes/models/screens/LLM/auth/connectors, identify zombie code and architectural gaps, write audit deliverables in `docs/audit/`.
- **Existing Modules to Reuse**:
  - `src/jovsi/domain/`: Pure domain models, state machine, eligibility, scoring, 15-point validation gate, factual consistency validator.
  - `src/jovsi/adapters/`: SQLite immutability triggers, sanitizer, Playwright mock portal submitter.
  - `mock_portal/`: Local hostile portal test harness.
  - `web/`: React 19 UI kit and screens.
- **Files Created / Changed**:
  - `docs/audit/RUNBOOK.md`
  - `docs/audit/DECISIONS.md`
  - `docs/audit/PROGRESS.md`
  - `docs/audit/INVENTORY.md`
  - `docs/audit/UI_WIRING_MATRIX.md`
  - `docs/audit/ZOMBIE_CODE.md`
  - `docs/audit/LLM_AUDIT.md`
  - `docs/audit/AUTH_AUDIT.md`
  - `docs/audit/AUTHZ_MATRIX.md`
  - `docs/audit/SOURCES_AUDIT.md`
  - `docs/audit/RECOVERY_PLAN.md`
- **Verified Command Results**:
  - Pytest full suite: `.\.venv\Scripts\pytest.exe -v` -> 115 passed, 409 warnings in 25.05s.
  - Web build: `cd web; npm run build` -> `tsc -b && vite build` succeeded in 1.34s.
  - Web lint: `cd web; npm run lint` -> 25 warnings, 0 errors.
- **Definition of Done for M0**: All 11 audit documents authored with real file citations, line ranges, test outputs, and clear recovery actions.

---

### Milestone 1: Strict Authentication, Identity & Account Isolation
- **Scope**: Implement user accounts, session lifecycle, password security, endpoint ownership checks, two-account isolation, and persisted display-name greetings.
- **Implemented Modules**:
  - `src/jovsi/adapters/db/models.py`: Added `UserDB`, `UserSessionDB`, `PasswordResetTokenDB`, `EmailVerificationTokenDB`, `UserSettingsDB`. Added `user_id` FK to `CandidateDB`.
  - `src/jovsi/adapters/db/session.py`: Auto-migration for `user_id` on SQLite startup.
  - `src/jovsi/services/auth.py`: PBKDF2-HMAC-SHA256 (600,000 iterations, 16-byte random salt, constant-time verification). 256-bit secure session tokens (SHA-256 hashed in DB), 24h idle timeout, 30d absolute timeout, token revocation on logout/password change. Sliding-window rate limiter on auth endpoints. Single-use reset and verification tokens.
  - `src/jovsi/api/dependencies.py`: `get_session_token_from_request`, `get_current_user`, `get_optional_current_user`.
  - `src/jovsi/api/routers/auth.py`: `/register`, `/login`, `/logout`, `/me`, `/profile`, `/change-password`, `/forgot-password`, `/reset-password`, `/verify-email`.
  - Endpoint Access Control:
    - `src/jovsi/api/routers/candidates.py`: Strict ownership enforcement on candidates and facts.
    - `src/jovsi/api/routers/applications.py`: Strict ownership enforcement on applications and document downloads.
    - `src/jovsi/api/routers/metrics.py`: Metrics summary query scoped to user's candidates.
    - `src/jovsi/api/routers/settings.py`: Settings persisted per user in `UserSettingsDB`.
    - `src/jovsi/api/routers/jobs.py`: Candidate ownership verified on job discovery.
  - Frontend Updates:
    - `web/src/types/index.ts`: User interface added.
    - `web/src/api/client.ts`: Auth endpoints implemented, hard-coded fallback removed.
    - `web/src/context/AuthContext.tsx`: Global auth context and session lifecycle.
    - `web/src/components/auth/AuthModal.tsx`: Login, register, and reset modal.
    - `web/src/screens/OverviewScreen.tsx`: Greeting contract verified:
      - Authenticated with display name: `Welcome back, {display_name}.`
      - Authenticated without display name: `Welcome back.`
      - Unauthenticated: `Your next role, in focus.`
    - `web/src/components/layout/FloatingNav.tsx`: Account pill and sign-in trigger.
    - `web/src/screens/SettingsScreen.tsx`: Account & Identity tab.
- **Verified Command Results**:
  - `.\.venv\Scripts\pytest.exe -v` -> 124 passed, 0 failed in 27.96s (115 baseline + 9 new security tests).
  - `cd web; npm run build` -> `tsc -b && vite build` succeeded in 1.11s.
  - `cd web; npm run lint` -> 28 warnings, 0 errors.
- **Definition of Done for M1**: Complete end-to-end auth, two-account isolation tests pass, display-name greeting contract fulfilled.

---

### Milestone 2: Configuration, Secrets Hygiene & LLM Provider Abstraction
- **Scope**: Enforce strict secrets hygiene (`.gitignore`, `.env.example`, automated git scanner), create secret-safe `LLMProvider` abstraction with Google Gemini (`gemini-2.5-flash`) integration and deterministic heuristic fallback, implement `/api/v1/health/llm`.
- **Implemented Modules**:
  - `.gitignore`: Added `.env`, `.env.*`, `!.env.example`.
  - `.env.example`: Full, safe documentation of all runtime variables.
  - `src/jovsi/config.py`: Added `LLM_MODEL`, `GEMINI_API_KEY`, and `effective_llm_api_key`.
  - `src/jovsi/services/llm.py`:
    - `LLMProvider` interface defining `generate_text`, `generate_structured`, `health_check`.
    - `GeminiLLMProvider`: Targets Google Gemini REST API (`https://generativelanguage.googleapis.com/v1beta`), passes API key strictly in `x-goog-api-key` header, redacts secrets from `__repr__` and logs, enforces 15s timeout with 3 exponential backoff retries on transient errors (429, 500, 503).
    - `FallbackLLMProvider`: Deterministic heuristic generator for text completions and Pydantic schema-conforming structured output (tagged `source: "fallback"`).
    - `HybridLLMService`: Transparent fallback router executing Gemini when enabled and configured, and seamlessly falling back on API failures.
  - `src/jovsi/api/main.py`: Exposed `GET /api/v1/health/llm` reporting provider health without credential leakage.
- **Tests Implemented & Verified**:
  - `tests/unit/test_llm_provider.py` (6 tests): Key masking, unconfigured mode, fallback conformance, mocked Gemini response parsing, hybrid error resilience, health endpoint.
  - `tests/security/test_secret_leakage.py` (3 tests): Scans all git-tracked files, git ignore rules for `.env`, and git history diffs for secrets.
- **Verified Command Results**:
  - `.\.venv\Scripts\pytest.exe -v` -> 133 passed, 0 failed in 34.04s.
  - `cd web; npm run build` -> `tsc -b && vite build` succeeded in 1.21s.
- **Definition of Done for M2**: Secrets hygiene verified via tests, Gemini provider implemented with deterministic fallback, zero secret leakage in health checks or logs.

---

### Milestone 3: Zombie-Code Removal & Mock Isolation
- **Scope**: Remove proved dead and redundant React components and obsolete re-exports, verify mock portal isolation, and ensure all tests continue passing.
- **Removed Dead Components**:
  - `web/src/components/Button.tsx`: Redundant re-export of `web/src/components/ui/Button.tsx`.
  - `web/src/components/CommandPalette.tsx`: Redundant re-export; `web/src/App.tsx` updated to import directly from `web/src/components/ui/CommandPalette.tsx`.
  - `web/src/components/Navbar.tsx`: Dead fixed navbar component superseded by `FloatingNav.tsx`.
  - `web/src/components/Card.tsx`: Dead boxed card component superseded by unboxed design system.
  - `web/src/components/AmbientBackdrop.tsx`: Dead canvas/SVG prototype.
  - `web/src/components/BrandLogo.tsx`: Dead legacy logo superseded by `JLogo.tsx` and `Wordmark.tsx`.
- **Mock Portal Isolation**:
  - Verified `mock_portal` code is completely unimported by `src/` core domain, services, and adapters.
  - Mock portal remains strictly isolated to integration tests and sandbox testing harnesses.
- **Verified Command Results**:
  - `.\.venv\Scripts\pytest.exe -v` -> 133 passed, 0 failed in 34.78s.
  - `cd web; npm run build` -> `tsc -b && vite build` succeeded in 894ms.
  - `cd web; npm run lint` -> 28 warnings, 0 errors.
- **Definition of Done for M3**: Dead components safely deleted with zero test breakage or frontend compile issues.

---

### Milestone 4: Master-Resume Ingestion & Profile Verification
- **Scope**: Verify end-to-end master-resume upload flow (PDF/DOCX/TXT), provenance tracking with document SHA-256 hash, proposed fact state machine, and wire the UI confirmation review banner and inline fact verification controls.
- **Implemented & Verified**:
  - `src/jovsi/services/resume_parser.py`: Verified `MasterResumeParser` handles PDF, DOCX, and TXT with magic verification, scanned PDF rejection (empty text check), entity extraction (contact, education, experience, projects, skills), and proposed fact generation with source document SHA-256 links.
  - `web/src/screens/CandidateProfileScreen.tsx`:
    - Wired `handleConfirmFact(factId)` to `api.confirmFact`.
    - Wired `handleConfirmAllFacts()` to `api.confirmAllFacts`.
    - Added prominent review banner when proposed facts exist with a single-click "Confirm All" verification button.
    - Added inline verification triggers on individual proposed facts (experience, education, and skills) with visual status indication (`ACTIVE` vs `PROPOSED`).
  - `docs/audit/DECISIONS.md`: Recorded Decision 007 (Master-Resume Fact Extraction & Provenance Workflow Verification).
- **Verified Command Results**:
  - `.\.venv\Scripts\pytest.exe -v` -> 133 passed, 0 failed in 35.50s.
  - `cd web; npm run build` -> `tsc -b && vite build` succeeded in 892ms.
  - `cd web; npm run lint` -> 28 warnings, 0 errors.
- **Definition of Done for M4**: Upload, extraction, provenance grounding, and candidate fact confirmation fully verified end-to-end across backend and frontend.

---

### Milestone 5: Source Registry & Real ATS Connectors
- **Scope**: Replace hardcoded/mock job sources with real database-backed registry (`JobSourceDB`), dynamic prober, real Ashby and SmartRecruiters connectors alongside Greenhouse, default employer seeds, API endpoints, and live UI indicators.
- **Implemented & Verified**:
  - `src/jovsi/adapters/db/models.py`: Added `JobSourceDB` model (`job_sources` table) tracking provider, employer, slug, status (`verified_active`, `failing`, `empty`, `unprobed`), posting counts, timestamps, error messages.
  - `src/jovsi/services/job_discovery.py`:
    - Implemented `AshbyConnector` using Ashby public job board API (`https://api.ashbyhq.com/posting-api/job-board/{board_name}`).
    - Implemented `SmartRecruitersConnector` using SmartRecruiters postings API (`https://api.smartrecruiters.com/v1/companies/{company}/postings`).
    - Implemented `SourceRegistryService` with dynamic probing (`probe_source`), DB sync, and aggregated status reporting.
  - `src/jovsi/adapters/db/session.py`: Auto-seeds default known employers (Cloudflare, Figma, Stripe, Canonical, Palantir, Ramp, Linear, Visa, McDonald's) on DB init.
  - `src/jovsi/api/routers/jobs.py`: Added `/api/v1/jobs/sources` (aggregates DB sources), `/api/v1/jobs/sources/employers`, and `/api/v1/jobs/sources/{id}/probe`.
  - `web/src/screens/JobDiscoveryScreen.tsx`: Wired live feed indicator pills displaying active employers and live posting counts per provider.
  - `tests/integration/test_source_registry.py`: 4 integration tests verifying ATS connectors and dynamic registry probing.
  - `docs/audit/DECISIONS.md`: Recorded Decision 008 (Real ATS Connectors & Dynamic Source Registry Architecture).
- **Verified Command Results**:
  - `.\.venv\Scripts\pytest.exe -v` -> 137 passed, 0 failed in 32.08s.
  - `cd web; npm run build` -> `tsc -b && vite build` succeeded in 1.05s.
- **Definition of Done for M5**: Multi-ATS connector architecture, real DB source registry, dynamic prober, and live UI status indicators operational.

---

### Milestone 6: Normalized Schema, Geo Dataset & Location Parser
- **Scope**: Extend schema with geographic tables (`geo_countries`, `geo_admin1`, `geo_cities`, `geo_aliases`, `job_locations`), compile comprehensive offline reference dataset covering 249 ISO countries, 98 administrative regions, 517+ global tech-hiring cities, and 858 aliases, and build a deterministic, high-precision offline `LocationParser` with >= 95% precision on real ATS strings.
- **Implemented & Verified**:
  - `src/jovsi/adapters/db/models.py`: Added `GeoCountryDB`, `GeoAdmin1DB`, `GeoCityDB`, `GeoAliasDB`, and `JobLocationDB`.
  - `src/jovsi/services/geo_data.py`: Reference dataset with 249 ISO countries, 98 admin1 states/provinces (US, CA, IN, DE, GB, AU), 517+ unique global tech cities, and 858 canonical aliases with priority hierarchy (`city > admin1 > country`).
  - `src/jovsi/services/geo.py`:
    - `ParsedLocation` schema (raw, work_mode, remote_scope, country, admin1, city, confidence).
    - `LocationParser`: Trie/regex tokenizer, postal code cleaner, work mode/remote scope classifier, multi-location splitter, synonym deduplicator.
    - `seed_geo_database()`: Idempotent SQLite seeder.
  - `src/jovsi/adapters/db/session.py`: Automatically calls `seed_geo_database(conn)` during `init_db()`.
  - `src/jovsi/api/routers/jobs.py`: Wired `JobLocationDB` generation on `import_job` and `discover_jobs`.
  - `tests/unit/test_geo_parser.py`: 6 tests verifying dataset integrity, SQLite seeding, multi-location splitting, edge case robustness, DB linking, and 100.00% precision on the 109 real-world ATS benchmark suite.
  - `docs/audit/DECISIONS.md`: Recorded Decision 009.
- **Verified Command Results**:
  - `.\.venv\Scripts\pytest.exe -v` -> 143 passed, 0 failed in 32.62s.
  - `cd web; npm run build` -> `tsc -b && vite build` succeeded in 1.06s.
- **Definition of Done for M6**: Complete normalized geo schema, offline reference dataset, 100% benchmark precision parser, and database seeding verified.

---

### Milestone 7: Search & Filters: Facets, URL State & UI Wiring
- **Scope**: Multi-dimensional job search API (`GET /api/v1/jobs/search`) with server-side faceted aggregation across countries, states, cities, work modes, and sources; location autocomplete endpoint (`GET /api/v1/jobs/facets/locations`); frontend search controls, multi-select popover filters, suitability score slider, active filter chips, unboxed empty state, and bidirectional URL state synchronization (`window.location.search` & `popstate`).
- **Implemented & Verified**:
  - `src/jovsi/api/routers/jobs.py`:
    - Added `GET /api/v1/jobs/search` with support for `q`, `country` (multi), `admin1` (multi), `city` (multi), `work_mode` (multi), `remote_scope` (multi), `min_score`, `source` (multi), `sort`, `page`, `page_size`, `candidate_id`.
    - Computed exact facets for countries, states, cities, work modes, and sources.
    - Added `GET /api/v1/jobs/facets/locations` for hierarchical location autocomplete.
  - `web/src/types/index.ts`: Added `JobSearchItem`, `JobLocation`, `CountryFacet`, `Admin1Facet`, `CityFacet`, `KeyCountFacet`, `JobSearchFacets`, `JobSearchResponse`, and `LocationHierarchyResponse`.
  - `web/src/api/client.ts`: Added `searchJobs` and `getLocationFacets` methods.
  - `web/src/screens/JobDiscoveryScreen.tsx`:
    - Connected debounced keyword search input.
    - Added Country and City multi-select popover filters with live counts and search.
    - Added Work mode pill toggles (`Remote`, `Hybrid`, `On-site`) displaying live facet counts.
    - Added Suitability score floor range slider (`≥ 0` to `95`).
    - Added Active filter chips bar with single-click remove per chip and "Clear all" button.
    - Added actionable empty state when 0 results match with reset guidance.
    - Added bidirectional URL state synchronization (`readUrlFilters`, `writeUrlFilters`, `popstate` history navigation).
  - `tests/integration/test_job_search_facets.py`: 7 integration tests verifying exact facet counts, multi-country union, country+city intersection, remote filtering, work mode + score combinations, pagination/sorting, and location autocomplete.
  - `docs/audit/DECISIONS.md`: Recorded Decision 010.
- **Verified Command Results**:
  - `.\.venv\Scripts\pytest.exe -v` -> 150 passed, 0 failed in 34.03s.
  - `cd web; npm run build` -> `tsc -b && vite build` succeeded in 1.06s.
- **Definition of Done for M7**: Server-side faceted aggregation, multi-dimensional search engine, frontend filter wiring, and URL state synchronization fully verified.

---

### Milestone 8: Aggregator/Feed Connectors & Manual Import
- **Scope**:
  - Implement and verify Aggregator Connectors:
    - `JobicyConnector`: Public remote tech jobs feed with rate-limit resilience and `LocationParser` integration.
    - `ArbeitnowConnector`: Official public European & remote tech jobs feed.
    - `AdzunaConnector`: Multi-country aggregator API with graceful credential handling (`UNCONFIGURED` / `BLOCKED: CREDENTIALS` status when missing keys, active search when configured).
    - `RemotiveConnector`: Open remote jobs feed.
  - SSRF-Safe Fetcher (`src/jovsi/adapters/ssrf.py`):
    - Strict validation against private IPs (`10/8, 172.16/12, 192.168/16, 127/8, 169.254/16, ::1, fc00::/7`), link-local, cloud metadata (`169.254.169.254`, `metadata.google.internal`), redirect hops validation, response size capping, and scheme restrictions.
  - Manual Import Engine & Deep Link Helper (`src/jovsi/services/manual_import.py`):
    - URL Import (`POST /api/v1/jobs/import/url`): Auto-detects ATS endpoints (Greenhouse, Lever, Ashby, SmartRecruiters) and extracts structured data directly; parses schema.org `JobPosting` JSON-LD / OpenGraph for generic pages; returns explicit guidance for restricted anti-scraping platforms (LinkedIn, Indeed, Naukri).
    - Text Import (`POST /api/v1/jobs/import`): Ingests user-pasted job postings with sanitization, location parsing, and deduplication.
    - Deep Links (`GET /api/v1/jobs/deep-links`): Generates search links for restricted platforms (LinkedIn, Indeed, Naukri, Wellfound) preserving search keywords and location.
    - Connector Health Telemetry (`GET /api/v1/jobs/sources/health`): Probes all registered connectors and returns real latency, status (`HEALTHY`, `DEGRADED`, `UNCONFIGURED`, `DOWN`), and error details.
  - UI Integration:
    - Update `JobDiscoveryScreen.tsx` import dialog to support URL auto-fetch and deep-links for restricted boards.
    - Update `SettingsScreen.tsx` with a Sources & Registry tab showing live connector telemetry and employer source manager.
  - Tests:
    - `tests/unit/test_ssrf_fetcher.py`: SSRF validation and attack vector tests.
    - `tests/unit/test_aggregator_connectors.py`: Feed connectors contract tests with recorded fixtures.
    - `tests/integration/test_manual_import_and_health.py`: URL import, deep links, and health endpoints.
- **Verified Command Results**:
  - `.\.venv\Scripts\pytest.exe -v` -> 171 passed, 0 failed in 51.75s.
  - `cd web; npm run build` -> `tsc -b && vite build` succeeded in 2.31s.
- **Definition of Done for M8**: SSRF-safe fetcher, public feed connectors, manual URL/paste import engine, deep-links generator, and connector health telemetry fully verified.

---

### Milestone 9: Eligibility Gates & Explainable Scoring
- **Scope**:
  - Separate hard eligibility gates from soft scoring:
    - Hard constraints: degree level, degree field, graduation year window, work authorization countries, mandatory certifications, mandatory skills, location/remote eligibility, application deadline.
    - Hard gate outcome: `PASS`, `FAIL`, or `NEEDS_REVIEW` (when mandatory requirement is unstated in candidate facts). Unknown mandatory requirements never auto-pass.
    - Soft scoring (0–100): skills overlap (required vs preferred), experience fit (months vs required), role similarity, recency.
  - Return explainable breakdown with human-readable reasons (`matched_skills`, `missing_skills`, `disqualifying_reasons`, `uncertain_reasons`).
  - Wire scoring and eligibility into `POST /api/v1/applications/{id}/evaluate` and `EvaluationDB`.
  - Frontend integration:
    - Display eligibility gate badge (`PASS`, `Needs Review`, `Disqualified`) and explainable score card on application items.
    - Render matched vs missing skills chips, disqualification reasons, and uncertainty verification callouts.
    - Interactive 100-point category breakdown accordion (Skills, Experience, Education, Role, Location).
- **Verified Command Results**:
  - `.\.venv\Scripts\pytest.exe -v` -> 181 passed, 0 failed in 34.73s.
  - `cd web; npm run build` -> `tsc -b && vite build` succeeded in 1.47s.
- **Definition of Done for M9**: Strict separation of hard constraints from soft scoring, unknown mandatory requirements yielding `NEEDS_REVIEW`/`UNCERTAIN`, 100-point soft score model, state machine routing (`FAIL` -> `REJECTED`, `UNCERTAIN` -> `AWAITING_USER_INPUT`, `PASS` -> `SHORTLISTED`/`BELOW_THRESHOLD`), and UI explainable breakdowns fully verified.

---

### Milestone 10: Job-Specific Resume Generation & Grounding Validator
- **Scope**:
  - Implement Job-Specific Resume Generator:
    - Synthesizes tailored resumes from verified active facts only (`Fact.is_usable`).
    - Uses Gemini LLM structured generation when configured, deterministic provenance-backed fallback selector when offline/unconfigured.
    - Generates cryptographic SHA-256 content hashes of the generated resume and PDF rendering.
  - Grounding Validator (`FactualConsistencyValidator`):
    - Rigorous reverse verification: every bullet, claim, company, degree, and skill in the generated resume must have a 1:1 trace to an active verified `FactDB` record.
    - Prevents hallucinated metrics, unearned skills, and fabricated experience.
    - Rejects any generated resume with untraceable claims and records audit violation.
  - PDF/DOCX Artifact Export & Version History:
    - Generates downloadable PDF/DOCX artifacts stored securely.
    - Links generated resume to application record (`ApplicationDB.current_resume_id`).
    - Enforces transition `SHORTLISTED` -> `RESUME_GENERATED` (Guard #10: verified resume & PDF stored).




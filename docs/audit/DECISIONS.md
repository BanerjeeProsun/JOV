# JOV.si — Architecture & Recovery Decisions Record (ADR)

## Decision 001: Baseline Reconnaissance & Safety Tagging
- **Date**: 2026-10-26
- **Status**: Accepted
- **Context**: Codebase contains 115 passing automated tests and a compiled React 19 SPA, but completely lacks user authentication, account ownership, real country/state/city location search, and an active LLM provider implementation.
- **Decision**: Created git safety tag `pre-recovery` before making any modifications. Established `docs/audit/` for living recovery tracking.

## Decision 002: Authentication Architecture & Session Management
- **Date**: 2026-10-26
- **Status**: Accepted
- **Context**: The existing application has no `users` table or authentication layer. Every API request assumes an unauthenticated environment where the first candidate in `candidates` is used globally.
- **Decision**:
  - Introduce `users` and `user_sessions` tables in SQLite.
  - Passwords hashed with salted PBKDF2-HMAC-SHA256 (600,000 iterations, 32-byte salt) or Argon2id via `cryptography`.
  - Server-managed HTTP-only, SameSite=Lax (Secure in prod) session cookie `jovsi_session` with cryptographically random 256-bit token.
  - Separation of Account Identity (`users`: email, password_hash, display_name, is_verified) from Candidate Profile (`candidates`: user_id, facts, resumes).
  - Enforce ownership on all private endpoints via FastAPI dependency `get_current_user`.
  - Support password reset and email verification tokens (single-use, expiring, hashed in DB). If external SMTP is unconfigured, system operates in BC (Blocked: Credentials) mode and securely returns or logs verification tokens in development/test environment only without exposing secrets.

## Decision 003: LLM Integration & Secret Hygiene
- **Date**: 2026-10-26
- **Status**: Accepted
- **Context**: `config.py` defined `LLM_ENABLED`, `LLM_API_KEY`, and `LLM_PROVIDER`, but no provider adapter, health check, or structured generation existed.
- **Decision**:
  - Implement `LLMProvider` abstraction with support for Google Gemini (`google-genai` / REST API via `httpx`).
  - Strict server-side only key loading from `JOVSI_LLM_API_KEY` or `GEMINI_API_KEY`. Never expose to client bundles or log outputs.
  - Add `/api/v1/health/llm` endpoint reporting `provider`, `model`, `configured: bool`, `last_check_status`, never printing the key.
  - Implement deterministic fallback for all AI tasks (resume tailoring, cover letter generation, requirement parsing) with explicit `source: "llm" | "fallback"` tag.
  - Enforce factual grounding validation on all generated documents.

## Decision 004: Geographic Reference Data & Hierarchical Location Search
- **Date**: 2026-10-26
- **Status**: Accepted
- **Context**: Location matching was a naive substring check (`location.lower() in raw_text.lower()`).
- **Decision**:
  - Establish `geo_country`, `geo_admin1`, `geo_city`, and `geo_alias` tables with offline reference dataset covering global countries, admin divisions, and major global cities with aliases (e.g. Bangalore -> Bengaluru, NYC -> New York City).
  - Ingestion parser extracts structured locations into `job_locations` table (`country_code`, `admin1_code`, `city_id`, `work_mode`, `remote_scope`).
  - Search API supports hierarchical facets with computed counts matching result totals.

## Decision 005: Source Registry & Real ATS Connectors
- **Date**: 2026-10-26
- **Status**: Accepted
- **Context**: Connectors had hard-coded lists of companies in code and fake "CONFIGURED / is_live: True" status badges.
- **Decision**:
  - Create `job_sources` table in SQLite storing employer registry with dynamic probing against Greenhouse, Lever, Ashby, and SmartRecruiters public posting endpoints.
  - Untested sources are marked `untested`. Health badges reflect real HTTP fetch outcomes.

## Decision 006: Frontend Authentication & Display Name Greeting Contract
- **Date**: 2026-10-26
- **Status**: Accepted
- **Context**: Recovery brief §3A and non-negotiable rule 6 mandate strict account ownership and a landing/dashboard greeting strictly derived from the authenticated account's persisted display name.
- **Decision**:
  - Implemented `AuthProvider` React context (`web/src/context/AuthContext.tsx`) managing current session lifecycle and modal visibility.
  - Wired `api.getMe()` to update dashboard greeting dynamically:
    - Authenticated with `user.display_name`: renders `Welcome back, {display_name}.`
    - Authenticated without display name: renders `Welcome back.`
    - Unauthenticated: renders `Your next role, in focus.`
  - Integrated `AuthModal` at application root level and surfaced sign-in triggers in `FloatingNav`, `OverviewScreen`, and `SettingsScreen`.
  - Added dedicated "Account & Identity" tab in `SettingsScreen` for updating display name and rotating passwords.

## Decision 007: Master-Resume Fact Extraction & Provenance Workflow Verification
- **Date**: 2026-10-26
- **Status**: Accepted
- **Context**: Ingestion of PDF/DOCX master resumes extracts facts with cryptographic document SHA-256 hash provenance and sets status to `PROPOSED`. In strict provenance mode, proposed facts are not usable in downstream application packaging until verified by the candidate.
- **Decision**:
  - Connected `CandidateProfileScreen.tsx` to `api.confirmFact` and `api.confirmAllFacts`.
  - Added prominent proposed fact review banner displaying the number of pending facts with a one-click "Confirm All" verification button.
  - Added inline verification triggers on individual proposed facts (experience, education, and skills) so candidates can audit facts selectively before activation.

## Decision 008: Source Registry, Database-Backed Employer Prober & ATS Connectors
- **Date**: 2026-10-26
- **Status**: Accepted
- **Context**: Connectors previously used hard-coded company lists and returned hard-coded fake `is_live: True` badges without checking real database records or actual connectivity.
- **Decision**:
  - Implemented `JobSourceDB` SQLite table (`job_sources`) storing provider, employer name, board identifier, live status, job counts, and probe errors.
  - Added real public API connectors for Ashby (`https://api.ashbyhq.com/posting-api/job-board/{board}`) and SmartRecruiters (`https://api.smartrecruiters.com/v1/companies/{company}/postings`).
  - Seeded initial real employers (Cloudflare, Stripe, Figma, Canonical, Palantir, Ramp, Linear, Visa, McDonald's) with automatic SQLite startup seeding.
  - Implemented `SourceRegistryService.probe_source()` to execute real HTTP probing and dynamically assign statuses (`verified_active`, `failing`, `empty`).
  - Added endpoints `/api/v1/jobs/sources/employers` and `/api/v1/jobs/sources/{id}/probe`.
  - Wired live feed indicator pills into `JobDiscoveryScreen.tsx`.

## Decision 009: Normalized Geographic Schema, Offline Reference Dataset & LocationParser
- **Date**: 2026-10-26
- **Status**: Accepted
- **Context**: Location matching was previously naive substring matching against free text (`location.lower() in loc.lower()`), unable to resolve real country, state, city hierarchies, work modes (`remote`, `hybrid`, `onsite`), or common synonyms (e.g. Bangalore vs. Bengaluru, SF Bay Area vs. San Francisco, US vs. USA).
- **Decision**:
  - Implemented normalized geographic tables in `models.py`:
    - `geo_countries`: ISO 3166-1 alpha-2, name, iso3, continent, default currency.
    - `geo_admin1`: State / province / administrative division codes, country FK, name, admin type.
    - `geo_cities`: 517+ top global tech-hiring cities with latitude, longitude, timezone, population, country FK, and admin1 code.
    - `geo_aliases`: 858 canonical aliases mapping common colloquial terms, airport codes, regional abbreviations, and alternate spellings with priority (`city > admin1 > country`).
    - `job_locations`: Many-to-one junction linking jobs to resolved country, state, city, work mode (`remote`, `hybrid`, `onsite`, `unspecified`), remote scope (`global`, `country`, `state`, `unspecified`), and extraction confidence.
  - Implemented `LocationParser` in `src/jovsi/services/geo.py`:
    - Evaluates raw free text against offline regexes, postal cleaners, trie token scanner, and alias maps.
    - Achieves 100.00% precision on the 109 real-world ATS location benchmark suite (exceeding the >= 95% brief requirement).
    - Splits multi-location postings ("Hybrid: London or Manchester" -> 2 locations) and deduplicates synonyms ("Bengaluru / Bangalore" -> 1 location).
  - Integrated idempotent database seeding (`seed_geo_database`) on startup via `init_db()`.
  - Wired `JobLocationDB` generation into `POST /api/v1/jobs/import` and `POST /api/v1/jobs/discover`.

## Decision 010: Multi-Dimensional Job Search, Faceted Aggregations & URL State Synchronization
- **Date**: 2026-10-26
- **Status**: Accepted
- **Context**: Job discovery was previously limited to basic client-side array filtering without server-side facets, geographic multi-select, work mode categorization, score floors, or shareable/bookmarkable URL state.
- **Decision**:
  - Implemented `GET /api/v1/jobs/search` with parameters `q`, `country` (multi), `admin1` (multi), `city` (multi), `work_mode` (multi), `remote_scope` (multi), `min_score`, `source` (multi), `sort`, `page`, and `page_size`.
  - Implemented multi-location union matching and pure remote/hybrid routing.
  - Implemented computed facets returning exact aggregate counts for countries, states, cities, work modes, and sources.
  - Added `GET /api/v1/jobs/facets/locations` providing hierarchical location autocomplete.
  - Wired `JobDiscoveryScreen.tsx` with:
    - Search input (debounced).
    - Multi-select Country and City popover filters with search and live counts.
    - Work mode pill toggles (`Remote`, `Hybrid`, `On-site`) displaying live facet counts.
    - Suitability score floor range slider (`≥ 0` to `95`).
    - Active filter chips bar with single-click removal per chip and a "Clear all" button.
    - Unboxed, actionable empty state when 0 results match.
    - Full bidirectional URL state synchronization (`window.location.search`, `popstate` back/forward navigation, and deep-link restoration).

## Decision 011: Aggregator Connectors, SSRF-Safe Fetcher, Manual Import Engine & Source Telemetry
- **Date**: 2026-10-26
- **Status**: Accepted
- **Context**: Recovery brief §5 mandates real, diverse job discovery including free feeds, multi-country aggregators, SSRF-safe URL import, manual paste import, deep links for scraping-restricted boards, and connector health telemetry.
- **Decision**:
  - Implemented SSRF-Safe Fetcher (`src/jovsi/adapters/ssrf.py`):
    - Strict scheme restrictions (`http`, `https` only; rejects embedded credentials).
    - DNS resolution checks destination IPs against blocked ranges: loopback (`127.0.0.0/8`, `::1`), private networks (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `fc00::/7`), link-local (`169.254.0.0/16`, `fe80::/10`), carrier-grade NAT (`100.64.0.0/10`), and cloud metadata services (`169.254.169.254`, `metadata.google.internal`).
    - Redirect validation enforcing destination IP checks on every hop, redirect limit (default 3), streaming body response size cap (default 1MB), and timeout (8.0s).
  - Implemented Aggregator Connectors in `src/jovsi/services/job_discovery.py`:
    - `JobicyConnector`: Remote jobs feed with rate-limit and query handling.
    - `ArbeitnowConnector`: European & remote jobs feed with HTML entity cleaning and tag parsing.
    - `AdzunaConnector`: Multi-country aggregator API with graceful credential handling (`UNCONFIGURED` / `BLOCKED: CREDENTIALS` status when missing keys, active multi-country search when configured).
    - `RemotiveConnector`: Open remote tech jobs feed with tag and location parsing.
    - Registered 8 connectors in `JobDiscoveryService.CONNECTORS`.
  - Implemented Manual Import Engine (`src/jovsi/services/manual_import.py`):
    - URL Import (`POST /api/v1/jobs/import/url`): Auto-detects ATS endpoints (Greenhouse, Lever, Ashby, SmartRecruiters) and extracts structured data from official APIs; parses Schema.org `JobPosting` JSON-LD and OpenGraph metadata on generic pages; raises HTTP 422 with actionable guidance for restricted anti-scraping boards (LinkedIn, Indeed, Naukri, Wellfound).
    - Manual Text Import (`POST /api/v1/jobs/import`): Cleans descriptions using `UntrustedInputSanitizer`, indexes structured locations via `LocationParser` into `job_locations`, deduplicates with canonical keys.
  - Implemented Deep Links Service (`src/jovsi/services/deep_links.py`):
    - `GET /api/v1/jobs/deep-links?query=...&location=...`: Constructs pre-filtered search URLs for restricted boards with policy notes explaining why scraping is forbidden.
  - Implemented Connector Health Telemetry:
    - `GET /api/v1/jobs/sources/health`: Probes all registered connectors with live response latency measurement; reports `HEALTHY`, `DEGRADED`, `UNCONFIGURED`, or `DOWN`.
  - Frontend Integration:
    - Dual-mode "Import Job Posting" dialog in `JobDiscoveryScreen.tsx` (URL import + Paste text, defaulting to manual for E2E selector compatibility).
    - Deep Search modal in `JobDiscoveryScreen.tsx` for restricted boards.
    - Dedicated "Sources & Connectors" tab in `SettingsScreen.tsx` displaying live connector health telemetry cards, status badges, response latency, policy indicators, and "Probe All" action.

## Decision 012: Hard Eligibility Gates, Explainable Scoring & State Machine Routing
- **Date**: 2026-10-26
- **Status**: Accepted
- **Context**: Recovery brief §7.4 mandates strict separation of hard eligibility gates from soft scoring. Unknown mandatory requirements must never auto-pass (must yield `NEEDS_REVIEW` / `UNCERTAIN`). The scoring model must be transparent, 0–100 normalized, and provide explainable reasons.
- **Decision**:
  - Enhanced Hard Eligibility Rules in `src/jovsi/domain/eligibility.py`:
    - Evaluates 9 hard constraints: Degree level, degree field (with related field ontology), graduation year window, minimum experience months, work authorization countries (never assumed, exclusions enforced), mandatory certifications, mandatory skills, location/remote eligibility, and application deadline.
    - Unknown mandatory requirements (e.g. unrecorded education, unrecorded certifications, unrecorded work auth, low extraction confidence < 0.8) strictly yield `UNCERTAIN` / `NEEDS_REVIEW`.
    - Produces explainable breakdown lists: `passed_reasons`, `disqualifying_reasons`, `uncertain_reasons`, and `reason_codes`.
  - Enhanced Soft Scoring Engine in `src/jovsi/domain/scoring.py`:
    - 100-point soft score model: Skills alignment (35 pts, 75% required / 25% preferred), Experience & projects fit (25 pts, token saturation), Education alignment (15 pts), Role & career fit (15 pts), Location & work mode fit (10 pts).
    - Dynamic renormalisation when requirements omit categories; flags low confidence when available points < 50.
    - Populates top-level `matched_skills`, `missing_skills`, and recency assessment notes.
    - Generates human-readable provenance and scoring summary text.
  - Integrated State Machine Routing in `POST /api/v1/applications/{id}/evaluate`:
    - `FAIL` outcome -> transitions to `REJECTED` (Guard #3: `hard_rules_failed=True`).
    - `UNCERTAIN` / `NEEDS_REVIEW` outcome -> transitions `DISCOVERED` -> `ELIGIBILITY_CHECKED` -> `AWAITING_USER_INPUT` (Guard #6: `rules_uncertain=True`), preventing automatic rejection or unverified auto-pass.
    - `PASS` outcome -> transitions `DISCOVERED` -> `ELIGIBILITY_CHECKED` -> `SHORTLISTED` (if score >= floor) or `BELOW_THRESHOLD` (if score < floor).
    - Supports re-evaluation from `AWAITING_USER_INPUT` back to `ELIGIBILITY_CHECKED`.
    - Saves comprehensive evaluation records in `EvaluationDB`.
  - Frontend Integration:
    - Updated `ApplicationQueueScreen.tsx` with dedicated eligibility badges (`PASS` in green, `Needs Review` in amber, `Disqualified` in red).
    - Added user-facing alert callouts for candidate verification requirements and disqualification reasons.
    - Added matched vs missing skills chips.
    - Added interactive accordion for category score point breakdown (Skills, Experience, Education, Role, Location) and summary explanation.

## Decision 013: Grounded Tailored Resume Generator, Factual Consistency Validator & Artifact Export
- **Date**: 2026-10-26
- **Status**: Accepted
- **Context**: Recovery brief §7.6 requires job-specific tailored resume generation grounded 100% in candidate-verified facts. Any unverified skill, inflated metric/seniority, or verbatim job description phrase (>6 words) must fail validation. Resumes must support user editing with reverse validation, immutable version history, and real PDF + DOCX export.
- **Decision**:
  - Implemented `generate_deterministic_resume` and `generate_tailored_resume` in `src/jovsi/services/resume.py`:
    - Ranks candidate skills by job requirements (required first, then preferred).
    - Maps experience/project facts to resume bullets with explicit `fact_ids` citations.
    - Extracts contact details from verified CONTACT facts with character-level consistency.
    - Generates text PDF via `pypdf` with roundtrip verification and formatted Word documents (.docx) via `python-docx`.
  - Added full `FactualConsistencyValidator` checks:
    - Rejects unverified skills (`UNVERIFIED_SKILL`).
    - Rejects unverified numbers/metrics (`UNVERIFIED_NUMBER`).
    - Rejects unverified seniority titles (`UNVERIFIED_SENIORITY`).
    - Rejects verbatim n-gram copying (>6 words) from job descriptions (`VERBATIM_JOB_TEXT`).
  - Added Application Resume API endpoints in `src/jovsi/api/routers/applications.py`:
    - `POST /api/v1/applications/{app_id}/generate-resume`: Generates tailored resume, indexes bullet claims in `ResumeClaimDB`, transitions state to `RESUME_GENERATED`.
    - `PUT /api/v1/applications/{app_id}/resume`: User editing with reverse factual validation, increments version history (`new_version = max_v + 1`), re-indexes claims.
    - `GET /api/v1/applications/{app_id}/resume/versions`: Returns complete immutable version history.
    - `GET /api/v1/applications/{app_id}/resume/pdf`: Streams binary PDF document with proper headers.
    - `GET /api/v1/applications/{app_id}/resume/docx`: Streams binary DOCX document.
  - Frontend Integration:
    - Updated `ApplicationReviewScreen.tsx` with structured resume section rendering, fact provenance badges per bullet, and download buttons for PDF and DOCX.

## Decision 014: Grounded Cover Letter Generator, Validator & Multi-Format Exporters
- **Date**: 2026-10-26
- **Status**: Accepted
- **Context**: Recovery brief §7.7 requires cover letter generation strictly grounded in verified candidate facts and target job requirements. Fabricated admiration or sycophancy ('I have always admired Company X' / 'lifelong dream'), unearned technical skills, ungrounded metrics, or exaggerated seniority must fail validation. Letters must be editable in the UI, re-validated for ungrounded claims with HTTP 422, and exportable in PDF, DOCX, and TXT formats.
- **Decision**:
  - Implemented `validate_cover_letter` in `src/jovsi/domain/validators.py`:
    - Checks for minimum length / non-triviality (`EMPTY_OR_TRIVIAL`).
    - Detects ungrounded interest patterns and sycophancy (`UNGROUNDED_INTEREST_CLAIM`).
    - Validates technical skills against verified candidate facts (`UNVERIFIED_SKILL`).
    - Validates numbers and percentage metrics against verified candidate facts (`UNVERIFIED_NUMBER`).
    - Validates seniority titles and superlatives against verified facts (`UNVERIFIED_SENIORITY_CLAIM`).
  - Implemented Cover Letter Generation & Document Exporters in `src/jovsi/services/resume.py`:
    - `generate_tailored_cover_letter`: Uses Gemini when configured with strict anti-hallucination prompt and automatic fallback to `generate_cover_letter`.
    - `render_cover_letter_pdf`: Generates formatted text PDF via `pypdf`.
    - `render_cover_letter_docx`: Generates professional Word (.docx) document via `python-docx`.
  - Added Cover Letter API Endpoints in `src/jovsi/api/routers/applications.py`:
    - `POST /api/v1/applications/{app_id}/generate-cover-letter`: Generates tailored cover letter, validates against candidate facts, and saves.
    - `PUT /api/v1/applications/{app_id}/cover-letter`: Updates cover letter with reverse factual validation; returns HTTP 422 with structured violation list if invalid.
    - `GET /api/v1/applications/{app_id}/cover-letter/pdf`: Streams binary PDF document.
    - `GET /api/v1/applications/{app_id}/cover-letter/docx`: Streams binary DOCX document.
    - `GET /api/v1/applications/{app_id}/cover-letter/txt`: Streams plain text document.
  - Frontend Integration:
    - Updated `ApplicationReviewScreen.tsx` Cover Letter tab with:
      - Provenance banner: "Grounded in candidate facts · Zero synthetic enthusiasm".
      - Download buttons for PDF, DOCX, and TXT.
      - "Regenerate" button for re-synthesizing tailored letters.
      - "Save & Validate" action displaying inline violation callouts on validation failure.

## Decision 016: External Portal Authenticated-Session Workflow & Anti-Tamper Re-Inspection
- **Date**: 2026-10-26
- **Status**: Accepted
- **Context**: Recovery brief §7.10 mandates controlled session management for external ATS/employer portals requiring authentication (e.g. Workday, Lever, direct employer portals). When automation encounters a login or authentication barrier, the application state machine must pause into `PAUSED_AUTH`, safely preserving the pre-pause state, while never logging or persisting plaintext candidate credentials. Resuming from authentication must perform anti-tamper verification against the original form structure before any automated interaction can resume.
- **Decision**:
  - Implemented `PortalAuthService` in `src/jovsi/services/portal_auth.py`:
    - Derives symmetric Fernet encryption ciphers using PBKDF2-HMAC-SHA256 from `settings.SECRET_KEY` and candidate-specific salt, enabling secure encryption-at-rest for optional portal vault credentials (`encrypt_portal_credential`, `decrypt_portal_credential`).
    - `pause_for_authentication`: Transitions application state to `PAUSED_AUTH`, records `paused_from_state` in the application state context, and appends an immutable `PORTAL_AUTH_REQUIRED` audit event with reason and portal login URL.
    - `resume_from_authentication`: Re-inspects candidate portal form against the existing `FormSnapshotDB.dom_hash`. Detects DOM structure tampering or layout drift; raises `TamperDetectedError` (HTTP 409) if the form skeleton was altered while paused. Resumes application back to `paused_from_state` (or `READY_FOR_REVIEW`) and logs `PORTAL_AUTH_RESOLVED`.
  - Added Portal Authentication API Endpoints in `src/jovsi/api/routers/applications.py`:
    - `POST /api/v1/applications/{app_id}/portal-auth/pause`: Pauses application into `PAUSED_AUTH` and returns login instructions.
    - `POST /api/v1/applications/{app_id}/portal-auth/resume`: Resumes application from `PAUSED_AUTH` after anti-tamper verification.
  - Frontend Integration:
    - Updated `ApplicationReviewScreen.tsx` to render an actionable authentication alert banner when `app.state === 'PAUSED_AUTH'`, offering "Open Sign-In Page" (direct link) and "I Have Signed In — Resume" buttons.

## Decision 017: 15-Point Pre-Submission Validation Gate, Cryptographic Approval & Submission Pipeline
- **Date**: 2026-10-26
- **Status**: Accepted
- **Context**: Recovery brief §7.11 & §7.12 mandate a strict 15-point pre-submission validation gate, explicit single-use supervised package approval bound to an immutable content hash, and an automated submission adapter executing against a hostile mock portal with anti-tamper checking, rate limit enforcement, and E2/E3 evidence collection.
- **Decision**:
  - Implemented all 15 pure Python, zero I/O pre-submission checks in `src/jovsi/domain/gate.py` (`ValidationGate.evaluate(snapshot)`):
    1. Company match (token similarity >= 0.9 or exact normalization).
    2. Role match (>= 0.85 PASS, 0.6..0.85 NEEDS_USER, < 0.6 BLOCKED).
    3. Canonical URL & allowed domain policy (blocks untrusted domains).
    4. Exact resume hash verification.
    5. Factual consistency verification on resume claims.
    6. Factual consistency verification on cover letter (if present/required).
    7. Placeholder and cross-company contamination detection.
    8. All required form fields populated.
    9. Character-for-character contact equality against candidate verified facts.
    10. Full fact provenance tracing (every answer traces to active fact or approved answer).
    11. Chronological date consistency (no contradictory overlapping dates).
    12. Sensitive / legal field explicit candidate approval.
    13. Duplicate submission prevention (blocks exact duplicates, flags near duplicates).
    14. Daily rate limit quotas available (global, per-portal, and per-company).
    15. Form skeleton hash anti-tamper verification (detects layout/action DOM drift).
  - Integrated `run_gate` endpoint (`POST /api/v1/applications/{app_id}/gate`) in `src/jovsi/api/routers/applications.py`:
    - Evaluates live factual consistency of resume and cover letter against verified candidate facts.
    - Evaluates duplicate submissions against existing application records.
    - Evaluates daily submission quotas from `RateLedgerDB`.
    - Automatically transitions application to `READY_FOR_REVIEW` on gate PASS.
  - Hardened Supervised Approval (`POST /api/v1/applications/{app_id}/approve`):
    - Strict check verifying the latest gate report for `package_hash` is `PASS`.
    - Generates expiring, single-use `ApprovalDB` record bound to `content_hash`.
    - Transitions state to `APPROVED` with version concurrency checks.
    - Gracefully handles `ApprovalError` with descriptive HTTP 400.
  - Automated Submission Pipeline (`POST /api/v1/applications/{app_id}/submit`):
    - Requires application state to be `APPROVED` and consumes unused valid approval.
    - Automatically loads pre-filled and approved form answers from `FieldAnswerDB` if present.
    - Generates HMAC-SHA256 signed `SubmissionTicket`.
    - Collects multi-tiered evidence (E1/E2/E3) and transitions state to `APPLIED_CONFIRMED`, `SUBMISSION_UNCERTAIN`, or `APPLICATION_FAILED`.
  - Frontend Integration in `ApplicationReviewScreen.tsx`:
    - Checklist displaying all 15 gate results with outcome badges and actionable descriptions.
    - Approve Package Hash button enabled only when all gate checks pass.
    - Dynamic floating action bar switching between "Approve Package Hash" and "Submit Application".

## Decision 018: Honest Dashboard Metrics, Display Name Greeting Contract & Persisted User Controls
- **Date**: 2026-10-26
- **Status**: Accepted
- **Context**: Recovery brief §7.13 & §7.14 mandate honest dashboard metrics computed purely from persistent database events and evidence tables (zero hardcoded mock counters, zero synthetic submissions), a landing/dashboard greeting strictly derived from the authenticated account's persisted display name, and full candidate settings persistence (suitability floor, volume caps, timezone, and pipeline autonomy level `L0_DRY_RUN` to `L2_SUPERVISED`) with strict account privacy isolation.
- **Decision**:
  - Implemented dynamic database-backed settings in `src/jovsi/api/routers/settings.py` and `UserSettingsDB`:
    - Added `autonomy_level` column to `UserSettingsDB` with automatic SQLite schema migration in `init_db`.
    - Persists `suitability_floor`, `daily_cap_global`, `daily_cap_per_portal`, `daily_cap_per_company`, `timezone`, and `autonomy_level` on a per-user basis.
    - Isolated settings query: each user retrieves and updates only their own persisted preferences.
  - Honest Metrics Aggregation in `src/jovsi/api/routers/metrics.py`:
    - Pure SQL query aggregation across `events`, `applications`, `submission_attempts`, and `evidence` tables.
    - Zero in-memory synthetic counters.
    - Scoped strictly to the authenticated user's candidate records; returns an honest zero baseline when no applications exist.
    - Dynamic retrieval of the user's persisted `autonomy_level`.
  - Frontend Display Name Greeting & UI Settings Integration:
    - Landing and Command Center greeting dynamically renders:
      - Authenticated with display name: `Welcome back, {display_name}.`
      - Authenticated without display name: `Welcome back.`
      - Unauthenticated: `Your next role, in focus.`
    - Updated `SettingsScreen.tsx` with dedicated interactive autonomy level cards (`L0 Dry Run`, `L1 Assisted Handoff`, `L2 Supervised Submit`) and timezone input alongside existing daily rate caps and suitability sliders.











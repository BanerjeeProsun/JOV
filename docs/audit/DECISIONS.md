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

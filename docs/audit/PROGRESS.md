# JOV.si — Recovery Progress Tracker

**Active Baseline Git Tag**: `pre-recovery` (Commit: `cf916c3`)

---

## Milestone Status Overview

| Milestone | Title | Status | Tests Passed | Commit |
|---|---|---|---|---|
| **M0** | Recon, Inventory, Recovery Plan | **COMPLETED** | 115 / 115 | `1b98d5c` |
| **M1** | Strict Authentication, Identity & Isolation | **COMPLETED** | 124 / 124 | `753f0cf` |
| **M2** | Configuration, Secrets Hygiene, LLM Provider | **COMPLETED** | 133 / 133 | Pending |
| **M3** | Zombie-Code Removal & Mock Isolation | **IN PROGRESS** | - | - |
| **M4** | Master-Resume Ingestion & Profile Verification | **PENDING** | - | - |
| **M5** | Source Registry & Real ATS Connectors | **PENDING** | - | - |
| **M6** | Normalized Schema, Geo Dataset & Parser | **PENDING** | - | - |
| **M7** | Search & Filters: Facets, URL State & UI Wiring | **PENDING** | - | - |
| **M8** | Aggregator/Feed Connectors & Manual Import | **PENDING** | - | - |
| **M9** | Eligibility Gates & Explainable Scoring | **PENDING** | - | - |
| **M10** | Job-Specific Resume Generation & Grounding | **PENDING** | - | - |
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

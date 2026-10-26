# JOV.si — Recovery Progress Tracker

**Active Baseline Git Tag**: `pre-recovery` (Commit: `cf916c3`)

---

## Milestone Status Overview

| Milestone | Title | Status | Tests Passed | Commit |
|---|---|---|---|---|
| **M0** | Recon, Inventory, Recovery Plan | **IN PROGRESS** | 115 / 115 | Pending |
| **M1** | Strict Authentication, Identity & Isolation | **PENDING** | - | - |
| **M2** | Configuration, Secrets Hygiene, LLM Provider | **PENDING** | - | - |
| **M3** | Zombie-Code Removal & Mock Isolation | **PENDING** | - | - |
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

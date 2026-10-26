# JOV.si — Autonomous Job Application Platform

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19-61DAFB.svg)](https://react.dev/)
[![TailwindCSS](https://img.shields.io/badge/TailwindCSS-3.4-38B2AC.svg)](https://tailwindcss.com/)
[![Playwright](https://img.shields.io/badge/Playwright-Chromium-45ba4b.svg)](https://playwright.dev/)
[![Test Suite](https://img.shields.io/badge/Tests-108%20Passed-brightgreen.svg)]()

> **Autonomous job discovery, evaluation, resume personalization, cover letter generation, and application automation platform.**  
> Built strictly adhering to the *JOV.si Architecture & Implementation Blueprint v2.0* and the *Raycast Midnight Command-Center* design system (`DESIGN.md`).

---

## 1. System Invariants & Core Guarantees

1. **Zero Fabricated Data or Metrics**: No mock counts, random chart numbers, or fabricated submission successes. All dashboard metrics derive strictly via SQL aggregation over append-only audit events (`events`), verified evidence records (`evidence`), and rate ledgers (`rate_ledger`).
2. **Strict Provenance Engine**: Every claim, date, or credential included in a generated resume or field answer must trace directly to an `ACTIVE` candidate fact with provenance `USER_SUPPLIED` or `USER_VERIFIED`. Unverified `PROPOSED` facts are physically blocked from document generation.
3. **15-Point Pre-Submission Validation Gate**: Applications are evaluated against an immutable `GateSnapshot` and bound to a cryptographic package hash:
   $$H = \text{SHA-256}(\text{canonical\_json}(\text{resume}, \text{cover\_letter}, \text{answers}, \text{target\_url}, \text{job\_hash}))$$
   Approval buttons in the UI are strictly disabled unless the gate evaluates to `PASS`.
4. **Evidence Ladder & Honest Status**: The label "Applied" is reserved strictly for `APPLIED_CONFIRMED` ($\ge E_2$ portal receipt number or $E_3$ status page check). Ambiguous submissions, timeouts, or network interruptions enter `SUBMISSION_UNCERTAIN` ("Sent, not confirmed") and are never automatically retried.
5. **Release 1 Safety Sandbox**: Automated browser submissions are physically restricted by adapter guards to the local hostile mock portal (`127.0.0.1:8765`, `localhost:8765`). Submissions to external production hosts are rejected.

---

## 2. Architecture & Design Tokens

### Layer Architecture
- **Domain Layer (`src/jovsi/domain/`)**: Pure domain models, 19-state transition machine, Phase A hard rules, Phase B 100-point soft scorer, factual consistency validator, and the 15-point validation gate. Zero external database or network dependencies (enforced by AST lint).
- **Service Layer (`src/jovsi/services/`)**: Orchestration for candidate fact provenance, resume tailoring, single-use hash-bound approvals, insert-then-click submission protocol, and reconciliation.
- **Adapter Layer (`src/jovsi/adapters/`)**: SQLAlchemy 2.0 database models with SQLite append-only triggers, hostile input sanitizer, Playwright browser automation, and mock portal adapters.
- **API Layer (`src/jovsi/api/`)**: FastAPI application with strict RFC 7807 problem details error handlers and REST routers.
- **Frontend Layer (`web/`)**: React 19 + TypeScript + Tailwind CSS Single Page Application compiled to `web/dist` and served directly by FastAPI or standalone via Vite.

### Design Tokens (`DESIGN.md`)
- **Canvas (`--color-void-black`)**: `#040506`
- **Card Surface (`--color-ink`)**: `#07080a` with signature tactile keyboard key inner shadow stack
- **Recessed Surface (`--color-obsidian`)**: `#111214`
- **Brand Accent (`--color-coral-pulse`)**: `#ff6363` (used exclusively for brand diamond mark, AI badges, and warnings)
- **Action Buttons (`--color-mist`)**: `#e6e6e6` neutral fill paired with `#454647` iron text
- **Hairline Borders**: `#363739`
- **Typography**: Inter for interface elements; Geist Mono for hashes, IDs, and technical metadata

---

## 3. Quick Start & Execution

### Prerequisites
- Python 3.11+
- Node.js v20+ and npm

### 1. Set Up Backend Virtual Environment
```bash
python -m venv .venv
.venv\Scripts\activate   # On Windows
pip install -e .
playwright install chromium
```

### 2. Build Frontend Single-Page App
```bash
cd web
npm install
npm run build
cd ..
```

### 3. Run the Services
**Terminal 1: Start the Local Hostile Mock Portal (Port 8765)**
```bash
uvicorn mock_portal.server:app --host 127.0.0.1 --port 8765
```

**Terminal 2: Start the JOV.si Core Application (Port 8000)**
```bash
uvicorn jovsi.api.main:app --host 127.0.0.1 --port 8000
```

Open your browser to:
- **Web Command Center**: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **API Documentation**: [http://127.0.0.1:8000/api/docs](http://127.0.0.1:8000/api/docs)
- **Health Diagnostics**: [http://127.0.0.1:8000/diagnostics/health](http://127.0.0.1:8000/diagnostics/health)

---

## 4. Verification & Testing

JOV.si includes a comprehensive 108-test automated suite verifying every architectural invariant and failure mode:

```bash
# Run all 108 tests
pytest -v

# Run 40-point factual consistency mutation corpus
pytest tests/unit/test_mutation_corpus.py

# Run 30-scenario hostile failure injection matrix
pytest tests/failure/test_failure_matrix.py

# Run 14-step backend vertical slice
pytest tests/e2e/test_vertical_slice.py

# Run full headless Chromium browser UI acceptance test
pytest tests/e2e/test_ui_vertical_slice.py
```

### Verification Test Suite Summary

| Milestone | Scope | Total Tests | Status |
|---|---|---|---|
| **M0 Foundations** | State machine (19x19), triggers, layers, AST lint, locator lint | 12 | **PASSED** |
| **M1 Profile & Ingestion** | Provenance lifecycle, hostile sanitizer, hard rules | 16 | **PASSED** |
| **M2 Scoring & Validation** | 100-pt scorer invariants, 40 deliberate mutations, PDF round-trip | 48 | **PASSED** |
| **M3 Mock Portal Adapter** | Mock server fault modes, form filler, read-back checks | 3 | **PASSED** |
| **M4 Gate & Failure Matrix** | 15 pre-submission checks, 30 failure scenarios | 27 | **PASSED** |
| **M5 Vertical Slice Backend** | 14 sequential pipeline steps to confirmed submission | 1 | **PASSED** |
| **M5 Full Browser UI Acceptance** | Real Chromium browser session exercising all 8 screens | 1 | **PASSED** |
| **TOTAL** | Complete verifiable test coverage | **108** | **ALL PASSED** |

---

## 5. Screen Inventory (8 Required Screens)

1. **Overview (`/`)**: Real-time honest KPI cards calculated from `/api/v1/metrics/summary` (Prepared, Confirmed, Uncertain, Failed, Today's Rate Ledger, Confirmation Rate).
2. **Job Discovery (`/jobs`)**: Table of imported jobs, search filter, details inspector, and Job Import modal with untrusted input sanitization.
3. **Application Queue (`/queue`)**: Active pipeline items moving through evaluation, resume generation, gate execution, and submission.
4. **Application Review (`/review/:id`)**: Package inspector, structured resume preview, field answers with provenance tags, full 15-point Gate Report table, and package hash approval button (strictly locked unless gate passes).
5. **Application Tracker (`/tracker`)**: Persistent application history, evidence levels ($E_0$–$E_3$), confirmation receipts, and append-only event audit logs.
6. **Candidate Profile (`/profile`)**: Fact graph grouped by category (Contact, Education, Experience, Skills, Work Auth) with status badges and confirmation actions.
7. **Settings (`/settings`)**: Configurable suitability match score floor, daily rate limits (global, portal, company), and read-only environment safety rails.
8. **Diagnostics (`/diagnostics`)**: Live API health, database trigger verification, mock portal oracle inspector (`/__admin/applications`), and test portal reset actions.

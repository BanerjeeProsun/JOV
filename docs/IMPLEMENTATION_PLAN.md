# JOV.si — Implementation Plan & Milestone Execution Roadmap

**Product Name:** JOV.si  
**Architecture Specification:** JOV.si Architecture & Implementation Blueprint v2.0  
**Design Reference:** DESIGN.md (Raycast dark theme, `#040506` canvas, Inter/GeistMono, `#ff6363` Coral accent)  
**Version:** 2.0.0-draft  
**Last Updated:** 2026-10-26  

---

## 1. System Vision & Architecture Overview

JOV.si is an autonomous, evidence-backed job discovery, evaluation, resume personalization, cover letter generation, and application automation platform. Its core invariant is **absolute correctness, honesty, and safety over speed or volume**:
- **Never fabricate** jobs, metrics, qualifications, dates, credentials, or submission statuses.
- **Strict provenance**: Every statement in a resume or form value must link directly to an active, verified candidate fact (`USER_SUPPLIED` or `USER_VERIFIED`).
- **15-point Pre-Submission Gate**: Evaluated against an immutable snapshot, producing a cryptographic package hash $H = \text{SHA-256}(\text{resume}, \text{cover\_letter}, \text{answers}, \text{target\_url}, \text{job\_hash})$. Approvals are bound to this exact hash.
- **Evidence Ladder**: Status `APPLIED_CONFIRMED` requires verifiable evidence ($E_2$ portal receipt or $E_3$ independent status page check). Any crash, timeout, or ambiguity enters `SUBMISSION_UNCERTAIN`, never auto-retried.
- **Two Processes, Three Layers**:
  1. API Process (FastAPI) serving UI decisions and recording user intent.
  2. Worker Process (Lease-based database queue) executing pipeline stages and browser automation.
  3. Pure Domain Core (models, state machine, rules, scoring, validators, gate) with zero external I/O.
- **Strict Release 1 Safety Boundary**: Submission host allowlist restricted strictly to `127.0.0.1:8765` (isolated local mock portal). All external real submissions are physically disabled until explicit later milestones.

---

## 2. Milestone Breakdown & Acceptance Gates

### Milestone 0: Foundations (M0) — Gate G0
**Deliverables:**
- Repository structure, project configurations (`pyproject.toml`, `.gitignore`, `alembic.ini`).
- Core environment configuration (`config.py`) with strict startup validation.
- Database models (SQLAlchemy 2.0 with SQLite WAL + foreign keys enabled, migration support).
- 19-state, 28-transition State Machine (`domain/state_machine.py`) with transition guards.
- Append-only audit event log with SQLite triggers preventing UPDATE and DELETE.
- Work queue leasing and heartbeat logic (`work_items`).
- API skeleton with health endpoint (`/health`, `/diagnostics/health`).
- Architectural lint checks (dependency boundary test, locator rule checks).

**Acceptance Gate G0:**
- 19x19 state transition matrix fully tested: exactly the 28 legal transitions pass, all others raise `IllegalTransition`.
- Database trigger proves direct UPDATE/DELETE on `events` table fails.
- Application boots and `/health` responds.
- Import boundary test verifies pure domain logic has zero external dependencies.

---

### Milestone 1: Candidate Profile & Job Ingestion (M1)
**Deliverables:**
- Candidate profile and fact domain models (`models.py`, `provenance.py`).
- Fact provenance engine (`USER_SUPPLIED`, `USER_VERIFIED`, `PROPOSED`, `REJECTED`, `SUPERSEDED`).
- Document upload and sha256 tracking.
- Untrusted input sanitization (`sanitizer.py`) for stripping HTML, script, zero-width characters, hidden divs, and normalising Unicode.
- Job ingestion API (`/jobs/import`) with canonical job key generation (`sha256(portal_key + native_id)` or `sha256(company + title + location)`).
- Deterministic requirement extraction (degrees, graduation years, experience, work auth, certifications, deadlines).
- Phase A hard constraint rules engine (`eligibility.py`) returning `PASS`, `FAIL`, or `UNCERTAIN`.

**Acceptance Gate:**
- Synthetic candidate and facts survive a complete application restart.
- `PROPOSED` facts cannot be used until confirmed as `USER_VERIFIED`.
- Sanitizer passes malicious input, hidden text, and oversized payload tests.
- Hard eligibility rules accurately flag pass, fail, and uncertain conditions without assumptions.

---

### Milestone 2: Scoring & Resume Personalization (M2) — Gate G1
**Deliverables:**
- Two-phase eligibility and scoring model (`scoring.py`):
  - Phase A: Hard gates (Degree, Grad Year, Min Experience, Work Auth, Certifications, Deadlines).
  - Phase B: 100-point soft scoring (Skills 35, Experience 25, Education 15, Role 15, Location 10) with dynamic renormalization when categories lack data.
  - Transparent explanation payload ("why 71/100", evidence spans, missing items).
- Deterministic resume generation from verified facts (`RESUME_GENERATED` stage).
- `FactualConsistencyValidator`:
  1. Structure & provenance validation.
  2. Entity coverage against canonical skill ontology.
  3. Date range containment and non-overlap check.
  4. Character-for-character contact information match.
  5. Superlatives/seniority check against fact text.
  6. Job-text verbatim copying detection (>6 words).
- Text PDF generation and round-trip extraction verification.
- Optional Cover Letter generation linked to facts and verified job details.

**Acceptance Gate G1:**
- Scorer mathematical invariants hold: determinism, monotonicity, bounds [0, 100], sum of category maxima = 100.
- All 40+ mutation corpus test cases (invented skills, altered dates, inflated numbers, false seniority, unverified employer) are rejected with exact error codes.
- Uncorrupted resume passes cleanly.
- PDF rendered text matches structured JSON round-trip test.

---

### Milestone 3: Mock Portal & Playwright Adapter (M3)
**Deliverables:**
- Hostile Mock Portal (`mock_portal/`) running on `127.0.0.1:8765`:
  - Career listings, dynamic application form, confirmation receipts, status lookup page.
  - Ground-truth database oracle `/__admin/applications`.
  - Fault modes: `slow_submit`, `drop_after_submit`, `reject_without_record`, `already_applied_warning`, `session_expired`, `captcha_required`, `dom_drift`, `job_404`, `server_validation_error`, `lying_confirmation`, `double_click`.
- Adapter layer split into dedicated interfaces:
  - `PortalDetector`: URL matching and policy lookup (no browser).
  - `PortalInspector`: Read-only DOM and field extraction.
  - `FormFiller`: Safe form population and read-back validation.
  - `Submitter`: Guarded submission requiring cryptographically signed `SubmissionTicket`.
- Playwright automation adhering strictly to locator policies (role, label, test-id; no XPath, no coordinates).

**Acceptance Gate:**
- FormFiller populates mock portal and read-back matches plan perfectly.
- L0 Dry-run execution leaves mock oracle with exactly 0 records.
- Adapter contract tests pass across all mock portal standard and edge cases.

---

### Milestone 4: Gate, Approval, Submission & Recovery (M4) — Gate G2
**Deliverables:**
- Full 15-Point Pre-Submission Validation Gate (`gate.py`):
  1. Company match
  2. Role match
  3. Canonical URL & domain check
  4. Correct job-specific resume attached
  5. Resume factual check passed
  6. Cover letter check passed
  7. No unresolved placeholders (`{{...}}`, `TODO`, `[NAME]`, cross-company contamination)
  8. All required fields populated
  9. Valid email and phone
  10. All values provenance-verified
  11. No contradictory dates
  12. No unapproved sensitive or legal answers
  13. No duplicate submission
  14. Rate-limit quota available (global, per-portal, per-company)
  15. No unexpected DOM mutation (form skeleton hash match)
- Content-hash bound approval protocol:
  - Single-use approval ticket bound to package SHA-256.
  - Fast pre-click recheck (< 2s) immediately prior to submit.
- Submission protocol with `insert-then-click` and rate ledger atomicity.
- Evidence collection ladder (E0 to E3) with SHA-256 proof artifacts.
- Watchdog and asynchronous Reconciler for `SUBMISSION_UNCERTAIN`.
- Full 30-scenario failure-injection test matrix.

**Acceptance Gate G2:**
- All 30 failure scenarios pass with expected domain states and ground-truth oracle verification.
- Oracle never records more than 1 submission for any application.
- Meta-tests verify that disabling any single gate check causes test suite failure.

---

### Milestone 5: Frontend Interface & End-to-End Acceptance (M5) — Gate G3
**Deliverables:**
- React 18 + TypeScript + Tailwind CSS application implementing the `DESIGN.md` specification:
  - Palette: Canvas (`#040506`), Card (`#07080a`), Recessed (`#111214`), Graphite (`#1b1c1e`), Secondary (`#9c9c9d`), Muted (`#6a6b6c`), Mist (`#e6e6e6`), Iron (`#454647`), Coral Brand Accent (`#ff6363`), Border (`#363739`).
  - Typography: Inter for UI, Geist Mono / monospace for metadata.
  - Tactile "key" inset shadow treatment, 8px grid alignment.
- 8 fully functional screens:
  1. Overview: Honest KPI cards, activity breakdown, autonomy banner.
  2. Job Discovery: Real search, filter, sort, match score breakdown, import modal.
  3. Application Queue: Active pipeline states, worker status, blocker reasons.
  4. Application Review: Package inspector, PDF preview, provenance badges, gate report, approval action.
  5. Application Tracker: Persistent application history, evidence levels, proof viewer, audit timeline.
  6. Candidate Profile: Fact management by category, status filters, provenance indicators, fact confirmation.
  7. Settings: Quota caps, suitability threshold, timezone, autonomy level controls (read-only safety flags).
  8. Diagnostics: Worker heartbeat, queue depth, gate results, system health, Playwright traces.
- Complete 14-step end-to-end vertical slice execution.

**Acceptance Gate G3:**
- 14-step vertical slice passes from clean cold start to verified `APPLIED_CONFIRMED`.
- UI displays no mock/hardcoded numbers; all cards derive directly from database queries.
- UI tests verify Approve button is disabled when gate outcome != PASS.
- `SUBMISSION_UNCERTAIN` is never labeled as "Applied".

---

### Post-M5: Extensions & Real-World Integration Readiness
**Deliverables:**
- Real Permitted Job Discovery Engine:
  - Public career API integrations (e.g. Greenhouse, Lever, Workable public job boards).
  - Source registry with health status, rate limits, capability flags.
- User-Assisted Persistent Authentication:
  - Isolated browser context for user login handoff.
  - AES-256 encrypted session storage (`storage_state`).
  - Session validation, expiry detection, and graceful handoff.
- Multi-document Candidate Ingestion:
  - Structured extraction from resumes/transcripts into `PROPOSED` facts.
  - Interactive fact review and verification workflow.
- Cover Letter Generation Engine:
  - Role-tailored template engine using verified candidate accomplishments.
  - Consistency and anti-contamination validation.
- Extensible Portal Integration Architecture:
  - Portal policy registry with legal review timestamps.
  - Supervised real-world submission protocol under strict user authorization.

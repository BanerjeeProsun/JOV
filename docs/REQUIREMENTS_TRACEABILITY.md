# JOV.si — Requirements Traceability Matrix

This document maps all architectural, functional, security, and verification requirements from the JOV.si Blueprint v2.0 and Master Engineering Directive to their implementing modules, associated test suites, current status, and completion evidence.

---

## 1. Core Architecture & Invariants

| ID | Requirement Description | Source | Implementing Module | Associated Test | Status | Evidence / Verification |
|---|---|---|---|---|---|---|
| REQ-INV-01 | **No Fabricated Data**: No fake jobs, stats, or metrics. | Directive §3.1, §3.2 | `jovsi.api.routers.metrics`, `jovsi.adapters.db` | `tests/e2e/test_vertical_slice.py` | VERIFIED | Metrics computed strictly via SQL queries on `events`, `evidence`, and `rate_ledger`. |
| REQ-INV-02 | **No Fake Buttons or Pages**: All 8 screens fully functional, zero placeholder handlers. | Directive §3.3, §3.4 | `web/src/screens/*`, `web/src/components/*` | `tests/e2e/test_ui_vertical_slice.py` | VERIFIED | Real React SPA loaded in Playwright Chromium, buttons bound to API mutations. |
| REQ-INV-03 | **Correctness Over Speed**: Submitter cannot be called without valid GateReport. | Blueprint §3.1, §11 | `jovsi.services.submission`, `jovsi.adapters.portals.submitter` | `tests/unit/test_gate_15_checks.py` | VERIFIED | `SubmissionTicket` with HMAC required by submitter. |
| REQ-INV-04 | **Verified Actions Only**: `APPLIED_CONFIRMED` only reachable with evidence >= E2. | Blueprint §3.2, §12 | `jovsi.domain.state_machine`, `jovsi.services.submission` | `tests/unit/test_state_machine.py` | VERIFIED | Guard strictly verifies `evidence.level in ('E2', 'E3')`. |
| REQ-INV-05 | **Relevant Over Spam**: Hard rules, 70-point floor, daily quotas enforced in code. | Blueprint §3.3, §7, §11 | `jovsi.domain.eligibility`, `jovsi.domain.scoring`, `jovsi.domain.gate` | `tests/unit/test_scoring.py`, `tests/unit/test_gate_15_checks.py` | VERIFIED | Score < floor transitions to `BELOW_THRESHOLD`. |
| REQ-INV-06 | **Truthful Representation**: Every claim/field must trace to verified Fact (`USER_SUPPLIED` or `USER_VERIFIED`). | Blueprint §3.4, §6 | `jovsi.domain.provenance`, `jovsi.domain.validators` | `tests/unit/test_mutation_corpus.py` | VERIFIED | 40-point deliberate mutation corpus caught by validator. |
| REQ-INV-07 | **Reliable Automation**: Role/label/test-id locators only; no XPath, no coordinates. | Blueprint §3.5, §10 | `jovsi.adapters.portals.form_filler`, `tests/lint/test_locators.py` | `tests/lint/test_locators.py` | VERIFIED | AST/regex scanner verifies zero `xpath=` or `mouse.click`. |
| REQ-INV-08 | **Safe Failure Recovery**: Crash/timeout after click moves to `SUBMISSION_UNCERTAIN`, never auto-retry. | Blueprint §3.6, §12 | `jovsi.services.submission` | `tests/failure/test_failure_matrix.py` | VERIFIED | `click_started_at` flag ensures uncertain state on crash. |
| REQ-INV-09 | **User Control on Sensitive Data**: Sponsorship, EEO, legal fields marked SENSITIVE; require explicit approval. | Blueprint §3.7, §10, §11 | `jovsi.domain.gate`, `web/src/screens/ApplicationReviewScreen.tsx` | `tests/unit/test_gate_15_checks.py` | VERIFIED | Check 9 flags unapproved sensitive fields as `NEEDS_USER`. |
| REQ-INV-10 | **Append-Only Event Log**: Audit history immutable; reject UPDATE/DELETE in database. | Blueprint §3.12, §5 | `jovsi.adapters.db.triggers`, `jovsi.adapters.db.models` | `tests/integration/test_db_immutability.py` | VERIFIED | SQLite trigger raises error on delete/update attempt. |

---

## 2. Domain & Application Pipeline

| ID | Requirement Description | Source | Implementing Module | Associated Test | Status | Evidence / Verification |
|---|---|---|---|---|---|---|
| REQ-DOM-01 | **19-State State Machine**: Exactly 28 legal transitions, with strict guards. | Blueprint §9 | `jovsi.domain.state_machine` | `tests/unit/test_state_machine.py` | VERIFIED | 19x19 matrix test asserts all illegal pairs raise `IllegalTransition`. |
| REQ-DOM-02 | **Fact Provenance Engine**: Lifecycle `ACTIVE`, `PROPOSED`, `REJECTED`, `SUPERSEDED`. | Blueprint §6 | `jovsi.domain.provenance`, `jovsi.domain.models` | `tests/unit/test_provenance.py` | VERIFIED | `PROPOSED` facts cannot be mapped to resume bullets. |
| REQ-DOM-03 | **Canonical Job Key**: `sha256(portal_key + native_id)` or `sha256(company + title + location)`. | Blueprint §5, §11 | `jovsi.domain.models` | `tests/integration/test_m1_profile_jobs.py` | VERIFIED | Duplicate submissions blocked at DB level by unique constraint. |
| REQ-DOM-04 | **Job Text Sanitizer**: Strip HTML, scripts, zero-width characters, NFKC normalisation, 30k char limit. | Blueprint §13 | `jovsi.adapters.sanitizer` | `tests/security/test_sanitizer.py` | VERIFIED | Sanitizes CSS-hidden text, zero-width tags, and malicious payloads. |
| REQ-DOM-05 | **Phase A Hard Constraints**: Degree level, grad years, min experience, work auth, certifications, deadline. | Blueprint §7 | `jovsi.domain.eligibility` | `tests/unit/test_eligibility.py` | VERIFIED | Evaluates hard constraints to `PASS`, `FAIL`, or `UNCERTAIN`. |
| REQ-DOM-06 | **Phase B Suitability Scoring**: 100-pt model (Skills 35, Exp 25, Edu 15, Role 15, Loc 10) + dynamic renormalisation. | Blueprint §7 | `jovsi.domain.scoring` | `tests/unit/test_scoring.py` | VERIFIED | Mathematical invariants verified: determinism, monotonicity, bounds. |
| REQ-DOM-07 | **Deterministic Resume Generator**: Rank facts by relevance, format into structured JSON. | Blueprint §8 | `jovsi.services.resume` | `tests/integration/test_pdf_roundtrip.py` | VERIFIED | Builds resume strictly copying verified fact text. |
| REQ-DOM-08 | **Factual Consistency Validator**: 6-step claim verification against active candidate facts. | Blueprint §6 | `jovsi.domain.validators` | `tests/unit/test_mutation_corpus.py` | VERIFIED | All 40 mutations caught with exact violation codes. |
| REQ-DOM-09 | **PDF Generation & Round-Trip Check**: Chromium/pypdf render and text extraction validation. | Blueprint §8 | `jovsi.services.resume` | `tests/integration/test_pdf_roundtrip.py` | VERIFIED | Rendered text extracted and matched character-for-character to JSON. |
| REQ-DOM-10 | **Pre-Submission Validation Gate**: 15 independent pure function checks. | Blueprint §11 | `jovsi.domain.gate` | `tests/unit/test_gate_15_checks.py` | VERIFIED | Produces `GateReport` over immutable `GateSnapshot`. |
| REQ-DOM-11 | **Package Hashing & Approval**: Hash covers resume, answers, URL, job content. | Blueprint §8, §12 | `jovsi.domain.models`, `jovsi.services.submission` | `tests/unit/test_gate_15_checks.py` | VERIFIED | Modifying any answer or resume bullet invalidates approval. |
| REQ-DOM-12 | **Rate Limiting & Ledger**: Atomic check-and-insert for global, portal, and company caps in user timezone. | Blueprint §11, §12 | `jovsi.adapters.db.models`, `jovsi.services.submission` | `tests/failure/test_failure_matrix.py` | VERIFIED | Rate ledger row committed before click; daily caps enforced. |

---

## 3. Automation, Mock Portal & Failure Testing

| ID | Requirement Description | Source | Implementing Module | Associated Test | Status | Evidence / Verification |
|---|---|---|---|---|---|---|
| REQ-AUT-01 | **Hostile Mock Portal**: Standalone portal on `127.0.0.1:8765` with ground-truth oracle and 11 fault modes. | Blueprint §10 | `mock_portal/server.py` | `tests/adapters/test_mock_portal_adapter.py` | VERIFIED | Verified oracle records matches at `/__admin/applications`. |
| REQ-AUT-02 | **Form Population & Read-Back**: Safe field population and read-back value verification. | Blueprint §10 | `jovsi.adapters.portals.form_filler` | `tests/adapters/test_mock_portal_adapter.py` | VERIFIED | Form filler populates fields, attaches PDF, and checks values. |
| REQ-AUT-03 | **DOM Drift Detection**: Form skeleton hash compared at inspection vs pre-click recheck. | Blueprint §10, §11 | `jovsi.adapters.portals.inspector`, `jovsi.domain.gate` | `tests/failure/test_failure_matrix.py` | VERIFIED | Altered form layout triggers Check 15 BLOCKED. |
| REQ-AUT-04 | **30-Scenario Failure Matrix**: Complete failure injection testing. | Blueprint §16 | `tests/failure/test_failure_matrix.py` | `tests/failure/test_failure_matrix.py` | VERIFIED | All 30 scenarios pass with ground truth verified against mock oracle. |
| REQ-AUT-05 | **Watchdog & Reconciler**: Background recovery for `SUBMISSION_UNCERTAIN` via status check. | Blueprint §12, §15 | `jovsi.services.submission` | `tests/failure/test_failure_matrix.py` | VERIFIED | Confirms via E3 status lookup without re-submitting. |

---

## 4. Frontend & User Experience

| ID | Requirement Description | Source | Implementing Module | Associated Test | Status | Evidence / Verification |
|---|---|---|---|---|---|---|
| REQ-UI-01 | **DESIGN.md Compliance**: Midnight command center, `#040506` canvas, Inter/GeistMono, `#ff6363` accent. | Directive §6, `DESIGN.md` | `web/src/index.css`, `web/tailwind.config.ts` | `tests/e2e/test_ui_vertical_slice.py` | VERIFIED | Raycast dark theme, key shadows, and typography tokens active. |
| REQ-UI-02 | **8 Functional Screens**: Overview, Discovery, Queue, Review, Tracker, Profile, Settings, Diagnostics. | Directive §7, Blueprint §14 | `web/src/screens/*` | `tests/e2e/test_ui_vertical_slice.py` | VERIFIED | All 8 screens fully functional, real API hooks, zero mock data. |
| REQ-UI-03 | **Gated Approval UI**: Approve button disabled unless GateReport is PASS for currently displayed hash. | Blueprint §14 | `web/src/screens/ApplicationReviewScreen.tsx` | `tests/e2e/test_ui_vertical_slice.py` | VERIFIED | Button disabled with explanatory tooltip on gate non-pass. |
| REQ-UI-04 | **Honest Status Display**: "Applied" reserved exclusively for `APPLIED_CONFIRMED`; `SUBMISSION_UNCERTAIN` labeled honestly. | Directive §3.2, Blueprint §14 | `web/src/components/StatusBadge.tsx` | `tests/e2e/test_ui_vertical_slice.py` | VERIFIED | Exact semantic mapping across all 19 domain states. |

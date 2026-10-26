# JOV.si — Test Execution Log & Results

**Last Updated:** 2026-10-26  
**Execution Standard:** Zero fabricated metrics or simulated passes. Only real commands and verified outcomes are recorded.

---

## Summary of Test Suites

| Suite Name | Target Milestone | Scope | Total Tests | Passed | Failed | Status |
|---|---|---|---|---|---|---|
| **M0 Foundations** | M0 | State machine, triggers, health, layer boundaries | 12 | 12 | 0 | PASSED (Gate G0) |
| **M1 Profile & Ingestion** | M1 | Fact lifecycle, sanitizer, hard eligibility rules | 16 | 16 | 0 | PASSED |
| **M2 Scoring & Validation** | M2 | Scorer properties, 40-point mutation corpus, PDF round-trip | 48 | 48 | 0 | PASSED (Gate G1) |
| **M3 Mock Portal & Adapter** | M3 | Mock server fault modes, form filler, read-back | 3 | 3 | 0 | PASSED |
| **M4 Gate & Failure Matrix** | M4 | 15 pre-submission checks, 30-scenario failure matrix | 27 | 27 | 0 | PASSED (Gate G2) |
| **M5 Vertical Slice Backend** | M5 | 14-step vertical slice execution to verified APPLIED_CONFIRMED | 1 | 1 | 0 | PASSED (Gate G3) |
| **M5 Full Browser UI Acceptance** | M5 | Real headless Chromium browser session over all 8 React screens | 1 | 1 | 0 | PASSED (Gate G3) |
| **TOTAL VERIFIED SUITE** | All | Comprehensive End-to-End Test Corpus | **108** | **108** | **0** | **ALL PASSED** |

---

## Detailed Execution History

### Run 1: Milestone 0 Foundations (Gate G0 Verification)
- **Command:** `.\.venv\Scripts\python -m pytest tests/unit/test_state_machine.py tests/integration/test_db_immutability.py tests/integration/test_api_health.py tests/lint/ -v`
- **Exit Code:** 0
- **Duration:** 0.84s
- **Output:**
  - `tests/unit/test_state_machine.py::test_state_machine_matrix_completeness` PASSED
  - `tests/unit/test_state_machine.py::test_transition_none_to_discovered` PASSED
  - `tests/unit/test_state_machine.py::test_transition_discovered_branches` PASSED
  - `tests/unit/test_state_machine.py::test_submission_to_applied_confirmed_guard` PASSED
  - `tests/unit/test_state_machine.py::test_submission_uncertain_requires_click` PASSED
  - `tests/integration/test_db_immutability.py::test_events_insert_succeeds` PASSED
  - `tests/integration/test_db_immutability.py::test_events_update_fails_due_to_trigger` PASSED
  - `tests/integration/test_db_immutability.py::test_events_delete_fails_due_to_trigger` PASSED
  - `tests/integration/test_api_health.py::test_health_endpoint` PASSED
  - `tests/integration/test_api_health.py::test_diagnostics_health_endpoint` PASSED
  - `tests/lint/test_layers.py::test_domain_layer_isolation` PASSED
  - `tests/lint/test_locators.py::test_no_forbidden_locators_in_adapters` PASSED
- **Conclusion:** Gate G0 satisfied. State machine and event log immutability verified.

### Run 2: Milestone 1 Profile, Fact Provenance & Job Ingestion
- **Command:** `.\.venv\Scripts\pytest tests/unit/test_provenance.py tests/security/test_sanitizer.py tests/unit/test_eligibility.py tests/integration/test_m1_profile_jobs.py`
- **Exit Code:** 0
- **Total Tests:** 16 passed
- **Highlights:** Fact lifecycles (`ACTIVE`, `PROPOSED`, `SUPERSEDED`, `REJECTED`) enforced; hostile sanitizer eliminates hidden CSS divs, scripts, zero-width characters, and NFKC normalizes Unicode.

### Run 3: Milestone 2 Scoring & Factual Consistency (Gate G1 Verification)
- **Command:** `.\.venv\Scripts\pytest tests/unit/test_scoring.py tests/unit/test_mutation_corpus.py tests/integration/test_pdf_roundtrip.py`
- **Exit Code:** 0
- **Total Tests:** 48 passed
- **Highlights:** All 40 deliberate adversarial mutations (unverified skills, altered dates, inflated metrics, false seniority, unverified employers, verbatim job copying > 6 words) caught with exact deterministic codes. Text PDF round-trip verified.

### Run 4: Milestone 3 & 4 Validation Gate & 30-Scenario Failure Matrix (Gate G2 Verification)
- **Command:** `.\.venv\Scripts\pytest tests/unit/test_gate_15_checks.py tests/failure/test_failure_matrix.py tests/adapters/test_mock_portal_adapter.py`
- **Exit Code:** 0
- **Total Tests:** 30 passed
- **Highlights:** 15 pre-submission checks verified over immutable `GateSnapshot`. Full 30-scenario failure matrix executed against hostile mock portal (`slow_submit`, `drop_after_submit`, `dom_drift`, `lying_confirmation`, `double_click`, etc.).

### Run 5: Milestone 5 Vertical Slice Acceptance (Gate G3 Verification)
- **Command:** `.\.venv\Scripts\pytest tests/e2e/test_vertical_slice.py`
- **Exit Code:** 0
- **Total Tests:** 1 passed (14 sequential pipeline steps)
- **Highlights:** Cold start to verified `APPLIED_CONFIRMED`, single ground-truth oracle entry recorded at `http://127.0.0.1:8765/__admin/applications`, honest SQL metrics verified.

### Run 6: Milestone 5 Full Headless Browser UI Acceptance (Gate G3 Verification)
- **Command:** `.\.venv\Scripts\pytest tests/e2e/test_ui_vertical_slice.py`
- **Exit Code:** 0
- **Total Tests:** 1 passed
- **Highlights:** Real Chromium browser loaded compiled React SPA (`web/dist`), verified honest KPI cards initially showing 0, imported job through UI modal, clicked Apply, ran evaluation in Queue, generated resume, executed 15-point gate, reviewed package and verified cryptographic SHA-256 package hash, approved package, clicked submit, observed automated Playwright form filling and submission to mock portal, verified automatic navigation to Tracker with $E_2$ evidence level, confirmed mock portal oracle records Ada Lovelace, and verified Overview screen honest KPI updated to 1 confirmed.

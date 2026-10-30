# JOV.si Repository Audit — Executive Summary

**Audit basis:** current working tree at `master`, audited 2026-10-27 (Asia/Kolkata). Application source was not modified. Existing working-tree changes were preserved.

## Overall condition

JOV.si is a runnable, well-tested local sandbox/prototype with a substantial domain model, real read-only job-source connectors, a provenance-oriented resume pipeline, and a functioning hostile mock-portal vertical slice. It is **not production-ready**. The passing suite proves many isolated contracts, but it does not prove production account isolation, real email delivery, real LLM operation, deployment reproducibility, or safe external submission.

The most serious issue is a confirmed authorization boundary failure for legacy records whose `candidates.user_id` is `NULL`: anonymous callers can retrieve those candidates, facts, applications, and application lists. The current database contains 143 users, 190 candidates, 68 jobs, 158 applications, 109 resumes, and 2 master documents; therefore this is not a theoretical migration-only case. Counts were inspected without exporting personal values.

## Verification summary

| Check | Result | Evidence |
|---|---|---|
| Backend suite | **219 passed** in 61.92s; 1,360 warnings | `.venv/Scripts/python.exe -m pytest -q` |
| Frontend build | **Passed**; Vite emitted a 594 KB minified JS chunk warning | `web/package.json:8`, `npm run build` |
| Frontend lint | **Passed with 28 warnings** | `web/package.json:9`, `npm run lint` |
| API/E2E startup | Verified by Playwright E2E server startup and health checks | `tests/e2e/test_ui_vertical_slice.py:69-86` |
| Live job-source health | Greenhouse, Lever, Ashby, SmartRecruiters, Jobicy, Arbeitnow, Remotive returned HTTP 200 during audit; this is connectivity only | `SourceRegistryService.check_all_sources_health`, `job_discovery.py:734-821` |
| LLM health | Gemini `gemini-2.5-flash`, **unconfigured**; deterministic fallback selected | `src/jovsi/services/llm.py:291-320`, live health command |
| Reference PDF | Present and used by the current regression test; generated PDF/download assertions pass | `storage/documents/68dd9203-93c2-4635-a0d9-6428d53432f7/...pdf`, `tests/integration/test_resume_pipeline_e2e.py:189-247,252-321` |
| Anonymous legacy isolation | **Failed** in a fresh isolated DB: candidate, facts, application, and application list returned 200 | Reproduction recorded in `TEST_RESULTS.md` as `SEC-001` |

## Significant-feature status counts

Primary statuses use the required taxonomy. Counts below cover 39 significant features in `REPOSITORY_INVENTORY.md`.

| Status | Count |
|---|---:|
| FV | 5 |
| IU | 11 |
| PF | 12 |
| BR | 3 |
| MO | 1 |
| DC | 2 |
| NI | 2 |
| BC | 2 |
| BA | 1 |
| **Total** | **39** |

## Critical and high-severity findings

| ID | Severity | Status | Finding |
|---|---|---|---|
| SEC-001 | P0 Critical | BR | `NULL user_id` records bypass ownership checks. Anonymous access to legacy candidate/application data was reproduced. |
| SEC-002 | P0 Critical | PF | Password-reset tokens are returned as `_test_token` by the production route; no SMTP/email-delivery path exists. |
| APP-001 | P0 Critical | BR | Gate validation fails open on resume/cover-letter validator exceptions and inserts fabricated defaults (`experience_years=3`, `legal_attestation=agree`). |
| APP-002 | P0 Critical | BR | Approval is not bound to the authenticated user and edits do not revoke/recompute approval; submit trusts the stored approval hash instead of recomputing the current package. |
| DATA-001 | P1 High | MO | Normal authenticated UI opens a prefilled “Mock Acme Corp” job form and can insert it into ordinary job data. |
| RES-001 | P1 High | PF | Parser supplies invented fallback education/experience values when extraction is incomplete. |
| JOB-001 | P1 High | PF | Live discovery ignores the selected UI geography because `handleDiscoverLive` omits `location`; connectors also use hard-coded employer lists. |
| AUTH-003 | P1 High | PF | Session cookie is `secure=False`, CSRF protection is absent, and rate limiting trusts client-controlled `X-Forwarded-For`. |
| CFG-001 | P1 High | NI | `pyproject.toml` omits runtime imports (`pydantic-settings`, `python-docx`, `python-multipart`); no Alembic configuration or migration directory exists. |
| OPS-001 | P1 High | PF | Diagnostics reports a synthetic worker heartbeat and `queue_depth: 0`; `WorkQueue` has no runtime worker/scheduler. |

## Required answers

1. **Authentication/user isolation:** basic registration/login/session tests pass, but user isolation is **not safe** for legacy `NULL user_id` records; SEC-001 is confirmed.
2. **Resume import/fact verification:** implemented and tested for PDF/DOCX/TXT backend paths, with proposed facts; frontend accepts only `.pdf,.txt`, and parser fallback fabrication makes the end-to-end feature **PF**.
3. **Generated PDFs/downloads:** current regression tests produce valid `%PDF-` bytes, correct MIME types, filenames, and Blob downloads; generated artifacts are rendered on demand rather than persisted as PDF files. Status **FV for the tested path**, with RES-002 storage/reproducibility risk.
4. **Genuine job discovery:** seven public endpoints were reachable during this audit; connector output and source attribution exist, but employer coverage is hard-coded and live health checks only prove HTTP 200. Status **PF/IU by connector**, not comprehensive discovery.
5. **Location filters:** normalized facet/search tests pass, but live discovery does not receive UI location filters and no saved geography preference drives a default. Status **PF**.
6. **LLM provider/model:** provider `gemini`, model `gemini-2.5-flash`; configuration is unconfigured and no real provider call succeeded. Mocked provider tests pass; live integration is **BC**.
7. **Nonfunctional/misleading controls:** direct route navigation/history, source-management authorization, diagnostics reset authorization, real email recovery, external portal submission, and some error/loading paths are incomplete; see `UI_WIRING_MATRIX.md`.
8. **Mock/dead code:** the normal job-import form contains mock data; `WorkQueue` is unreferenced; `PortalPolicyDB` is unused; root `herovid*.mp4` files are not loaded by the UI; several historical audit documents contradict the current tree.
9. **Credentials/permissions blockers:** Gemini and Adzuna credentials are absent; external submission is intentionally blocked by the loopback safety policy.
10. **Existing tests:** the current `.venv` suite passes 219 tests, but tests include default-database mutations and do not cover the reproduced `NULL user_id` case.

## Five most important next steps

1. Enforce mandatory authenticated ownership and migrate/ quarantine legacy orphan records before exposing any private endpoint; add anonymous and orphan-row tests.
2. Remove token responses and implement a real email provider abstraction; harden cookies, CSRF, proxy IP handling, and production configuration.
3. Make the gate fail closed, remove fabricated form defaults, bind approvals to the authenticated user, and recompute/invalidate package hashes after every mutation.
4. Replace normal-path mock job defaults with empty-state UX; connect the source registry and UI geography/preferences to real discovery and server-side filtering.
5. Make the runtime reproducible: declare all imports, add migrations, isolate every test DB, implement/disable honestly the worker and artifact-storage paths, and add production-like authorization/download regression tests.

Detailed findings and evidence are indexed in the documents below.

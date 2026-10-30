# JOV.si Dependency-Ordered Implementation Roadmap

The roadmap fixes correctness/security before cosmetic work. Each item includes affected modules, required tests, acceptance criteria, and definition of done.

## P0 — security and package correctness

### R0.1 Close orphan-record access

**Findings:** SEC-001, SEC-003.  
**Modules:** `api/dependencies.py`, `api/routers/candidates.py`, `applications.py`, `metrics.py`, `jobs.py`, `adapters/db/models.py`, migration system.

**Change:** Require authenticated users for private candidates, facts, documents, applications, metrics, settings, source administration, and diagnostics. Treat `user_id=NULL` rows as quarantined/non-addressable, not an anonymous tenant. Add an explicit migration/reporting path for legacy rows; do not silently attach personal data to an arbitrary account.

**Tests:** anonymous/orphan matrix for every private endpoint; two-account tests with orphan rows; direct ID, list, download, mutate, and metrics cases.  
**Acceptance:** all orphan/private calls return 401/404; authenticated users see only their own records; empty anonymous workspace contains no legacy data.  
**Done:** migration reviewed, tests pass in isolated DB, no private route uses optional auth.

### R0.2 Remove secret-returning reset path and add mail abstraction

**Findings:** SEC-002; email delivery NI.  
**Modules:** `services/auth.py`, `api/routers/auth.py`, `config.py`, new mail adapter, frontend auth modal.

**Change:** never return reset/verification tokens; send links through a provider or local test sink. Normalize configuration and make registration verification policy explicit.

**Tests:** mail-sink delivery, token single-use/expiry, response schema secret scan, enumeration equality, rate limit through trusted proxy configuration.  
**Acceptance:** no token appears in JSON/log/frontend; reset works only through captured mail link.

### R0.3 Make gate and approval fail closed

**Findings:** APP-001, APP-002, SEC-007/008.  
**Modules:** `applications.py`, `services/submission.py`, `domain/gate.py`, `application_service.py`, resume/cover-letter update paths.

**Change:** validator exceptions produce BLOCKED; remove all factual/legal defaults; bind `approved_by` to authenticated user; canonicalize and recompute the current package at gate, approval, and submit; revoke approval on any content/answer/job change; persist immutable package/version IDs.

**Tests:** mutation after gate/approval, validator exception injection, missing experience/work-auth/legal answer, client approver spoof, stale ResumeDB version, concurrent approval/submit, hash mismatch.  
**Acceptance:** no content mutation can submit under an old approval; unknown answers block; no synthetic answer can enter a package.

## P1 — core product functionality

### R1.1 Make resume ingestion evidence-only

**Findings:** RES-001/003/004/006.  
**Modules:** `resume_parser.py`, `candidates.py`, `ResumeImportWorkflow.tsx`, `models.py`.

**Change:** replace invented parser fallbacks with nullable/proposed unknowns; add size/signature limits, DOCX UI support, explicit scan/OCR state, master-version pointer, fact supersession, and durable storage abstraction.

**Tests:** malformed/empty/encrypted/oversized/scanned PDF, DOCX browser upload, missing education/experience, repeated upload, replacement/deletion/restore, account isolation.

### R1.2 Make artifact generation durable and hash-bound

**Findings:** RES-002/007/008/009.  
**Modules:** `services/resume.py`, `applications.py`, storage adapter, `ResumeDB`/new artifact model, frontend download client.

**Change:** persist PDF/DOCX bytes or content-addressed storage, renderer/version metadata, cover-letter versions, and exact approved bytes; remove placeholder contact fallbacks.

**Tests:** restart/download, hash equality, page overflow/Unicode, PDF/DOCX/ZIP MIME, browser Blob, error JSON not saved as file.

### R1.3 Connect source registry and geography to discovery

**Findings:** JOB-001, source mismatch, DATA-001.  
**Modules:** `job_discovery.py`, `jobs.py`, `JobDiscoveryScreen.tsx`, source models, preferences.

**Change:** remove Mock Acme defaults from normal path; make source registry authoritative; pass country/state/city/work mode/remote scope to discovery; preserve freshness/expiry/source attribution; define onboarding geography when preferences are absent.

**Tests:** UI-to-live-discovery request contract, country exclusion (including Korean/non-target fixtures), remote scope, expired/deadline, duplicate source records, connector schema failure/unavailable state.

## P2 — application workflow

### R2.1 Finish portal auth/manual handoff honestly

**Modules:** `portal_auth.py`, `applications.py`, portal adapter interfaces, UI review screen.

**Change:** either implement encrypted per-user Playwright storage state with expiry/consent/portal policy or label all external portals manual-only. Persist proof refs/evidence before confirmed reconciliation.

**Tests:** pause/resume, session expiry, DOM drift, account separation, proof hash/evidence transition.

### R2.2 Enforce all rate caps and policies

**Modules:** `submission.py`, `gate.py`, `RateLedgerDB`, settings route/UI.

**Change:** global/portal/company atomic quotas, timezone-aware date, explicit environment-only safety flags, no wildcard UI allowlist.

**Tests:** concurrent submissions, each cap, timezone rollover, policy-denied host, L0/L1/L2 transitions.

## P3 — UX/integration completeness

### R3.1 Add real routing and honest states

**Modules:** `App.tsx`, nav, all screens, Vite/FastAPI static fallback.

**Change:** route every actual screen and review ID; support refresh/back/forward; add loading/error/empty/unavailable states rather than console-only catches.

### R3.2 Complete account/settings/email/source workflows

**Modules:** settings/auth/source routes and screens.

**Change:** account-gated source administration, persisted user preferences including geography, email verification/recovery UI, source health semantics that distinguish HTTP reachability from verified ingestion.

## P4 — quality and cleanup

### R4.1 Reproducible runtime

Declare all runtime dependencies, add lock/migration tooling, isolate every test DB, add CI, and document persistent storage/worker startup. Replace deprecated UTC calls with aware datetimes.

### R4.2 Visual/accessibility/performance pass

Restore or commit the authoritative design spec, reconcile tokens, test themes/video/reduced motion at 390/768/1024/1440, fix lint warnings, split the large frontend chunk, and add keyboard/focus/ARIA tests.

### R4.3 Safe cleanup

After reference proof, classify/remove root hero duplicates, stale compatibility aliases, unused policy/work-queue code, and superseded audit claims. Preserve mock portal and test fixtures.

## Definition of production readiness

All P0/P1 acceptance tests pass in isolated environments; no private endpoint accepts anonymous orphan access; no secret/token enters API responses; generated packages are durable and hash-bound; real sources and filters report unavailable honestly; LLM state is explicit; external submission remains disabled unless a permitted adapter has live contract/evidence tests; empty data produces honest empty UI; deployment and migrations are reproducible.

# JOV.si Repository Inventory and Architecture Map

## Repository state

`git status --short --branch` reported branch `master` with modified `jovsi.db`, eight application/frontend source files, and untracked `opencode.jsonc` plus `tests/integration/test_resume_pipeline_e2e.py`. Those changes were treated as user work and not overwritten.

The repository has no `AGENTS.md`, no `DESIGN.md` file despite references in `README.md:11,36`, no `alembic.ini`, no Alembic migration directory, no Docker/deployment manifest, and no checked-in CI workflow found by repository search.

## Technology inventory

| Area | Actual implementation | Evidence | Status |
|---|---|---|---|
| Frontend | React 19.3 + TypeScript 6 + Vite 8 + Tailwind 3.4 | `web/package.json:12-32` | FV (build) |
| Frontend navigation/state | One SPA with `activeTab` React state; no router or URL route registry | `web/src/App.tsx:20-62` | PF |
| Styling | CSS variables, Tailwind aliases, light/dark theme provider, Geist Sans/Instrument Serif | `web/src/design/tokens.css`, `web/tailwind.config.ts:8-62` | PF |
| Motion/icons | `motion` and `lucide-react` | `web/package.json:16-18`; screens/components | IU |
| Backend | FastAPI app with lifespan DB initialization | `src/jovsi/api/main.py:19-32` | FV (startup tests) |
| ORM/database | SQLAlchemy 2, SQLite default, WAL + foreign keys; PostgreSQL URL is not separately verified | `src/jovsi/adapters/db/session.py:15-34` | PF |
| Schema changes | `create_all` plus silent SQLite `ALTER TABLE` blocks; no versioned migrations | `session.py:37-110` | NI |
| API routers | Auth, candidates, jobs, applications, metrics, settings | `main.py:76-82`; router files | IU |
| Domain | State machine, eligibility, scoring, provenance, gate, validators | `src/jovsi/domain/*.py` | IU |
| Background jobs | `WorkQueue` model/service only; no worker loop/scheduler starts | `src/jovsi/worker/queue.py:12-90` | DC |
| LLM | Gemini REST client plus deterministic fallback/hybrid service | `src/jovsi/services/llm.py:97-320` | BC/PF |
| Resume/document generation | pypdf fallback, Playwright PDF renderer, python-docx, ZIP handoff | `src/jovsi/services/resume.py`; `planning.py` | PF |
| Browser automation | Playwright adapters and local hostile mock portal | `src/jovsi/adapters/portals/`; `mock_portal/server.py` | FV in sandbox; BA externally |
| Authentication | PBKDF2 password hashes, hashed session tokens, reset/verification token tables, cookie sessions | `services/auth.py`; `routers/auth.py` | PF |
| File storage | Relative `storage/documents/<candidate_id>`; generated PDF bytes are not persisted | `routers/candidates.py:437-442`; `applications.py:709-742` | PF |
| Email | No SMTP/provider client or send operation found | repository search; `routers/auth.py:195-202` | NI |
| Observability | Basic health/diagnostics JSON; no structured logging/metrics backend | `api/main.py:150-200` | PF |
| Deployment | README commands only; no container/CI/deployment manifest | `README.md:47-105` | NI |

## Actual data flow

```text
Browser SPA
  -> relative /api/v1 requests (Vite proxy in dev; FastAPI static mount in build)
  -> FastAPI router
  -> optional/current-user dependency + SQLAlchemy Session
  -> service/domain logic
  -> SQLite tables and relative storage/documents files

Resume upload
  file -> parser -> DocumentDB + PROPOSED FactDB rows -> UI confirmation
  -> ACTIVE verified facts -> evaluation/scoring -> ResumeDB JSON
  -> render PDF/DOCX on request -> HTTP bytes -> browser Blob download

Job discovery
  UI -> /jobs/discover -> hard-coded connector classes -> public HTTP feeds
  -> sanitize -> JobDB/JobLocationDB -> evaluation/ranking
  or UI/manual URL -> SSRF validator -> ATS/JSON-LD extraction -> persistence

Submission sandbox
  application -> gate snapshot -> ApprovalDB hash -> Playwright mock portal
  -> EvidenceDB -> state transition -> metrics/tracker
```

## Significant feature status register

| Feature | Primary status | Evidence / reason |
|---|---|---|
| API import/startup/health | FV | Playwright/API tests start app and health endpoints; `tests/e2e/*` |
| Full Python suite | FV | 219 passed in current `.venv` |
| Frontend production build | FV | `npm run build` passed |
| Basic registration/login/logout/session expiry | IU | `tests/security/test_authentication.py`; no production email delivery |
| Ownership isolation | BR | `SEC-001`; orphan-row anonymous access reproduced |
| Password reset/email verification | PF | Token lifecycle exists; delivery absent; reset token test escape exists |
| Frontend auth guards | PF | Guards hide tabs, but server/API and direct URLs are not uniformly protected |
| Master resume upload backend | PF | PDF/DOCX/TXT parser tests pass; file limits and parser fallbacks are unsafe |
| Master resume UI | PF | PDF/TXT only, simulated processing timer, no replace/delete/download workflow |
| Fact proposal/confirmation | IU | Proposed/active tests pass; edits are not provenance-revalidated on update |
| Resume deterministic generation | IU | Grounding and round-trip tests pass; no relevance evidence selection beyond ordering |
| Resume PDF/DOCX download | FV | Current integration tests verify bytes, MIME, filename, and endpoint |
| Cover-letter generation/export | PF | Deterministic template and mockable LLM; latest content is stored in ResumeDB without a version record |
| Greenhouse/Lever connectors | IU | Live HTTP health reached endpoints; fixed default employer lists |
| Ashby/SmartRecruiters connectors | IU | Adapter contract tests and live HTTP health; no live ingestion acceptance |
| Jobicy/Arbeitnow/Remotive feeds | IU | Live HTTP health; failures are swallowed in connectors |
| Adzuna connector | BC | Requires `ADZUNA_APP_ID` and `ADZUNA_API_KEY`; audit health reported UNCONFIGURED |
| LLM provider/tailoring integration | BC | Gemini model/client exists, but live health is unconfigured; mocked provider tests only |
| Email delivery/recovery | NI | No SMTP/provider adapter or send operation found |
| Source registry/probing UI/API | PF | Registry/probes exist but source-management routes are unauthenticated and discovery ignores registry selection |
| Location parser/database | IU | Dataset and parser tests pass; user preference/default geography is not wired |
| Server-side job search/facets | PF | Facet tests pass; incomplete filters and live-discovery mismatch remain |
| Eligibility hard rules | IU | Deterministic tests pass; API assigns synthetic defaults to discovered jobs |
| Suitability scoring | IU | Deterministic scoring tests pass; score is not a hiring probability, but UI wording needs review |
| Application creation/duplicate key | PF | Candidate ownership checked only for bound rows; jobs/import remain public |
| Application planning/manual handoff | PF | ZIP and field tests pass; missing legal facts default to assumed answers |
| External portal auth handoff | IU | State/session/anti-tamper unit tests pass; no real portal session lifecycle verified |
| Pre-submit gate | BR | Fail-open exception handling and fabricated values in `applications.py:1453-1501` |
| Approval/submission binding | BR | Stale package/approval and client-supplied approver issues (`APP-002`) |
| Local mock submission | FV | E2E/failure matrix reaches mock evidence; intentionally sandbox-only |
| Real-world submission | BA | `ALLOW_REAL_SUBMISSION=False`, loopback allowlist, unsupported external portal detector |
| Tracker/reconciliation | PF | State/events/UI exist; proof reference is accepted but not persisted as EvidenceDB in resolve endpoint |
| Metrics | IU | SQL-backed counts pass; orphan rows contaminate anonymous scope and diagnostics are synthetic |
| Settings persistence | PF | Per-user values persist, but module-global safety values and UI `['*']` allowlist are unsafe |
| Visual design/themes/media | PF | Rendered QA assets and build exist; missing DESIGN.md and token/reference mismatch |
| Normal-path mock/demo data | MO | Job Discovery defaults to Mock Acme Corp; queue has mock fallbacks |
| Work queue/worker | DC | Service/table unreferenced and diagnostics claim heartbeat/zero depth |
| Root hero video assets | DC | `herovid.mp4`/`herovidlight.mp4` are not referenced; UI loads `web/public/media/*` |
| Deployment/migrations | NI | No migration/deployment artifacts; dependency manifest incomplete |

## Commands and startup

Documented startup is `uvicorn mock_portal.server:app --host 127.0.0.1 --port 8765` and `uvicorn jovsi.api.main:app --host 127.0.0.1 --port 8000` (`README.md:69-83`). Tests use isolated engines for most fixtures but several current integration tests call `init_db()` against the configured default database. See `TEST_RESULTS.md`.

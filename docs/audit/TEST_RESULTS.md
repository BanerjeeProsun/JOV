# JOV.si Audit Test Results

## Commands executed

| Command | Result |
|---|---|
| `git status --short --branch` | `master`; modified database and application/frontend files; untracked audit-related test/config files listed in Executive Summary |
| `python -m pytest -q` | Failed before collection: host Python `C:\Python314\python.exe` has no pytest |
| `.venv/Scripts/python.exe -m pytest -q` | **219 passed**, 1,360 warnings, 61.92s |
| `npm run build` in `web` | **Passed**; `tsc -b && vite build`; warning for 594.47 KB minified JS chunk |
| `npm run lint` in `web` | **Passed with 28 warnings**, 0 errors |
| `.venv/Scripts/python.exe -c` runtime imports | FastAPI, Pydantic Settings, docx, multipart, Playwright, pypdf imports succeeded |
| LLM health command | `gemini` / `gemini-2.5-flash`; `configured=false`, `status=unconfigured` |
| Live source health command | 7 public connectors returned `HEALTHY` HTTP responses during this run; Adzuna `UNCONFIGURED`; manual `HEALTHY` |
| Isolated orphan access reproduction | Anonymous candidate/facts/application/application-list requests returned HTTP 200; finding `SEC-001` |

## Test quality observations

- The suite exercises state-machine, provenance, sanitizer, SSRF, connector parsing, PDF round-trip, account tests, mock portal failures, and a Playwright UI vertical slice.
- Provider tests mock Gemini HTTP calls; no successful real LLM call was made.
- Connector tests use recorded/mocked responses. The live health call checks status code, not schema correctness or job-result fidelity.
- `tests/integration/test_resume_pipeline_e2e.py:31-43` calls `init_db()` without an isolated engine. Other tests also call the default database path. Running the suite therefore can write test users/jobs/applications/resumes to tracked `jovsi.db`; the audit did not reset or revert it.
- The current full run reports deprecation warnings for `datetime.utcnow()` throughout auth, DB, API, and submission paths, plus Starlette/httpx compatibility warnings.
- Browser tests use the local mock portal and do not submit to real employers.

## Reproduction: SEC-001

1. Create a fresh temporary SQLite database with `init_db(engine)`.
2. Insert a `CandidateDB` with `user_id=NULL`, a child `FactDB`, a `JobDB`, and an `ApplicationDB`.
3. Override FastAPI `get_db` with that temporary session factory.
4. Call anonymously:
   - `GET /api/v1/candidates/{candidate_id}` -> **200**
   - `GET /api/v1/candidates/{candidate_id}/facts` -> **200**
   - `GET /api/v1/applications/{application_id}` -> **200**
   - `GET /api/v1/applications` -> **200**, list contains the orphan application
5. Root cause: `candidates.py:35-47` and `applications.py:50-62` only reject foreign access when `candidate.user_id is not None`; list queries explicitly select `user_id IS NULL` for anonymous callers (`applications.py:143-148`).

## Coverage gaps requiring regression tests

1. Anonymous access to every private endpoint when records have `NULL user_id`.
2. Authenticated user access to legacy orphan rows.
3. Reset-token absence from all production API responses and logs.
4. Email send/delivery and verification-link expiry using a local mail sink.
5. CSRF, secure-cookie, proxy-header, and session fixation behavior.
6. Resume parser rejection when required facts are missing; no invented fallback values.
7. DOCX upload from the browser and oversized/encrypted/malformed uploads.
8. Package hash changes after resume, cover-letter, or field edits; approval revocation.
9. Gate validator exceptions must block, never pass.
10. `Discover Live Jobs` must transmit selected country/city/work mode filters.
11. Empty database must not show Mock Acme or fallback candidate labels.
12. Direct URL refresh/history behavior for every user-facing workspace state.
13. Source-registry authorization and provider-registry-driven discovery.
14. Actual PDF/DOCX download bytes through browser automation, including JSON error responses.

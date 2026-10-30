# Security and Data-Integrity Audit

## Confirmed risks

| ID | Severity | Status | Evidence |
|---|---|---|---|
| SEC-001 | P0 | BR | Orphan `NULL user_id` candidate/fact/application access returned 200 anonymously; `candidates.py:35-47`, `applications.py:50-62,143-148`. |
| SEC-002 | P0 | PF | Reset token returned in API response for real users; `auth.py:195-202`; no mail provider. |
| SEC-003 | P1 | PF | Unauthenticated job import/source-management/diagnostic reset mutates shared state; `jobs.py:29-175,828-899`, `main.py:181-200`. |
| SEC-004 | P1 | PF | Settings endpoint mutates process-global safety flags and UI can send wildcard host allowlist; `settings.py:77-90`, `SettingsScreen.tsx:113-123`. |
| SEC-005 | P1 | PF | `secure=False` cookie and default development secret; `auth.py:43-52`, `config.py:62-66`. |
| SEC-006 | P1 | PF | Trusts first `X-Forwarded-For` value for auth rate limiting; `auth.py:35-40`. |
| SEC-007 | P1 | PF | Gate exception paths are fail-open; fabricated legal/experience values can pass validation; `applications.py:1453-1501`. |
| SEC-008 | P1 | PF | Approval/package hash can remain valid after document/content edits; `applications.py:553-651,867-928`, `submission.py:127-202`. |
| SEC-009 | P1 | PF | Test suite writes to configured default `jovsi.db` from non-isolated tests; `tests/integration/test_resume_pipeline_e2e.py:31-43`. |

## Fabricated or synthetic functionality

- `JobDiscoveryScreen.tsx:111-123` prepopulates a normal import modal with “Mock Acme Corp”, a localhost portal URL, and a synthetic description. The E2E test relies on this (`tests/e2e/test_ui_vertical_slice.py:116-126`), but the same default is available to ordinary users. Status `MO`, finding `DATA-001`.
- `ApplicationQueueScreen.tsx:158-163` uses Mock Acme/Senior Software Engineer fallback display values when API fields are absent. This hides missing data rather than producing an honest error/empty state.
- `applications.py:1453-1456` and `1651-1655` use hard-coded `3`, `YES`, `NO`, and `agree` values in application planning/submission fallback paths.
- `main.py:168-178` reports `worker_heartbeat` as current time and `queue_depth: 0` without checking a worker or queue.
- `SourceRegistryService.get_registered_sources` can label untested registry rows `is_live=True` (`job_discovery.py:616-642`), while live health is a separate HTTP probe.

## Positive controls retained

The sanitizer strips scripts/hidden elements/bidi controls and caps length (`sanitizer.py:33-70`); generic URL import validates DNS/IP and redirects (`ssrf.py:93-220`); passwords/tokens are hashed; the local submitter verifies HMAC and host allowlist; fact provenance and DB immutability tests exist. These controls should not be removed while fixing the failures above.

## Data-integrity acceptance criteria

An empty database must render empty states, no demo employer/candidate labels, no synthetic metrics, and no mock portal actions unless a test-only feature flag is explicit. Every generated claim and every sensitive answer must have active fact or explicit user approval provenance. Every “confirmed” submission must have an EvidenceDB artifact whose hash and target job match the application package.

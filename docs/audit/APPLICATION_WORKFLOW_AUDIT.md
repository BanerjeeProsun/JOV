# Application Workflow Audit

## Actual lifecycle

`POST /applications` creates `DISCOVERED` (`applications.py:80-133`). The implemented happy path is:

```text
DISCOVERED -> evaluate -> SHORTLISTED -> generate resume -> RESUME_GENERATED
-> gate -> READY_FOR_REVIEW -> approve -> APPROVED
-> submit -> SUBMISSION_IN_PROGRESS -> APPLIED_CONFIRMED or SUBMISSION_UNCERTAIN
```

The local mock portal is the only supported automated submission destination in the default safety configuration.

## Findings

| ID | Severity/status | Evidence | Observed behavior | Correction |
|---|---|---|---|---|
| APP-001 | P0 / BR | `applications.py:1480-1501` | Validator construction exceptions are caught and leave `resume_valid`/`cover_letter_valid` as `True`; `applications.py:1453-1456` inserts `3` years and `agree` attestation. | Fail closed; never synthesize factual/legal answers; require explicit candidate input and persist approval. |
| APP-002 | P0 / BR | `applications.py:1586-1607`; `submission.py:56-99,123-202`; update endpoints `applications.py:553-651,867-928` | `approved_by` comes from client payload; approval checks a stored gate report but does not recompute the current package; resume/letter/field edits do not revoke approvals or force a new gate. | Derive actor from current authenticated user; recompute canonical package at approve and submit; revoke old approvals on every package mutation; enforce one current package ID. |
| APP-003 | P1 / PF | `applications.py:1200-1233,1248-1267` | Package endpoint uses latest ResumeDB version, while PDF endpoint prefers `current_resume_id`; these can diverge. | Use a single immutable package/version selector everywhere. |
| APP-004 | P1 / PF | `applications.py:1319-1376`, `portal_auth.py:107-145` | Portal auth pause/resume is state-only; no Playwright storage-state lifecycle or external portal authentication handoff is actually wired. | Implement a per-user encrypted session-state vault with explicit consent, expiry, portal policy, and browser lifecycle tests; otherwise label feature manual-only. |
| APP-005 | P1 / PF | `submission.py:144-231`, `submitter.py:22-117` | Mock portal submission performs inspect/fill/click/evidence; external host is rejected by policy. Real portal mapping/authentication/submission is not verified. | Keep external mode disabled until each adapter is separately permitted, tested, and evidence-verified. |
| APP-006 | P2 / PF | `applications.py:1678-1707` | `proof_ref` is accepted by resolve endpoint but not stored as evidence; confirmed state can be manually asserted after an uncertain result. | Require and persist proof artifact/hash before E2 transition. |
| APP-007 | P1 / PF | `submission.py:133-142,175-184` | Only global rate cap is enforced in the submission service; portal/company ledgers are not inserted there despite settings fields. | Enforce all configured caps atomically with unique scope/date constraints. |
| APP-008 | P1 / PF | `applications.py:1621-1675` | Submit checks state and unused approval but not `settings.ALLOW_REAL_SUBMISSION` directly; safety is delegated to adapter allowlist. | Add explicit mode/portal-policy check at API boundary and return an honest unavailable state. |
| APP-009 | P1 / PF | `ApplicationState`/`StateMachine` | Nested branch in `state_machine.py:244-250` makes `LINK_INVALID`/`DUPLICATE_BLOCKED` guard branches unreachable under the surrounding `MANUAL_HANDOFF` condition. | Refactor transition guard branches and add mutation tests for each transition. |

## What is verified

`tests/e2e/test_vertical_slice.py`, `tests/e2e/test_ui_vertical_slice.py`, and `tests/failure/test_failure_matrix.py` exercise the local hostile mock portal, HMAC ticket, rate/approval failures, DOM drift, lying confirmation, and evidence states. This is strong sandbox evidence, not external integration evidence.

## External portal authentication distinction

JOV account sessions use `jovsi_session` (`routers/auth.py:31-52`). Portal auth state is represented by application state and a Fernet helper (`portal_auth.py:29-45`), but no external stored Playwright session state is used by the current route. The two concepts are logically separated; the actual portal session feature is incomplete.

# JOV.si Authentication and Account-Security Audit

## Status conclusion

Basic credentials, password hashing, session revocation, expiry, and two owned-account tests are implemented. Authentication/user isolation as a product guarantee is **BR** because legacy orphan rows are intentionally exposed to anonymous callers.

## Evidence

| Area | Evidence | Result |
|---|---|---|
| Password hashing | `services/auth.py:84-103` PBKDF2-HMAC-SHA256 with per-password salt and constant-time compare | IU; add migration/rehash policy |
| Email normalization | `auth.py:123-124` strips/lowercases | IU; validation only checks `@`, not robust email syntax |
| Session storage | `auth.py:198-248` stores SHA-256 token hash, idle/absolute expiry, revocation | IU; tests pass |
| Cookie | `routers/auth.py:43-52` HTTP-only, SameSite=Lax, **secure=False** | P1 risk in any HTTPS deployment |
| Rate limiting | `auth.py:56-79`, auth routes | PF; in-process only, trusts `X-Forwarded-For` from client (`auth.py:35-40`), not distributed |
| Reset flow | `routers/auth.py:181-202` | BR/P0: `_test_token` is returned for existing accounts; no email sender exists |
| Email verification | token DB/service exists (`auth.py:358-400`) | PF: token creation is not wired to registration mail delivery |
| CSRF | no CSRF token/middleware found | PF; SameSite mitigates some cross-site POSTs but is not a complete deployment control |
| Backend route guards | most private routes use optional user plus ownership helper | BR for orphan rows; jobs/source/diagnostics mutation routes are public |
| Frontend guards | `App.tsx:20-138`, `AuthRequiredGate` | IU only; frontend guards cannot enforce API security and no real URL route guard exists |
| Display name | `OverviewScreen.tsx:94-106`, `AuthContext.tsx:26-49` | IU for authenticated owned users; legacy/sandbox fallback can still show candidate data |
| File access | document/application helpers check parent candidate only when linked | BR for `user_id=NULL` parent rows |

## Confirmed SEC-001 reproduction

Fresh isolated DB, orphan candidate/application, anonymous client:

```text
GET /api/v1/candidates/{id}          200
GET /api/v1/candidates/{id}/facts    200
GET /api/v1/applications/{id}        200
GET /api/v1/applications             200 (orphan application included)
```

Root cause is the conditional ownership logic in `candidates.py:35-47` and `applications.py:50-62`, combined with explicit anonymous `IS NULL` queries in `applications.py:143-148` and `metrics.py:29-36`.

## Other security/integrity findings

- **SEC-002 P0:** password reset secrets cross the API boundary (`auth.py:195-202`) and are available to the frontend client type (`web/src/api/client.ts:135-138`).
- **SEC-003 P1:** `POST /api/v1/jobs/sources/employers`, source probing, job import, mock diagnostics, and diagnostics reset have no mandatory auth dependency (`jobs.py:798-899`, `main.py:181-200`). This enables shared-database pollution and mock-state manipulation.
- **SEC-004 P1:** `SettingsScreen.tsx:113-123` sends `submit_host_allowlist: ['*']` when real submission is enabled; settings API writes process-global safety settings (`settings.py:77-90`). Even if submitter policy checks remain, the UI exposes an unsafe configuration representation.
- **SEC-005 P1:** external portal credentials/session vault has a deterministic key derived from `SECRET_KEY` (`portal_auth.py:29-45`); the default secret is an insecure development string (`config.py:62-66`) and production startup does not reject it.
- **SEC-006 P2:** `resolve_uncertain` accepts `proof_ref` but does not persist it as `EvidenceDB` (`applications.py:1678-1707`).

## Required security tests

Add orphan-row, unauthenticated mutation, reset-token response, secure-cookie/CSRF, proxy-header, settings allowlist, file authorization, package-staleness, and session-switching browser tests before production claims.

# JOV.si — Authorization & Ownership Matrix (AUTHZ)

This matrix defines the required access control policy for every endpoint in the JOV.si API.

---

## Endpoint Authorization Policy

| Endpoint | Method | Public / Private | Required Auth | Ownership Enforcement Query | Current Baseline Status | Target Status (M1) |
|---|---|---|---|---|---|---|
| `/health` | GET | Public | None | None (System status only) | **FV** | **FV** |
| `/diagnostics/health` | GET | Public (Dev) | None | None | **FV** | **FV** |
| `/api/v1/auth/register` | POST | Public | None | Normalizes email, hashes password, creates `UserDB` | **NI** | **FV** |
| `/api/v1/auth/login` | POST | Public | Rate-limited | Verifies password hash, issues `jovsi_session` | **NI** | **FV** |
| `/api/v1/auth/logout` | POST | Private | Session | Revokes `UserSessionDB`, clears cookie | **NI** | **FV** |
| `/api/v1/auth/me` | GET | Private | Session | `SELECT * FROM users WHERE id = current_user.id` | **NI** | **FV** |
| `/api/v1/auth/profile` | PATCH | Private | Session | Updates `display_name` on `current_user.id` | **NI** | **FV** |
| `/api/v1/auth/change-password` | POST | Private | Session | Validates current password, updates hash, revokes other sessions | **NI** | **FV** |
| `/api/v1/auth/forgot-password` | POST | Public | Rate-limited | Generic 200 response; creates hashed reset token in DB | **NI** | **FV** |
| `/api/v1/auth/reset-password` | POST | Public | Rate-limited | Validates unexpired single-use token; updates password hash | **NI** | **FV** |
| `/api/v1/auth/verify-email` | POST | Public | Token | Validates unexpired verification token; sets `is_verified=True` | **NI** | **FV** |
| `/api/v1/candidates` | GET | Private | Session | `SELECT * FROM candidates WHERE user_id = current_user.id` | **BR** (Global read) | **FV** |
| `/api/v1/candidates` | POST | Private | Session | Creates candidate bound to `current_user.id` | **BR** (Unowned) | **FV** |
| `/api/v1/candidates/{id}` | GET | Private | Session | `WHERE id = ? AND user_id = current_user.id` | **BR** (IDOR) | **FV** |
| `/api/v1/candidates/{id}/facts` | GET | Private | Session | Checks candidate ownership, returns facts | **BR** (IDOR) | **FV** |
| `/api/v1/candidates/{id}/facts` | POST | Private | Session | Checks candidate ownership, inserts fact | **BR** (IDOR) | **FV** |
| `/api/v1/facts/{id}/confirm` | POST | Private | Session | Joins `facts -> candidates` where `candidates.user_id = current_user.id` | **BR** (IDOR) | **FV** |
| `/api/v1/facts/{id}/reject` | POST | Private | Session | Joins `facts -> candidates` where `candidates.user_id = current_user.id` | **BR** (IDOR) | **FV** |
| `/api/v1/facts/{id}` | PUT | Private | Session | Joins `facts -> candidates` where `candidates.user_id = current_user.id` | **BR** (IDOR) | **FV** |
| `/api/v1/facts/{id}` | DELETE | Private | Session | Joins `facts -> candidates` where `candidates.user_id = current_user.id` | **BR** (IDOR) | **FV** |
| `/api/v1/candidates/{id}/master-resume` | GET | Private | Session | Checks candidate ownership | **BR** (IDOR) | **FV** |
| `/api/v1/candidates/{id}/resume/upload` | POST | Private | Session | Checks candidate ownership; binds uploaded document | **BR** (IDOR) | **FV** |
| `/api/v1/documents/{id}/download` | GET | Private | Session | Joins `documents -> candidates` where `candidates.user_id = current_user.id` | **BR** (IDOR) | **FV** |
| `/api/v1/documents/{id}` | DELETE | Private | Session | Checks document ownership | **BR** (IDOR) | **FV** |
| `/api/v1/jobs` | GET | Private/Public | Optional | Public read of active listings; personalized if session present | **FV** | **FV** |
| `/api/v1/jobs/discover` | POST | Private | Session | Personalizes ranking using candidate facts owned by `current_user.id` | **PF** | **FV** |
| `/api/v1/jobs/import` | POST | Private | Session | Sanitizes and imports job listing | **FV** | **FV** |
| `/api/v1/applications` | GET | Private | Session | `SELECT * FROM applications WHERE candidate_id IN (SELECT id FROM candidates WHERE user_id = current_user.id)` | **BR** (Global read) | **FV** |
| `/api/v1/applications` | POST | Private | Session | Verifies `candidate_id` belongs to `current_user.id` | **BR** (IDOR) | **FV** |
| `/api/v1/applications/{id}` | GET | Private | Session | Verifies application belongs to `current_user.id` | **BR** (IDOR) | **FV** |
| `/api/v1/applications/{id}/evaluate` | POST | Private | Session | Verifies application ownership | **BR** (IDOR) | **FV** |
| `/api/v1/applications/{id}/generate-resume` | POST | Private | Session | Verifies application ownership | **BR** (IDOR) | **FV** |
| `/api/v1/applications/{id}/cover-letter` | PUT | Private | Session | Verifies application ownership | **BR** (IDOR) | **FV** |
| `/api/v1/applications/{id}/gate` | POST | Private | Session | Verifies application ownership | **BR** (IDOR) | **FV** |
| `/api/v1/applications/{id}/approve` | POST | Private | Session | Verifies application ownership | **BR** (IDOR) | **FV** |
| `/api/v1/applications/{id}/submit` | POST | Private | Session | Verifies application ownership | **BR** (IDOR) | **FV** |
| `/api/v1/applications/{id}/resolve` | POST | Private | Session | Verifies application ownership | **BR** (IDOR) | **FV** |
| `/api/v1/metrics/summary` | GET | Private | Session | Aggregates metrics filtered to `current_user.id` | **BR** (Global counts) | **FV** |
| `/api/v1/settings` | GET | Private | Session | Returns user-specific settings | **PF** (Global settings) | **FV** |
| `/api/v1/settings` | PATCH | Private | Session | Persists settings for `current_user.id` | **PF** (Global settings) | **FV** |

# JOV.si — Authentication & Account Security Audit

## 1. Executive Summary & Existing State

| Workflow / Capability | Current Status | Evidence / Implementation Path | Risk & Deficiencies | Target State (M1) |
|---|---|---|---|---|
| **Account Registration** | **NI** (Not Implemented) | `src/jovsi/api/routers/candidates.py:34` | Anonymous candidates created without email or password | Real user registration with email, password hash, and display name |
| **Sign-In** | **NI** (Not Implemented) | Missing | Anyone can access any data without credentials | Cookie-based session creation with Argon2/PBKDF2 validation |
| **Sign-Out** | **NI** (Not Implemented) | Missing | No server session to invalidate | Session revocation and cookie clearance |
| **Email Verification** | **NI** (Not Implemented) | Missing | No email verification workflow | Cryptographic single-use token verification; BC status when SMTP unconfigured |
| **Password Reset** | **NI** (Not Implemented) | Missing | No recovery mechanism | Secure time-limited reset tokens; generic responses preventing enumeration |
| **Session Lifecycle** | **NI** (Not Implemented) | Missing | No sessions exist; stateless unauthenticated requests | Cryptographically random 256-bit session token, HttpOnly, SameSite=Lax |
| **Account Identity vs Candidate** | **BR** (Broken/Conflated) | `src/jovsi/adapters/db/models.py:46` (`CandidateDB`) | No `UserDB` exists; `CandidateDB` conflates account identity with resume data | Separate `UserDB` (account, credentials, display name) from `CandidateDB` |
| **Dashboard Greeting Identity** | **PF** (Partially Functional) | `web/src/screens/OverviewScreen.tsx:79` | Pulls candidate display name or defaults to 'Candidate' / 'My Profile' | Displays authenticated `user.display_name` persisted in DB |
| **Resource Ownership Enforcement** | **BR** (Broken / IDOR) | `candidates.py`, `applications.py`, `jobs.py` | All endpoints accept unauthenticated requests and trust client IDs without ownership checks | Every private resource queries `WHERE user_id = current_user.id` |
| **Two-Account Isolation** | **BR** (Zero Isolation) | All endpoints | Account A can view, edit, or delete Account B's resumes and applications | Complete cross-account isolation verified by automated tests |

---

## 2. Cryptographic & Session Specifications for M1

### Password Security
- Algorithm: Salted PBKDF2-HMAC-SHA256 with 600,000 iterations and 32-byte cryptographically secure random salt (or Argon2id via `cryptography` when available).
- Plaintext passwords never stored, logged, or serialized.
- Minimum password length: 8 characters.

### Session Architecture
- Session Cookie: `jovsi_session` with `HttpOnly`, `SameSite=Lax`, and `Secure` (in HTTPS / production).
- Session Token: 256-bit cryptographically random token (`secrets.token_urlsafe(32)`).
- Storage: Stored in `user_sessions` table with `user_id`, `created_at`, `expires_at`, and `revoked_at`.
- Lifetimes: Idle timeout (24 hours), absolute timeout (30 days).
- Invalidation: Sign-out updates `revoked_at = NOW()` and clears cookie with `Max-Age=0`.
- Rotation: New session ID issued upon successful sign-in.

### Protection Against Credential Attacks
- Rate Limiting: In-memory sliding window rate limiter for `/api/v1/auth/login` and `/api/v1/auth/register` (e.g. max 5 failed attempts per IP per 5 minutes).
- Account Enumeration Defense: Password reset request returns generic success message (`"If this email is registered, instructions have been sent"`) regardless of whether account exists.

---

## 3. Account Identity vs. Candidate Profile Architecture

```
+-----------------------------------------------------------+
|                        users                              |
|-----------------------------------------------------------|
| id (UUID, PK)                                             |
| email (String 255, Unique, Normalized lowercase)          |
| password_hash (String 255)                                |
| display_name (String 120, User-selected preferred name)   |
| is_verified (Boolean, Email verification status)          |
| is_active (Boolean, Default True)                         |
| created_at, updated_at                                    |
+-----------------------------------------------------------+
                             | 1
                             |
                             | 1
                             v
+-----------------------------------------------------------+
|                      candidates                           |
|-----------------------------------------------------------|
| id (UUID, PK)                                             |
| user_id (UUID, FK -> users.id, Unique, Indexed)          |
| timezone (String 64)                                      |
| is_synthetic (Boolean)                                    |
| created_at, updated_at                                    |
+-----------------------------------------------------------+
```

### Dashboard Greeting Invariant
- The dashboard greeting must strictly display:
  - `Welcome back, {user.display_name}.` when `display_name` is set.
  - `Welcome back.` when `display_name` is empty or unset.
- Display name is editable in Account Settings and updates immediately upon save and reload.
- Changing accounts switches the greeting and all associated data immediately.

---

## 4. Required Acceptance Tests for M1

1. `test_auth_registration_success_and_duplicate_email()`
2. `test_auth_login_success_and_wrong_password()`
3. `test_auth_session_cookie_expiry_and_revocation()`
4. `test_auth_password_reset_flow_prevents_enumeration()`
5. `test_auth_display_name_greeting_update()`
6. `test_auth_two_account_isolation_candidates()`
7. `test_auth_two_account_isolation_resumes()`
8. `test_auth_two_account_isolation_applications()`
9. `test_auth_two_account_isolation_evidence()`
10. `test_auth_rate_limiting_on_login()`

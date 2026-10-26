# JOV.si — Architecture Decision Records (ADRs)

---

## ADR-001: Product Naming, Namespace, and Environment Prefix
- **Status:** Accepted
- **Context:** The v1.0 specification contained conflicting references ("ARGON", "JOB.si", "JOV.si"). The prompt and blueprint explicitly mandate consistency.
- **Decision:** Use **JOV.si** consistently as the product name. Python package namespace is `jovsi`, database file name is `jovsi.db`, and all configuration variables use the `JOVSI_` prefix.
- **Consequences:** Eliminates confusion across UI, documentation, API schemas, and test suites.

---

## ADR-002: Layering Boundary and Pure Domain Logic
- **Status:** Accepted
- **Context:** Automation platforms often fail due to convenience shortcuts (e.g., API directly calling browser automation, domain models importing network clients).
- **Decision:** 
  - Dependencies point inward only: `api/` and `worker/` call `services/`; `services/` call `domain/` and `ports/`; `adapters/` implement `ports/`.
  - The `domain/` package contains zero I/O, no network calls, and no database queries.
  - Enforced by an automated architectural lint test (`tests/lint/test_layers.py`) which inspects Python AST imports.
- **Consequences:** All core business logic (eligibility, scoring, validation, state transitions) can be tested deterministically with zero database or browser setup.

---

## ADR-003: Database-Backed Work Queue with Optimistic Leases
- **Status:** Accepted
- **Context:** Introducing Redis or Celery adds deployment complexity and disconnects job queue states from relational state transactions.
- **Decision:** Use a database-backed `work_items` table in SQLite (with WAL mode enabled) and PostgreSQL. Workers acquire rows using atomic leases (`lease_owner`, `lease_until = now + 60s`, `idempotency_key`).
- **Consequences:** Guaranteed transactional consistency between state changes and next-stage enqueuing. Submit stage is explicitly marked non-retryable on lease timeout to prevent double-submits.

---

## ADR-004: 19-State Machine with Defined Recovery Exits
- **Status:** Accepted
- **Context:** Blueprint v1.0 only had 12 states and lacked key edge cases (e.g., below threshold, expired deadline, invalid link, paused login, duplicate blocked, submission uncertain exits).
- **Decision:** Implement the 19 states and 28 legal transitions defined in Blueprint v2.0 §9.
  - States: `DISCOVERED`, `ELIGIBILITY_CHECKED`, `REJECTED`, `EXPIRED`, `LINK_INVALID`, `AWAITING_USER_INPUT`, `SHORTLISTED`, `BELOW_THRESHOLD`, `RESUME_GENERATED`, `READY_FOR_REVIEW`, `MANUAL_HANDOFF`, `DUPLICATE_BLOCKED`, `APPROVED`, `SUBMISSION_IN_PROGRESS`, `APPLIED_CONFIRMED`, `SUBMISSION_UNCERTAIN`, `APPLICATION_FAILED`, `PAUSED_AUTH`, `WITHDRAWN`.
  - `SUBMISSION_UNCERTAIN` resolves strictly through reconciliation (E2/E3 evidence) or user confirmation, never by auto-retrying submission.
- **Consequences:** Complete state coverage prevents deadlocks and undefined states.

---

## ADR-005: Fact Provenance and Anti-Hallucination Engine
- **Status:** Accepted
- **Context:** AI generation risks hallucinating skills, inflated dates, or fabricated achievements on candidate resumes.
- **Decision:**
  - Fact status lifecycle: `ACTIVE`, `PROPOSED`, `REJECTED`, `SUPERSEDED`.
  - Only `ACTIVE` facts with provenance `USER_SUPPLIED` or `USER_VERIFIED` are eligible for resume inclusion or form answers.
  - Structured output required: Resumes are generated as structured JSON where every bullet must cite `{text, fact_ids[]}`. Bullets without fact citations are rejected automatically.
  - `FactualConsistencyValidator` checks entity coverage against an explicit skill ontology, verifies exact numbers/dates, checks contact info character-for-character, and blocks word copying (>6 words) from job descriptions.
- **Consequences:** Prevents unverified claims from reaching recruiters; guarantees 100% verifiable candidate claims.

---

## ADR-006: 15-Point Pre-Submission Gate & Cryptographic Submission Ticket
- **Status:** Accepted
- **Context:** Submitting is irreversible. A user approval must be strictly tied to the exact application payload and verified right before browser submission.
- **Decision:**
  - Package Hash: $H = \text{SHA-256}(\text{canonical\_json}(\text{resume}, \text{cover\_letter}, \text{answers}, \text{target\_url}, \text{job\_hash}))$.
  - 15 independent validation checks run over an immutable `GateSnapshot`.
  - Submitter requires a `SubmissionTicket` containing an HMAC signature generated exclusively by `SubmissionService`.
  - Pre-click recheck verifies live DOM skeleton hash, URL domain, rate caps, and approval validity in < 2s.
- **Consequences:** Impossible for UI shortcuts or stale pages to trigger an unapproved or drifted application.

---

## ADR-007: Release 1 Mock-Only Submission Sandbox
- **Status:** Accepted
- **Context:** Safety requirement prevents accidental or automated submissions to real external company career portals during development and testing.
- **Decision:**
  - `JOVSI_SUBMIT_HOST_ALLOWLIST` is restricted to `127.0.0.1:8765`.
  - The submitter adapter enforces this boundary; requests to external hosts are refused immediately.
  - Real job discovery (read-only) and structured imports are supported, while submissions stay sandboxed to the hostile mock portal until explicit subsequent milestone releases.
- **Consequences:** Absolute safety against unwanted external actions while thoroughly verifying automation and fault recovery against the local mock portal.

---

## ADR-008: Design System Tokens & Raycast UI Dark Mode
- **Status:** Accepted
- **Context:** UI must follow `DESIGN.md` rather than generic templates or random color palettes.
- **Decision:**
  - Dark-near-black palette: Canvas (`#040506`), Card (`#07080a`), Recessed (`#111214`), Graphite (`#1b1c1e`), Secondary Text (`#9c9c9d`), Muted (`#6a6b6c`), Primary Text (`#ffffff`), Mist Button (`#e6e6e6`), Iron Text (`#454647`), Coral Brand Accent (`#ff6363`).
  - Key shadow stack: `rgba(255,255,255,0.05) 0px 1px 0px 0px inset, rgba(255,255,255,0.25) 0px 0px 0px 1px, rgba(0,0,0,0.2) 0px -1px 0px 0px inset`.
  - 8px base spacing grid, 1200px max width container, Inter for UI, Geist Mono for metadata.
- **Consequences:** Apple-level polish with an austere, developer-tool dark aesthetic.

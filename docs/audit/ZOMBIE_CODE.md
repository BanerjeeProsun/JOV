# JOV.si — Zombie Code & Redundancy Audit

Status Taxonomy:
- **DC**: DEAD / UNREACHABLE
- **DR**: DUPLICATED / REDUNDANT
- **MO**: PLACEHOLDER / MOCK-ONLY
- **BR**: BROKEN

---

## Zombie Code Candidates & Deletion Protocol

| Candidate Path | Category | Static / Dynamic Reference Proof | Route / DB Reference | Test References | Risk Assessment | Disposition |
|---|---|---|---|---|---|---|
| `web/src/components/Button.tsx` | **DR** (Redundant) | All screens import from `../components/ui/Button.tsx`. `components/Button.tsx` has 0 references in `web/src/` | None | None | Low: `components/ui/Button.tsx` is the active button component | **Removed in M3** |
| `web/src/components/ui/CommandPalette.tsx` | **DR** (Redundant) | App now imports directly from `./components/ui/CommandPalette.tsx`. Legacy wrapper deleted | None | None | Low: Re-export eliminated | **Removed in M3** |
| `web/src/components/Navbar.tsx` | **DC** (Dead) | App navigation uses `FloatingNav.tsx`. `Navbar.tsx` has 0 references in `web/src/` | None | None | Low: Legacy fixed navigation bar replaced by floating dock | **Removed in M3** |
| `web/src/components/Card.tsx` | **DC** (Dead) | Removed during UI unboxing overhaul (`cf916c3`). 0 references in `web/src/` | None | None | Low: Boxed card design system abandoned in favor of unboxed layouts | **Removed in M3** |
| `web/src/components/AmbientBackdrop.tsx` | **DC** (Dead) | 0 references across entire codebase | None | None | Low: Early canvas background prototype | **Removed in M3** |
| `web/src/components/BrandLogo.tsx` | **DC** (Dead) | App uses `components/brand/JLogo.tsx` and `Wordmark.tsx`. 0 references in `web/src/` | None | None | Low: Legacy logo component | **Removed in M3** |
| `src/jovsi/adapters/db/models.py:297` (`PortalPolicyDB`) | **DC** (Dead Table) | Defined as table `portal_policies`. 0 references in `src/jovsi/` services or routers; 0 references in `tests/` | SQLite table `portal_policies` (0 rows) | None | Medium: Table in DB schema, but completely unmanaged | **Keep model or deprecate cleanly without schema breakage** |
| `src/jovsi/worker/queue.py` (`WorkQueue`) | **DC** (Unreferenced Worker) | 0 static or dynamic imports across `src/` and `tests/` | None | None | Low: Generic lease queue drafted but never integrated into worker loop | **Isolate / Keep for background jobs (M5)** |
| `src/jovsi/config.py:45-47` (`LLM_ENABLED`, `LLM_API_KEY`) | **MO** (Placeholder Config) | Settings class declares keys but no service invokes LLM. No provider adapter exists | None | None | High: Must be replaced with real LLM provider abstraction | **Replace in M2** |
| `web/src/screens/JobDiscoveryScreen.tsx:41-52` (Pre-populated form) | **MO** (Hard-coded Fixture) | Pre-fills "Mock Acme Corp" and `http://127.0.0.1:8765/jobs/job-123/apply` directly in user form state | None | `test_ui_vertical_slice.py:121` clicks import without filling form | High: E2E browser test relies on this pre-population! | **Isolate to test helper or preserve safe default until M3/M14** |
| `web/src/api/client.ts:75` (`display_name: 'My Profile'`) | **MO** (Fake Profile Default) | Hard-codes synthetic candidate creation when DB is empty | `/api/v1/candidates` | None | High: Violates authentic user greeting requirements | **Replace with real Onboarding & Auth (M1)** |
| `src/jovsi/services/job_discovery.py:234-266` | **MO** (Fake Badges) | Returns static list of connectors with `status: "CONFIGURED", is_live: True` regardless of actual connectivity | `/api/v1/jobs/sources` | `test_job_discovery.py:15` | High: Violates truth-in-reporting requirement | **Replace with DB-backed Source Registry (M5)** |
| `.gitignore` missing `.env*` | **BR** (Security Risk) | `.gitignore` does not ignore `.env`, `.env.local`, `.env.*` | None | None | High: Risk of accidental secret commit | **Fix immediately in M0/M1** |

---

## Deletion Safety Protocol
1. Baseline verified passing 115 tests and frontend build.
2. Tag `pre-recovery` created.
3. Every deletion in M3 must be accompanied by full test execution (`pytest -v` and `npm run build`).
4. Any component removed must not break `test_ui_vertical_slice.py`.

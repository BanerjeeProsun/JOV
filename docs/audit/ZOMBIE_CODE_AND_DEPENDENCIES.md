# Zombie Code, Redundancy, and Dependency Audit

No application code was deleted. Candidates below require proof before cleanup.

| Candidate | Status | Evidence | Recommendation |
|---|---|---|---|
| `src/jovsi/worker/queue.py` / `WorkItemDB` | DC | No runtime imports or worker loop found; diagnostics still reports a heartbeat | Keep only if a worker milestone is scheduled; otherwise isolate behind an explicit feature and remove after migration review |
| `PortalPolicyDB` | DC | Model exists in `models.py:299-309`, table has 0 rows, no service/router references | Either implement policy registry used by detector/health or deprecate with a schema plan |
| Root `herovid.mp4`, `herovidlight.mp4` | DC candidate | `git grep` finds no UI references; UI loads `web/public/media/hero-video*` | Remove only after checking external scripts/docs; prefer one authoritative media directory |
| `web/src/components/ThemeProvider.tsx` | DR by design | One-line re-export of `design/theme/ThemeProvider` | Keep as compatibility export or consolidate imports |
| `docs/audit/FINAL_REPORT.md`, `PROGRESS.md`, `AUTH_AUDIT.md`, `INVENTORY.md` | DR/stale | Claim 212/213 tests and old pre-recovery defects that conflict with current code; `FINAL_REPORT.md:31-50` is especially overconfident | Retain history but mark superseded and link this audit; do not use as current status |
| `jov-ad-studio/` | UN | Separate Remotion project with its own lockfile and no core app imports | Keep as separate asset tooling until ownership/deployment purpose is documented |
| Compatibility Tailwind color aliases | DR | `tailwind.config.ts:35-56` aliases old Apple names to current variables | Keep during migration; remove after class search and visual regression |
| `FallbackLLMProvider` | Keep | Explicitly used for unavailable provider and tested | Keep, but surface fallback state honestly |
| `mock_portal/` | Keep/isolate | Used by E2E/failure matrix and safety sandbox | Keep available to tests; hide/reset/admin endpoints behind local/test controls |
| Scratch scripts and rendered PNG/PDF files | UN | `scratch/` contains DB/parser/render utilities and artifacts | Classify each by import/config/test reference before cleanup; avoid deleting user evidence |

## Dependency/configuration findings

- `pyproject.toml:7-18` omits runtime imports observed in `config.py` (`pydantic-settings`), `resume.py`/parser (`python-docx`), and FastAPI multipart upload support (`python-multipart`). The current `.venv` has them, but a clean install from the manifest is not reproducible.
- `alembic` is declared but no Alembic config/migrations exist; `init_db` performs silent auto-migrations and swallows exceptions (`session.py:37-110`).
- No lockfile exists for Python dependencies. `web/package-lock.json` exists, but frontend chunk size is already above the 500 KB warning threshold.
- No deployment/CI manifest was found; persistent SQLite/storage paths, workers, cookies, CORS, and email are not deployment-described.
- `datetime.utcnow()` deprecation warnings are pervasive and should be addressed before a Python version upgrade.

## Cleanup rules

1. Preserve mock portal and useful fixtures in test-only paths.
2. Prove dynamic imports/config/database references before deletion.
3. Migrate stale documentation rather than deleting historical evidence.
4. Remove root media/scratch artifacts only after a reference and user-change review.

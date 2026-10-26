# JOV.si — Verified System Runbook

This runbook documents the exact, verified commands to run, test, and build the JOV.si system on the host environment (Windows, Python 3.12, Node 20+, PowerShell).

---

## 1. Environment & Prerequisites

- **Python**: Python 3.12.14 in `.venv` (`.\.venv\Scripts\python.exe`)
- **Node.js**: Node v20+ with npm (`web/package.json`)
- **Database**: SQLite `jovsi.db` (auto-initialized by `init_db()`)
- **Browser Automation**: Playwright Chromium installed in `.venv`

---

## 2. Test Execution Commands (Verified)

### Full Python Test Suite
Runs all 115 unit, integration, failure-injection, and browser-acceptance tests:
```powershell
.\.venv\Scripts\pytest.exe -v
```
*Verified result*: `115 passed, 409 warnings in 25.05s`.

### Individual Test Suites
```powershell
# Factual consistency mutation corpus (40 tests)
.\.venv\Scripts\pytest.exe tests/unit/test_mutation_corpus.py -v

# Hostile failure injection matrix (12 tests)
.\.venv\Scripts\pytest.exe tests/failure/test_failure_matrix.py -v

# 14-step backend vertical slice acceptance test
.\.venv\Scripts\pytest.exe tests/e2e/test_vertical_slice.py -v

# Full headless Chromium Playwright browser UI acceptance test
.\.venv\Scripts\pytest.exe tests/e2e/test_ui_vertical_slice.py -v

# Immutability triggers and append-only audit log test
.\.venv\Scripts\pytest.exe tests/integration/test_db_immutability.py -v
```

### Frontend Build & Lint (Verified)
```powershell
cd web
npm run build
npm run lint
cd ..
```
*Verified result*: `tsc -b && vite build` succeeded in 1.34s; `oxlint` executed with 0 errors.

---

## 3. Running the Application (Local Development)

### Terminal 1: Hostile Mock Portal (Port 8765)
The mock portal simulates external hostile job portals with honeypots, rate limiting, and CSRF/HMAC protections:
```powershell
.\.venv\Scripts\uvicorn.exe mock_portal.server:app --host 127.0.0.1 --port 8765
```

### Terminal 2: JOV.si Backend & Web Static Server (Port 8000)
Serves the FastAPI API and the compiled React single-page application at `http://127.0.0.1:8000/`:
```powershell
.\.venv\Scripts\uvicorn.exe jovsi.api.main:app --host 127.0.0.1 --port 8000
```

### Terminal 3 (Optional): Vite Frontend Dev Server with HMR (Port 5173)
```powershell
cd web
npm run dev
```

---

## 4. Key Endpoints

- Web App: `http://127.0.0.1:8000/`
- API Documentation (Swagger): `http://127.0.0.1:8000/api/docs`
- Health Check: `http://127.0.0.1:8000/health`
- Diagnostics Health: `http://127.0.0.1:8000/diagnostics/health`
- Mock Portal: `http://127.0.0.1:8765/`
- Mock Portal Oracle: `http://127.0.0.1:8765/__admin/applications`

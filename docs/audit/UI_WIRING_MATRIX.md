# JOV.si UI Wiring Matrix

Status is the primary taxonomy required by the audit. `FV` means the complete path was exercised; a rendered control or passing unit test alone is not sufficient.

## Routing baseline

There is no React Router. `web/src/App.tsx:24-57` stores `activeTab` only in component state. The apparent `/`, `/jobs`, `/queue`, `/tracker`, `/profile`, `/settings`, and `/diagnostics` labels are tabs, not registered browser routes. Refresh/direct URL/history therefore cannot restore the selected page. Job filters have their own query-string synchronization (`JobDiscoveryScreen.tsx:47-84`), but this does not create page routes.

## Matrix

| Screen/control | Event handler/state | API request | Backend path/dependency | Observed outcome/status | Recommended correction |
|---|---|---|---|---|---|
| Public Sign In | `AuthModal.handleSubmit` | `POST /api/v1/auth/login` | `auth.py` -> PBKDF2/session cookie | Covered by auth tests; **IU** | Add browser error/expiry tests and production cookie configuration |
| Public Create Account | same | `POST /api/v1/auth/register` | Creates User, Candidate, UserSettings, session | Covered; no email dispatch; **PF** | Send verification mail through a configured provider |
| Forgot password | `AuthModal` | `POST /auth/forgot-password` | Creates reset token | Returns `_test_token` for real users (`auth.py:195-202`); **BR** | Never return token; use mail sink/provider in tests |
| Sign out (nav/settings/overview) | `AuthContext.logout` | `POST /auth/logout` | Revokes token and deletes cookie | Covered; UI state clears; **IU** | Add account-switching browser test against cached screens |
| Theme toggle | `FloatingNav`/ThemeProvider | none | `localStorage` + `data-theme` | Works in rendered QA; **IU** | Test FOUC/reduced motion in browser at both themes |
| Explore Product | `handleExploreProduct` | none | Scrolls to `#product-architecture` | Works only on overview; **PF** | Use real landing route/anchor state |
| Overview refresh | `OverviewScreen.refresh` | `GET /metrics/summary`, `GET /candidates`, `GET /master-resume` | SQL metrics + candidate data | API/UI tests pass; orphan scope risk; **IU** | Require auth and reject orphan records |
| Overview Discover opportunities | `onNavigate('jobs')` | later `/jobs/search` | State-only tab | Does not produce a browser route; **PF** | Router navigation with URL and back/forward support |
| Overview Import resume | `onNavigate('profile')` | later upload | State-only tab | Works within SPA; direct refresh loses context; **PF** | Router and onboarding state |
| Workspace nav tabs | `FloatingNav` buttons | none directly | `setActiveTab` | Controls animate and switch screens; no URL/history; **PF** | Register routes and preserve selected application URL |
| Mobile nav | same | none | Same state | Visible bottom bar; small labels are screen-reader-only; **IU** | Add browser keyboard/target-size assertions |
| Profile Sync Graph | `CandidateProfileScreen.loadData` | `GET /candidates`, master status, facts | Optional auth candidate lookup | Works for owned records; **IU** | Make candidate endpoint mandatory auth |
| Profile Add Custom Fact | `handleAddFactSubmit` | `POST /candidates/{id}/facts` | `ProvenanceEngine.create_user_fact` | Persists user fact; **IU** | Add schema validation by fact kind and edit UI |
| Confirm one fact | `handleConfirmFact` | `POST /facts/{id}/confirm` | Mutates FactDB status/provenance | Works; ownership misses orphan rows; **PF** | Deny all unauthenticated/private fact mutations |
| Confirm all facts | `handleConfirmAllFacts` | `POST /candidates/{id}/confirm-all-facts` | Bulk status update | Works for owned test candidate; **IU** | Add explicit count and rejection tests |
| Delete fact | `handleDeleteFact` | `DELETE /facts/{id}` | Deletes FactDB | Works; no confirmation dialog; **PF** | Confirm destructive fact deletion and preserve provenance history |
| Resume dropzone/file chooser | `handleSelectFile` | none until upload | `<input accept=".pdf,.txt">` and drag/drop | Backend supports DOCX but UI excludes it; no size/signature precheck; **PF** | Accept DOCX, enforce size/signature, explain encrypted/scanned failures |
| Upload & Extract Provenance | `handleUploadAndProcess` | multipart `POST /candidates/{id}/resume/upload` | Parser -> DocumentDB + proposed FactDB | Backend tests pass; UI has simulated 350 ms processing timer; **PF** | Drive state from server job/status, not timer |
| Replace master resume | Same upload workflow | same upload endpoint | Same document/fact upsert | Label exists, but no explicit active-version/deletion UI; **PF** | Add version selection and safe replacement semantics |
| Job keyword search | `executeSearch` on filter state | `GET /jobs/search?q=...` | SQL title/company/description filter | Server-side query and tests pass; **IU** | Display API errors rather than console-only failures |
| Country/city/work-mode filters | `toggleCountry`, `toggleCity`, `toggleWorkMode` | repeated query params to `/jobs/search` | JobLocationDB subquery/facets | Facet tests pass; location selection only affects search, not live discovery; **PF** | Share one filter DTO with discovery and add remote-country semantics tests |
| Suitability slider | `updateFilter({minScore})` | `/jobs/search?min_score=` | EvaluationDB score subquery only when candidate ID exists | Control works; no score shown for un-evaluated jobs; **PF** | Make “unknown score” explicit and require candidate selection |
| Filter URL chips/back-forward | `writeUrlFilters`, `popstate` | no extra API beyond search | Browser history query state | Filter state restores inside Jobs screen; page route does not; **PF** | Add router-level URL state |
| Deep Search | `handleOpenDeepLinks` | `GET /jobs/deep-links` | Static permitted links service | Generates handoff links; does not import/search those sites; **IU** | Label as external handoff and test policy copy |
| Import Job Posting modal | `handleImportSubmit` | `POST /jobs/import` | Sanitizer + JobDB/JobLocationDB | **Mock default values are inserted into ordinary DB**; **MO** | Start empty; require user input; isolate fixtures |
| Import by URL | `handleUrlImport` | `POST /jobs/import/url` | SSRF + ATS/JSON-LD extractor | Restricted boards return actionable error; **IU** | Add live schema tests and auth/abuse controls |
| Discover Live Jobs | `handleDiscoverLive` | `POST /jobs/discover` | Connector registry classes | Calls all connectors but omits `location`, `work_mode`, country, and city from request; **PF** | Send complete filters and persist source attribution/freshness |
| Job Apply | `handleStartApplication` | `POST /applications` | Candidate/job lookup + unique application key | Creates application and moves to Queue; job source is not ownership-scoped; **PF** | Require auth and bind application to selected/current job package |
| Open portal link | anchor `href={selectedJob.source_url}` | browser navigation | External destination | Correctly hands off URL; no portal policy check in UI; **IU** | Display source/policy/support status before handoff |
| Queue refresh | `loadApplications` | `GET /applications` | Candidate-scoped SQL, orphan rows anonymous | Works for owned accounts; **PF** | Require auth; add empty/loading/error assertions |
| Queue Run Evaluation | `handleRunEvaluation` | `POST /applications/{id}/evaluate` | Eligibility + scoring + state machine | Tested vertical slice; **IU** | Reject synthetic default job requirements and persist evidence references |
| Queue Generate Resume | `handleGenerateResume` | `POST /applications/{id}/generate-resume` | Resume/cover generation + ResumeDB | Tested; generated PDF is rendered but not stored as file; **PF** | Persist artifact metadata/bytes in durable storage |
| Queue Execute Gate | `handleRunGate` | `POST /applications/{id}/gate` | Gate snapshot | UI reports result; backend fails open on validation exceptions; **BR** |
| Queue Review Package | `onSelectApplication` | later `GET /applications/{id}` | State-only review screen | Works in SPA; not directly addressable; **PF** |
| Queue Submit to Portal | `handleSubmit` | `POST /applications/{id}/submit` | Playwright mock portal | Mock E2E passes; real external is blocked; **MO/BA** |
| Review PDF/DOCX downloads | current uncommitted `handleDownload*` | `GET /applications/{id}/resume/{pdf,docx}` then Blob URL | Binary response and `Content-Disposition` | Current endpoint tests and browser path are wired; **FV** | Keep regression test for JSON error/Blob MIME |
| Review cover-letter regenerate/save | `handleRegenerateCoverLetter`, `handleSaveCoverLetter` | POST/PUT cover-letter endpoints | Validator + ResumeDB content update | Works in unit/integration tests; no separate version/hash invalidation; **PF** |
| Review field editing/copy | `handleSaveFields`, `handleCopy` | PUT/GET `/fields` | FieldAnswerDB | Persists and supports clipboard; gate can still default missing values; **PF** |
| Review approve | `handleApprove` | `POST /approve` with UI hash | ApprovalDB/service | Gate hash displayed and tested, but `approved_by` is client input and package freshness is not recomputed; **BR** |
| Review manual handoff | `handleMarkManual` | `POST /mark-submitted-manual` | State/event | Works in service tests; proof is candidate assertion, not external evidence; **PF** |
| Tracker inspect/resolve | `handleInspectDetail`, `handleResolveUncertain` | GET app + POST resolve | Event/state machine | State transitions tested; `proof_ref` is not stored in EvidenceDB; **PF** |
| Settings Save | `handleSave` | `PATCH /settings` | Per-user DB settings plus module globals | Persistence test passes, but UI sends `['*']` when enabling real submission and API mutates process-global safety flags; **BR** |
| Settings source Probe All | `loadSourceHealth` | `GET /jobs/sources/health` | Sequential live HTTP status probes | Honest latency/status for HTTP reachability; no auth and no schema validation; **PF** |
| Diagnostics mock oracle/reset | direct `fetch` | `/diagnostics/mock-portal/*` | HTTP calls to localhost mock | Reset/oracle controls are unauthenticated; errors become empty/error JSON; **PF** |
| Command palette | `CommandPalette` actions | mostly navigation callbacks | Same state-only tabs | Controls work in SPA; no route/history; **PF** |

## Controls requiring immediate repair

`SEC-001`, `SEC-002`, `APP-001`, `APP-002`, `DATA-001`, and `CFG-001` are the minimum blocker set. Existing UI tests should remain, but need isolated databases and production-like authorization fixtures.

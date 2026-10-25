# DepartmentAI End-to-End Verification Report

## Student-to-Official shared queue implementation and re-verification — 2026-10-25

- Implemented the approved local routing policy: a Student explicitly submits an owned draft to a queue shared by authenticated Officials; the first Official to claim the submitted application becomes its assigned processor.
- Added backend routes for Student submission, Official unassigned-queue listing, and Official claim. Submission writes `SUBMITTED` status history and an audit event atomically. Claim locks the application row and rejects non-submitted or already-claimed items.
- Added Student submit and Official queue/claim UI, API helpers, and corresponding API/workspace tests. Updated the API contract, role-permission matrix, and manual workflow guide.
- Verification rerun: isolated integration test `backend/tests/test_local_database_integration.py` passed (**1 passed**) with `DEPARTMENTAI_DATABASE_ENV=test`. It covers submit-to-claim behavior, role/ownership denial, queue visibility, and duplicate submission/claim conflicts. Frontend API/auth/login/workspace tests and JavaScript syntax checks also passed.
- Live local checks: API `/health/ready` returned `ready`; OpenAPI exposed all three handoff routes; frontend on port 5502 returned HTTP 200. The prior browser page was unavailable, so a fresh browser tab was opened and the Student sign-in flow selected. The fresh tab remained on the sign-in form; no authenticated workflow could be exercised.
- Unauthenticated live API checks returned HTTP 401 for `GET /official/applications/unassigned`, `POST /applications/7/submit`, and `POST /applications/7/claim`, confirming authentication enforcement without performing a write.
- The user authorized submitting existing application `APP-2026-00001` (ID 7). A read-only database check confirmed it remains `DRAFT` and unassigned. No status change or claim was made because the fresh browser still had no authenticated Student session; authentication was not bypassed.
- Live Student session subsequently became available. Opening `APP-2026-00001` confirmed the draft and rendered the submit control. The first click exposed a frontend wiring bug: `app.js` called submit/queue/claim helpers without importing them, so the handler failed locally before making an API request. After importing them and reloading, the browser exposed a stale API module and then duplicate API module instances between `app.js` and `auth.js`; these were aligned with a shared cache-busted module URL so the in-memory bearer token is used consistently. Updated the auth contract test to exercise that same module instance.
- Repeated live browser verification: Student `synthetic.student` opened `APP-2026-00001` and selected **Submit to Official queue**. API log recorded `POST /applications/7/submit` HTTP 200 followed by refreshed detail/history reads HTTP 200. The Student page displayed `SUBMITTED` and the shared-queue confirmation.
- Official `synthetic.official` then signed in. API log recorded `GET /official/applications/unassigned?limit=20&offset=0` HTTP 200; the Official UI displayed `APP-2026-00001` under **Unassigned submissions** and the assigned list remained empty. The application was not claimed.
- Read-only development-database verification confirmed `APP-2026-00001` status `SUBMITTED`, a submission timestamp, exactly one matching `SUBMITTED` history row and submission audit event, no Official assignment, and eligibility for the unassigned-queue filter.
- Final focused validation after the frontend module fix: API contract, auth, and workspace tests passed; JavaScript syntax and scoped `git diff --check` passed. Institutional identity/database behavior remains outside this local synthetic verification.

## Browser session persistence — 2026-10-25

- Fixed the reload sign-out behavior without persisting account passwords. The bearer token is stored in tab-scoped `sessionStorage`, then validated with `GET /auth/me` at startup before rebuilding the authenticated workspace.
- Live browser verification: after signing in as `synthetic.student`, reloaded the page. `GET /auth/me` returned HTTP 200 with role `STUDENT`; the Student Workspace and Sign Out control were restored, and the login form was absent.
- Logout continues to revoke the server session and clear browser token storage. Closing the tab clears `sessionStorage`; server expiration/revocation still applies.
- Automated auth test covers token storage, `/auth/me` restoration in a fresh auth-module instance, and clearing storage on logout. Auth/API/login/workspace tests and JS syntax checks passed.

## Academic Assistant knowledge-base diagnosis — 2026-10-25

- Confirmed root cause: the isolated `departmentai_dev` database had zero rows in `documents`, `sections`, and `knowledge_chunks`, while the local source assets existed (`UG Ordinance.pdf`, extracted text, structure, 246 prepared chunks, and 246 matching 384-dimensional embeddings). The Assistant retrieved no ordinance context, which caused in-scope queries to be answered as insufficient.
- Updated `backend/ingest_knowledge_base.py` so the explicit development-only ingestion pipeline creates missing document/section metadata additively from the processed structure file before inserting chunks. It still refuses non-development profiles and prevents duplicate chunk ingestion. Ingested the existing local UG ordinance into `departmentai_dev`: 13 sections and 246 chunks; no application records were touched.
- Verified hybrid retrieval locally for late registration, grade improvement, programme duration, academic deficiency, and attendance. Added query rewrites for common phrases (“academic probation,” “degree extension,” and “normal/slow paces of study”) to match the ordinance’s terminology, clause-title relevance scoring, and Assistant source formatting compatible with the documented API response. The guardrail now allows the paces-of-study question while continuing to reject unrelated questions.
- Live browser verification after indexing: Student asked “What are the rules for late registration?” and received an answer grounded in the UG Ordinance, with source citations. The previous in-session answers remain historical; ask again after the update to see indexed results.
- Remaining content limitation: the ordinance uses “Academic Deficiency (ACD),” not “academic probation,” and specifies maximum programme duration rather than a general “degree extension application.” Query expansion helps retrieve the related clauses, but the answer must distinguish the ordinance’s actual terms and must not invent a separate process.
- Focused regression checks cover guardrail acceptance, query expansion, semantic relevance and citations. No institutional database was used. A real Gemini request was made by the Assistant with ordinance context as part of the requested browser verification; do not use non-public or personal records with external AI without approval.

## Manual synthetic workflow completion — 2026-10-25

- Completed the supported Student → Official → DUGC → Official closure path in the explicitly selected local `departmentai_dev` environment using synthetic application `APP-2026-00005` (application ID 5). Official status updates returned HTTP 200 for `DRAFT → SUBMITTED → DOCUMENT_VALIDATION → PROCESSING → UNDER_REVIEW → COMMITTEE_REVIEW`; committee assignment returned HTTP 200; the DUGC `APPROVED` decision returned HTTP 200; Official closure to `CLOSED` returned HTTP 200.
- Student and staff views showed the synthetic uploaded PDF metadata. A browser download was attempted, but no definitive HTTP response was captured, so download success remains unverified.
- Eligibility and deficiency refreshes each returned HTTP 200 with zero results. AI analysis was generated and persisted for this synthetic-only record; the external Gemini response was advisory and reported insufficient ordinance context. It was not used as an official decision.
- Final read-only verification showed application 5 `CLOSED`, its DUGC review `COMPLETED/APPROVED`, and the document metadata and analysis record present. Student-created application `APP-2026-00006` remains `DRAFT` and unassigned; no Official handoff is available for newly created applications, so that separate flow remains blocked.
- On returning to a previously opened Student detail, the status-history and committee panels were stale from in-memory cached responses even though the application summary showed `CLOSED`. Updated [frontend/app.js](../frontend/app.js) to refresh those read-only panels on each detail navigation. After the change, the browser displayed all status transitions, the completed DUGC decision, and the final closure. This change does not add server capabilities or alter authorization.
- Focused frontend verification: `node --check frontend/app.js`, API contract tests, auth-service tests, login-form tests, and role-workspace tests all passed. Browser verification confirmed the Student-owned application list and final detail; Official and DUGC workflow actions and HTTP results are recorded above from the completed synthetic run.
- No definitive download status or screen-reader/live institutional authorization result was established. A browser logout attempt again reported `POST /auth/logout` as `net::ERR_ABORTED`; a subsequent read-only query found one active, unexpired synthetic Student session. The session token was not inspected, so the count is not conclusively correlated to that request, but server-side revocation is unverified and requires investigation before relying on logout for session termination.
- This is local synthetic development evidence only. The institutional PostgreSQL service and production authentication remain unverified; this report does not claim production readiness.

**Verification date:** 2026-10-25
**Overall status:** **LOCAL SYNTHETIC WORKFLOWS VERIFIED; NOT READY FOR INSTITUTIONAL / PRODUCTION DEPLOYMENT**

## Analysis schema follow-up — 2026-10-25

- The three analysis actions initially failed because the isolated schemas lacked five tables used by existing services. Added `document_extractions`, `application_requirements`, `eligibility_results`, `deficiencies`, and `ai_analyses` to the explicit development/test schema initializer; no institutional profile or database was touched. Initializing development and test added five tables to each, and a subsequent development initialization added zero.
- Automated isolated workflow coverage: eligibility route returned deterministic `NOT_MET` for one synthetic requirement, deficiency route returned one corresponding synthetic finding, and AI-analysis route persisted a synthetic analysis. The test stubs AI generation and ordinance retrieval; no provider request is made by the automated test.
- Browser against synthetic `departmentai_dev` application ID 3: `GET /applications/3/eligibility` — HTTP 200, zero requirements; `GET /applications/3/deficiencies` — HTTP 200, zero findings; `POST /applications/3/ai-analysis` — HTTP 200, persisted analysis ID 1. The last browser action made a real Gemini request with only the synthetic fixture context. It returned an advisory result that explicitly noted insufficient ordinance context; there were no documents, requirements, eligibility findings, deficiencies, or ordinance sources for the sample.
- The development application's read-only status history showed it progressed through the synthetic Official workflow to `APPROVED` and then `CLOSED` during this check window (latest event `CLOSED` at 2026-10-25 11:42:26, actor `synthetic.official`). These status transitions were not part of the analysis actions performed here. No status mutation, reset, or compensating write was issued by this verification; the observed state was left intact.
- Focused validation after the schema change: backend suite **19 passed** (one Starlette/AnyIO deprecation warning), guardrails **10 passed**, frontend API/login/auth/role-workspace tests **4 passed**, and `frontend/config.js` syntax check passed.

## Local role/workflow verification before analysis follow-up — 2026-10-25

### Environment and scope

- This checkout's frontend returned HTTP 200 from `http://127.0.0.1:5502/`. A separate development-profile FastAPI process at `http://127.0.0.1:8001` used `DEPARTMENTAI_DATABASE_ENV=development` and the isolated `departmentai_dev` database. Its CORS environment was restricted to the exact browser origin `http://127.0.0.1:5502`; the browser API base was set to port 8001 for this run.
- The existing listener on port 8000 returned HTTP 404 for `/health/live` and was left untouched. Port 5500 was not taken over. No proxy or browser-security bypass was used.
- The development-only seeder created/reused synthetic Student, Official, and DUGC users. Browser verification completed application ID 2. Afterward, the seeder was run twice and returned application ID 3 both times; a read-only database query confirmed ID 2 remained `APPROVED` and ID 3 remained `DRAFT`, with exactly one synthetic account per role. This verifies active-draft reuse and preservation of the completed workflow. No institutional record or credential was used.

### Live browser/API responses

Actual cross-origin browser requests succeeded after their CORS preflights. These are local-development results only.

| Method and path                           |     HTTP | Observed response/result                                                                  |
| ----------------------------------------- | -------: | ----------------------------------------------------------------------------------------- |
| `GET /health/live`                        |      200 | `{"status":"ok"}`                                                                         |
| `GET /health/ready`                       |      200 | `{"status":"ready"}`; required local DB tables present                                    |
| `GET /openapi.json`                       |      200 | OpenAPI JSON served                                                                       |
| `POST /auth/login`                        |      200 | Synthetic Student, Official, and DUGC login succeeded                                     |
| `GET /applications?limit=5&offset=0`      |      200 | Student dashboard loaded its owned synthetic application                                  |
| `GET /applications?limit=20&offset=0`     |      200 | Official/DUGC workspaces loaded only assigned synthetic application                       |
| `GET /applications/2`                     |      200 | Synthetic application JSON; Official response included allowed transitions                |
| `GET /applications/2/documents`           |      200 | Empty document list; no stored filesystem path exposed                                    |
| `GET /applications/2/status-history`      |      200 | History object; Student response omitted `changed_by`                                     |
| `GET /applications/2/committee-reviews`   |      200 | Review object; Student response omitted `decided_by`, DUGC results filtered by membership |
| `GET /applications/2/ordinance-retrieval` |      200 | Empty `results` list returned from the intentionally empty local knowledge schema         |
| `PATCH /applications/2/status`            | 200 each | Five legal synthetic transitions through `COMMITTEE_REVIEW` submitted by Official UI      |
| `POST /applications/2/committee`          |      200 | Official assigned the synthetic DUGC review                                               |
| `PATCH /committee-reviews/1/decision`     |      200 | DUGC recorded synthetic `APPROVED` decision; Student UI showed human decision, not actor  |

No `/ask`, AI-analysis, processing, eligibility, deficiency, document upload, or upload/download browser operation was invoked. Automated integration tests exercise synthetic document upload, metadata, download, empty-name/oversize validation, and unauthorized access.

### Automated checks

- Backend: `DEPARTMENTAI_DATABASE_ENV=test .venv\Scripts\python.exe -m pytest backend\tests -q` — **19 passed**, one Starlette/AnyIO deprecation warning.
- Guardrails: `.\.venv\Scripts\python.exe -m pytest tests\test_guardrails.py -q` — **10 passed**.
- Frontend: API, login, auth-service, and role-workspace Node tests — **all passed**.
- Syntax: `node --check` on all **20** frontend `.js`/`.mjs` files — **passed**.
- Browser: viewport widths 376, 768, 1281 had no horizontal overflow; keyboard Tab reached a control with a solid 2px focus outline. Screen-reader and broader assistive-technology checks were not performed.
- Full repository `pytest` was **not run** because the broader tests may connect to the institutional database or invoke AI/provider operations.

### Institutional services and deployment blockers

- A current `Test-NetConnection 10.219.45.43 -Port 5432 -InformationLevel Quiet` returned **False**. No institutional database query was attempted. This does not establish whether VPN/private routing, a firewall, or PostgreSQL service availability is the cause. Required action: the network/database administrator must restore the approved route and verify service/firewall status.
- Local `/health/ready` returning 200 proves only that `departmentai_dev` is reachable and has the required local schema. It is not evidence that the institutional database is healthy.
- Local password authentication is disabled in the institutional profile (automated test expects 503). Institutional IdP integration, trusted account provisioning, Official/committee membership governance, audit visibility policy, screen-reader testing, and production security review remain unverified or blocked.

The following 2026-10-24 sections are retained as historical evidence and are superseded where they describe preview-only roles, missing application lists, missing auth, or no browser database integration.

## Latest local integration verification — 2026-10-24

- The current checkout's frontend loaded at `http://127.0.0.1:5501/`; its configured API base was `http://127.0.0.1:8000`. A real browser issued cross-origin GET requests to that API and received successful responses without CORS errors. Port 5500 remains owned by the other checkout and was not stopped or modified.
- Browser-verified read routes against the explicit local `development` database, each HTTP 200:

| Method and path                           | Response shape observed                                                                                                                                               |
| ----------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET /applications/1`                     | JSON object with `id`, `application_number`, `applicant_identifier`, `application_type`, `title`, `description`, `status`, `submitted_at`, `created_at`, `updated_at` |
| `GET /applications/1/status-history`      | JSON object with `application_id`, `history`                                                                                                                          |
| `GET /applications/1/documents`           | JSON object with `application_id`, `documents`                                                                                                                        |
| `GET /applications/1/committee-reviews`   | JSON object with `application_id`, `reviews`                                                                                                                          |
| `GET /applications/1/ordinance-retrieval` | JSON object with `application_id`, `query`, `results`; empty results were rendered as an honest empty state                                                           |

These requests used the synthetic browser-test application. The exact synthetic marker was subsequently deleted from `departmentai_dev`; a verification query confirmed zero remaining rows for that marker. No live institutional record was queried.

- Isolated backend integration suite: **17 passed**, one Starlette deprecation warning. It exercises synthetic application create/read, status transitions/history, document metadata, committee assignment/review/decision, and empty ordinance retrieval only against `departmentai_test`; fixtures are cleaned by an exact synthetic identifier. Guardrails: **10 passed**.
- Frontend verification: syntax checks for **19** JS/MJS files passed; `frontend/services/api.test.mjs`, `frontend/components/auth/login.test.mjs`, and `frontend/pages/role-workspaces.test.mjs` passed. Browser API reads succeeded from the Student preview page. Official and DUGC remain read-only previews; authenticated access, role authorization, application queues, and record-level isolation were not tested or established.
- Schema initialization reran in both `development` and `test` profiles and reported **0 tables created** for each, confirming idempotence on these isolated databases.
- The institutional PostgreSQL endpoint `10.219.45.43:5432` remains unreachable based on the earlier bounded TCP check. No attempt to switch or fall back was made; institutional data and service health remain unverified. Full `pytest` and AI/provider tests were not run because of possible live database/AI side effects.

## Local database development verification — 2026-10-24

### Configuration and safety

- The original project `.env` still targets institutional PostgreSQL `10.219.45.43:5432`; its credential values were not printed or changed. The default backend profile remains `institutional`. A local database requires explicit process selection through `DEPARTMENTAI_DATABASE_ENV=development` or `test`; missing local config, non-loopback host, wrong database name, or invalid profile fails closed.
- Local PostgreSQL service `postgresql-x64-18` is running PostgreSQL 18.6 on loopback port 5432. It requires password authentication. The existing local databases `departmentai` and `departmentai_m11_test_20261022` were catalog-inspected read-only and not modified.
- Newly created isolated databases: `departmentai_dev` and `departmentai_test`, owned by the separate local-only `departmentai_local` role. Their new credentials are stored only in ignored `.env.development` and `.env.test`; no secret was printed or committed.
- No core-application Alembic migrations or ORM models were found. The existing `module2/database/schema.sql` is specifically for Module II faculty tables and is not the schema for these API routes. Added `backend/database/application_schema.sql` mirrors inspected local definitions and active service SQL for applications, status history, document metadata, committee reviews, audit logs, and empty pgvector-backed retrieval tables. pgvector 0.8.6 was enabled by the local administrator on only the two new databases. Initialization is idempotent, transactional, restricted to the two named local database profiles, and refuses unexpected tables. No knowledge chunks or institutional records were copied.

### Implemented local integration coverage

- Automated local integration test uses the explicitly selected `departmentai_test` database and unique synthetic identifiers only.
- It exercises `POST /applications`, `GET /applications/{id}`, empty `GET /ordinance-retrieval`, initial and transitioned `GET /status-history`, PDF metadata upload and `GET /documents`, the existing allowed transitions through `COMMITTEE_REVIEW`, DUGC assignment and `GET /committee-reviews`, synthetic committee decision recording, and final application/status-history reads.
- Test cleanup deletes only the unique synthetic applicant marker from `departmentai_test`; uploaded bytes go to pytest's temporary directory. No institutional database or existing local database is targeted.
- Unavailable-database behavior is tested to return an HTTP error rather than a fabricated application.
- These test actor labels do not represent verified Student, Official, or DUGC identities. Backend authentication/authorization remains absent. AI analysis/provider calls, vector ingestion, application-list endpoints, and queues are not part of the local workflow.

### Historical CORS/source remediation and earlier check — 2026-10-23

Backend CORS source was updated after the live checks below: exact local origins now include `http://127.0.0.1:5501`, configured origins can be supplied through `CORS_ALLOWED_ORIGINS`, allowed methods/headers are explicit, and credentials are disabled. The confirmed Uvicorn process was restarted from this checkout. From the current frontend page at `http://127.0.0.1:5501/`, a browser cross-origin `GET http://127.0.0.1:8000/openapi.json` with `Content-Type: application/json` (therefore a browser preflight followed by the actual GET) succeeded with HTTP 200, `application/json`, OpenAPI 3.1.0 and 18 paths. This verifies CORS and OpenAPI reachability only. Port 5500 still returns `ERR_EMPTY_RESPONSE`; configured PostgreSQL remains unreachable and no business-data route was tested. The old failures in the following dated table are historical evidence from before the API restart.

At that historical stage, backend tests reported **11 passed** and no business-data route had been called. Those results are superseded by the 2026-10-24 local integration evidence above; the earlier failures below are retained as diagnostic history, not current status.

This report separates source inspection, mocked contract tests, local runtime checks, and live database workflows. A running frontend or FastAPI docs page is not evidence of a successful end-to-end workflow.

## Role and workspace results

| Role/workspace   | Source/UI result                                                                                                                                                                            | End-to-end status                                                                                                                                                       |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Student          | Local preview identity; dashboard, application creation/detail, documents, status/history, and settings. Application list remains explicitly unavailable; AI/provider workflow was not run. | **LOCAL PATH PARTIALLY VERIFIED** — synthetic application create/read and associated reads passed locally; no ownership authorization or institutional integration.     |
| Official         | Read-only governance preview with known-ID lookup and application/status/document/review panels. Queue and write controls are absent.                                                       | **LOCAL API PATH VERIFIED, PERMISSIONS UNVERIFIED** — browser GETs used synthetic local data; no authenticated queue or role authorization exists.                      |
| DUGC             | Read-only governance preview with known-ID lookup and review/decision-history panels. Assigned queue and decision controls are absent.                                                      | **LOCAL API PATH VERIFIED, PERMISSIONS UNVERIFIED** — synthetic review workflows passed in isolated tests; no authenticated committee identity or authorization exists. |
| Committee Member | No dedicated role or assignment-scoped identity was found. `DUGC`, `DMPC`, and `DDPC` are committee type values in the API contract.                                                        | **NOT IMPLEMENTED / NOT A VERIFIED ROLE**.                                                                                                                              |

The detailed role matrix and the mandatory role-by-feature gaps/evidence report are in [`ROLE_PERMISSION_MATRIX.md`](./ROLE_PERMISSION_MATRIX.md) and [`FRONTEND_BACKEND_GAPS.md`](./FRONTEND_BACKEND_GAPS.md).

## Historical runtime and API evidence — 2026-10-23 (superseded above)

| Check                                                          | Observed result                                                                                                                                                      | Meaning                                                                                                                                                                                                                                        |
| -------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Frontend `http://127.0.0.1:5501/`                              | HTTP 200                                                                                                                                                             | UI serves, but browser API calls from this origin are CORS-blocked.                                                                                                                                                                            |
| Frontend `http://127.0.0.1:5500/` and `http://localhost:5500/` | Python 3.12 PID 4076; raw `GET /` accepted then closed with zero response bytes                                                                                      | Process CWD is another checkout (`...\sojwal_proj\...\frontend`, not current `...\sojwal_proj2\...`); owner must correct it safely. It was left untouched.                                                                                     |
| Temporary frontend bound to `[::1]:5500`                       | Direct IPv6 request returned HTTP 200; browser navigation to `localhost:5500` failed loading `components/auth/login-role-selector.js` with `net::ERR_EMPTY_RESPONSE` | Not a reliable workaround; temporary listener was stopped, existing IPv4 listener was left running.                                                                                                                                            |
| Backend `GET /docs`                                            | HTTP 200                                                                                                                                                             | FastAPI docs reachable; not a DB readiness check.                                                                                                                                                                                              |
| Backend `GET /openapi.json`                                    | HTTP 200; latest check took 73 ms; JSON declares 18 paths / 19 method operations                                                                                     | OpenAPI schema reachable; not proof that route handlers can access dependencies.                                                                                                                                                               |
| Backend `GET /applications/0`                                  | No response before a 4-second timeout (about 4.16 seconds observed)                                                                                                  | Database-backed application read not verified; no record response was received.                                                                                                                                                                |
| Configured PostgreSQL network                                  | `10.219.45.43:5432` TCP unreachable; one ICMP packet timed out                                                                                                       | API process environment contains this host/port. Wi-Fi is up with default route via `10.241.172.178`; McAfee VPN TAP is disconnected and no Windows VPN profiles were returned. Local `127.0.0.1:5432` accepts TCP but is a separate instance. |
| CORS preflight from `http://127.0.0.1:5500`                    | HTTP 200; matching allow-origin header                                                                                                                               | Origin is allowed, but its frontend listener did not serve the root page.                                                                                                                                                                      |
| CORS preflight from `http://localhost:5500`                    | HTTP 200; matching allow-origin header                                                                                                                               | Hostname variant is allowed too.                                                                                                                                                                                                               |
| CORS preflight from `http://127.0.0.1:5501`                    | HTTP 400                                                                                                                                                             | Origin is not allowed; no browser-security workaround was used.                                                                                                                                                                                |
| Browser fetch from port 5501 to `/openapi.json`                | Blocked by CORS; `net::ERR_FAILED`, no allow-origin header                                                                                                           | Real browser integration from 5501 is not working.                                                                                                                                                                                             |
| Browser requests from the current role-preview checks          | Zero backend requests from Student, Official, and DUGC preview interactions at port 5501                                                                             | These are UI-only checks. No successful browser API request from an allowed origin was possible in this environment.                                                                                                                           |
| Local PostgreSQL service/loopback                              | Service running; port 5432 reachable                                                                                                                                 | Local server availability does not show the configured endpoint is healthy.                                                                                                                                                                    |
| Local read-only `STUDENT-TEST` / `Test request` query          | Query succeeded; zero matching IDs                                                                                                                                   | This was a separate loopback database, not the `.env`-configured endpoint; it cannot establish whether a previous browser request persisted remotely.                                                                                          |

No application create, upload, status transition, committee assignment/decision, AI analysis, or other write was issued in this verification pass. The unresolved possible prior create submission remains a safety caveat; the configured database must be checked read-only when reachable.

## Endpoint contract coverage

Backend source and OpenAPI were inspected for the routes documented in [`API_CONTRACT.md`](./API_CONTRACT.md). The frontend helper contract test uses a local mock server; it does not call the database-backed backend.

- `POST /ask`: request/response helper contract covered by mock tests; current live RAG/AI request not run.
- `POST /applications`: source contract covered; no live create call performed in this pass.
- All 19 frontend API helper paths were matched to OpenAPI routes. Request/response details and side effects are inventoried in [`FRONTEND_BACKEND_GAPS.md`](./FRONTEND_BACKEND_GAPS.md) and [`API_CONTRACT.md`](./API_CONTRACT.md).
- Local mock tests cover request/response helpers for application creation/details, documents, eligibility/deficiency request shapes, AI analysis, status, committee, and audit operations. They are not live backend tests. New application detail, ordinance, eligibility, and deficiency cases use only the local mock test server.
- Eligibility and deficiency GET routes have database write side effects and were not called against the live API.
- Status history, committee review, audit, processing, status update, committee assignment, and committee decision: helper contracts covered by mock tests where applicable; no privileged or persistent write was run.
- `/docs` and `/openapi.json`: current HTTP 200.

## Historical automated tests — 2026-10-23 (superseded above)

### Passed in this verification pass

- `node --check` for all 19 frontend `.js`/`.mjs` files — passed.
- `node frontend/services/api.test.mjs` — passed; includes default/overridden/invalid/mixed-content API-base configuration and local-mock contracts for application detail, ordinance, eligibility/deficiency helper shapes, documents, AI, and workflow calls.
- `node frontend/components/auth/login.test.mjs` — passed; verifies preview warning and no unverifiable password prompt.
- `node frontend/pages/role-workspaces.test.mjs` — passed; verifies truthful, escaped, read-only Official/DUGC views.
- `.\.venv\Scripts\python.exe -m pytest backend\tests -q` — **2 passed**.
- `.\.venv\Scripts\python.exe -m pytest tests\test_guardrails.py -q` — **10 passed**.
- Browser-only navigation covered Student dashboard, application-list unavailable state, create page and settings; Official dashboard, lookup, processing, committee, audit-unavailable and settings; DUGC dashboard, assigned lookup, committee, decision history, audit-unavailable and settings.
- Browser layout check measured CSS viewport widths 376, 768, and 1281 px on all visited role pages; no horizontal overflow (`scrollWidth <= clientWidth`). Keyboard and assistive-technology checks remain incomplete.
- Focus/keyboard spot check: role-selector first button received keyboard focus and Enter opened the local preview form; the Student navigation button showed a 2.4 px solid focus outline. Browser-driven role preview rendered Student, Official, and DUGC pages with synthetic identifiers only; these page transitions made zero backend requests. Screen-reader behavior and authenticated keyboard workflows remain unverified.

### Blocked, not run, or mock-only

- Full `pytest tests -q` was **not rerun** in this pass. A previous attempt failed during collection when `tests/test_qa_pipeline.py` could not reach PostgreSQL. That file executes live question-answering calls at module import; rerunning while DB connectivity is unavailable could exercise external AI/database paths.
- All frontend API helper tests use a local mock server; they verify request shape/handling, not persistence or backend authorization.
- No live Gemini request was made; no paid/external AI operation was invoked.
- No role-permission tests exist for authenticated identities because the backend has no authentication/authorization contract.

## Historical browser, security, accessibility notes — 2026-10-23 (superseded above where dated)

- A fresh browser page loaded the updated role-selector wording. UI-only navigation traversed all pages listed above, using synthetic local preview identities and no application ID. No application API call or write was made during the role navigation checks.
- A separate explicit browser `fetch` from port 5501 to `/openapi.json` failed with CORS (`net::ERR_FAILED`, missing `Access-Control-Allow-Origin`); the safe `/applications/0` browser probe timed out. The CORS failure is not hidden by the UI.
- Targeted browser recheck: Student `My Applications`, Official `Application processing review`, and DUGC `Decision history` rendered from port 5501 using synthetic preview identifiers, with zero API requests and no console/page errors during those interactions. `scrollWidth <= clientWidth` at CSS viewport widths 376, 768, and 1281. A successful integrated browser request from port 5500 remains blocked by its unrelated listener.
- Final recheck at 21:14 +05:30 again identified port 5500 PID 4076 serving from the other `sojwal_proj` checkout. Browser navigation from the current checkout's port 5501 attempted `GET /openapi.json` against the API and failed with CORS (`TypeError: Failed to fetch`, absent allow-origin header, `net::ERR_FAILED`). This is an observed browser CORS failure, not successful integration.
- A fresh browser navigation to the required `http://127.0.0.1:5500/` origin failed with `ERR_EMPTY_RESPONSE (-324)`; the current checkout's frontend did not load there.
- Final role preview check on port 5501 rendered Student `My Applications`, Official `Application processing review`, and DUGC `Assigned application lookup` at CSS viewport widths 376/768/1281 without horizontal overflow. Synthetic preview identifiers only, no application IDs, no backend requests, and no console/page errors in those role interactions.
- Final frontend checks rerun: syntax checks for 19 JS/MJS files passed; API service, login preview, and role workspace tests passed. Focused backend (2) and guardrails (10) passed in the immediately preceding verification pass, not rerun here. Full pytest and all live database/AI tests were skipped.
- `GET /openapi.json` was live-verified HTTP 200 with 19 declared operations; no application, document metadata, status-history, or committee-review read response was obtained in this final pass. These remain source-inspected/API-declared, not live-verified.
- No real role authentication, backend Network result, persisted state, cross-role isolation, or backend-backed sign-out was verified.
- Historical M15 spot checks for mobile navigation/settings are recorded in `PROJECT_STATE.md`; the complete viewport, keyboard, focus, labels, contrast, and assistive-technology matrix remains outstanding.
- Security blocker: backend routes have no authentication or record-level authorization. The UI role selector and client-side filters do not secure student records. Audit routes return raw records; client filtering cannot establish confidentiality.
- The pre-remediation backend CORS allowlist was local-only and did not include port 5501. No production origin was added. The successful post-remediation browser result is described above.

## Changed and pre-existing work

The earlier frontend-verification pass did not change backend files; later explicitly authorized CORS and local-database development work did change backend files, as listed below. No change was committed or discarded.

### Files changed during the current master-prompt continuation

- `frontend/components/auth/login-role-selector.js`
- `frontend/components/auth/login.test.mjs`
- `frontend/app.js`
- `frontend/services/api.test.mjs`
- `docs/FRONTEND_BACKEND_GAPS.md`
- `docs/API_CONTRACT.md`
- `docs/END_TO_END_VERIFICATION_REPORT.md`
- `docs/M11_M17_MANUAL_TESTING_GUIDE.md`
- `docs/DEPLOYMENT_GUIDE.md`
- `docs/ROLE_PERMISSION_MATRIX.md`
- `PROJECT_STATE.md`
- `README.md`

### Local database development additions/updates — 2026-10-24

- `backend/database/connection.py`
- `backend/database/application_schema.sql`
- `backend/database/initialize_local_database.py`
- `backend/ingest_knowledge_base.py`
- `backend/retrieval/semantic_search.py`
- `backend/tests/test_database_profiles.py`
- `backend/tests/test_local_database_integration.py`
- `.env.development.example`
- `.env.test.example`
- `README.md`
- `docs/API_CONTRACT.md`
- `docs/DEPLOYMENT_GUIDE.md`
- `docs/END_TO_END_VERIFICATION_REPORT.md`
- `docs/FRONTEND_BACKEND_GAPS.md`

Before this continuation, the worktree already contained modified tracked backend files (`backend/retrieval/semantic_search.py`, `backend/services/ai_analysis_service.py`), untracked `backend/tests/`, modified frontend/docs files, and other uncommitted/untracked project artifacts. See `git status --short` for the complete inherited inventory. Nothing was committed or discarded.

## Required next actions

1. Obtain owner authorization for backend authentication, applicant ownership checks, committee/official permissions, and audit visibility controls; until then, do not deploy with real institutional data.
2. Restore the approved institutional VPN/private-network route and have the database administrator verify `10.219.45.43:5432`; local database success does not verify institutional access.
3. Add authenticated, role/record-scoped list and workflow endpoints before implementing Student application lists, Official/DUGC queues, or enabling committee writes.
4. Add an authenticated document-content download capability if file retrieval is required.
5. Finish keyboard, focus, screen-reader, and responsive accessibility coverage; run only approved staging AI tests and complete M16/M17 before any deployment decision.

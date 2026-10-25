# DepartmentAI Deployment Preparation

## Status

**NOT READY FOR INSTITUTIONAL / PRODUCTION DEPLOYMENT.** Local synthetic development and test authentication, role-scoped access, and supported workflows are implemented and verified. No hosting provider or production environment has been specified, and no production credentials were used.

The backend enforces local development/test bearer authentication and role/record permissions. Local password login is deliberately disabled in the institutional profile until an approved identity provider and account-provisioning process are configured. Audit reads remain denied pending a privacy/visibility policy. These constraints, plus institutional PostgreSQL unreachability, block any deployment with real institutional data.

## Supported local development setup

Use Windows PowerShell from the repository root. Do not use the checked-in/ignored local virtual environment as a deployment artifact.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Fill `.env` locally with the DB and AI credentials appropriate to the environment. Never print, commit, or share the file. The backend reads `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, and `DB_PASSWORD`; semantic retrieval and ingestion code also refer to `DEPARTMENTAI_DB_PASSWORD`; Gemini operations use `GEMINI_API_KEY`. Verify variable use against the backend code before provisioning a new environment.

Start the API from the repository root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Start the static frontend in another terminal:

```powershell
Set-Location .\frontend
python -m http.server 5500 --bind 127.0.0.1
```

If port 5500 is occupied by another checkout, do not stop or take over its process. Start this checkout's frontend on port 5501 instead:

```powershell
python -m http.server 5501 --bind 127.0.0.1
```

Use `http://127.0.0.1:5500/` for local browser integration when available. The backend's explicit local CORS defaults allow `http://127.0.0.1:5500`, `http://localhost:5500`, and `http://127.0.0.1:5501`. If 5500 is occupied, inspect its owner and do not stop or take over another process; port 5501 can serve this checkout without a proxy.

## Frontend API origin

`frontend/config.js` defines `globalThis.DEPARTMENTAI_API_BASE_URL`. For local development it is empty and the frontend uses `http://127.0.0.1:8000`.

Before building/serving a production static frontend, set that value to the deployment's actual HTTPS API origin, for example:

```js
globalThis.DEPARTMENTAI_API_BASE_URL ??= "https://api.example.edu";
```

Replace the example with the approved API URL; it is not a configured project endpoint. The frontend rejects invalid URLs, embedded credentials, query strings/fragments, and mixed-content HTTP API URLs when the page uses HTTPS. Never put API keys, passwords, or database connection strings in this file.

`CORS_ALLOWED_ORIGINS` optionally replaces the local defaults with exact comma-separated HTTP(S) origins. For deployment, configure only approved HTTPS frontend origin(s); wildcards, credentials, and unapproved origins are not permitted. This CORS configuration is not authentication or authorization.

## Explicit local database development

The active backend connection helper selects a database profile through the process environment variable `DEPARTMENTAI_DATABASE_ENV`:

- Unset or `institutional`: reads the existing repository `.env` and keeps the configured institutional host/database. There is no local fallback.
- `development`: reads only `.env.development`, requires a loopback host, and requires the exact database name `departmentai_dev`.
- `test`: reads only `.env.test`, requires a loopback host, and requires the exact database name `departmentai_test`.

The development/test configuration files are ignored by Git. Copy `.env.development.example` and `.env.test.example` and provide a local-only role/password. Do not copy credentials between environments. The local schema command only runs in development/test mode and refuses to operate if it sees unrecognized tables.

PostgreSQL 18.6 is installed as Windows service `postgresql-x64-18` and listens locally on port 5432. Safe catalog inspection found existing `departmentai` and `departmentai_m11_test_20261022` databases with application tables; neither was modified. New isolated `departmentai_dev` and `departmentai_test` databases were created with a dedicated local role, pgvector 0.8.6 enabled, and eight application/retrieval tables initialized from `backend/database/application_schema.sql`. The schema was matched to existing application-service SQL and inspected local catalog definitions. No knowledge chunks or institutional/application records were copied.

After creating the local role and the two new databases with a local PostgreSQL administrator, use:

```powershell
Copy-Item .env.development.example .env.development
Copy-Item .env.test.example .env.test

$env:DEPARTMENTAI_DATABASE_ENV = "development"
.\.venv\Scripts\python.exe -m backend.database.initialize_local_database
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Before initialization, enable the installed pgvector extension in each new local database using the local PostgreSQL administrator:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

The development/test profiles do not have permission to create server extensions; initialize pgvector as the local administrator first.

To load the existing processed undergraduate ordinance into the isolated development database, run the development-only ingestion command after initializing the schema:

```powershell
$env:DEPARTMENTAI_DATABASE_ENV = "development"
.\.venv\Scripts\python.exe -m backend.ingest_knowledge_base
```

The command uses the checked-in processed chunks, precomputed embeddings, and ordinance structure under `documents\ug\processed`. It creates missing document/section metadata additively, then loads the chunks. It stops rather than overwriting an existing index. The command refuses the institutional and test profiles; never change that guard or point this ingestion at institutional data. Successful ingestion should report 246 chunks and 13 sections. Restart FastAPI after application-code changes; ingestion data itself is visible to the running local API.

Run the isolated workflow tests in another terminal:

```powershell
$env:DEPARTMENTAI_DATABASE_ENV = "test"
.\.venv\Scripts\python.exe -m backend.database.initialize_local_database
.\.venv\Scripts\python.exe -m pytest backend\tests -q
```

The integration test creates provisioned synthetic Student/Official/DUGC accounts and a unique synthetic application, verifies bearer login and ownership-scoped reads, empty ordinance retrieval and status history, uploads/downloads synthetic PDF bytes in pytest's temporary directory, walks allowed status transitions, assigns a DUGC review, records a synthetic committee decision, checks role visibility and logout revocation, and deletes only its exact test marker from `departmentai_test`. It also checks database-unavailable behavior, institutional-profile login refusal, and upload-size limits. Empty retrieval tables contain no copied institutional material; AI analysis and external-provider calls are not exercised.

For the local browser demo, explicitly set `DEPARTMENTAI_DATABASE_ENV=development`, initialize the schema, and create synthetic accounts using the development-only seeder documented in the root README. The seeder requires three synthetic passwords from the current shell, does not print them, and refuses to seed outside the fixed `departmentai_dev` database. It reuses an active synthetic workflow and creates a new draft after the previous one reaches a terminal status; it never resets completed records. The default API address is port 8000 and the default frontend origin is port 5500; if a listener is already using either port, do not take over or terminate it without its owner's approval. Use an alternate port, configure the exact `CORS_ALLOWED_ORIGINS`, and set `globalThis.DEPARTMENTAI_API_BASE_URL` in `frontend/config.js` to the matching API address.

The local schema initializer also provisions the analysis tables required by eligibility, deficiency, document extraction, and AI-assisted application analysis. In the 2026-10-25 follow-up check, these five tables were added to both isolated development and test profiles (and a second development initialization created zero tables). Browser requests for eligibility and deficiencies on synthetic application 3 returned HTTP 200 with empty results because it has no requirements. AI-assisted analysis returned HTTP 200 and persisted analysis ID 1 after calling the configured Gemini service with synthetic-only context. Do not use these mutating/AI-backed actions with institutional records without data, privacy, and provider approval.

### Academic Assistant knowledge readiness — 2026-10-25

The Assistant requires ordinance chunks in the selected database; having source PDFs and processed JSON files on disk alone is not sufficient. The isolated development database was populated with the 246 precomputed undergraduate ordinance chunks using the command above. Before ingestion, `/ask` had no retrieved context and answered that context was insufficient. After ingestion, a browser test of “What are the rules for late registration?” returned a sourced answer. This result applies only to the local synthetic development profile; institutional knowledge ingestion and deployment remain separately controlled.

### Latest local browser/API integration check — 2026-10-25

- This checkout's static frontend was served at `http://127.0.0.1:5502/` and returned HTTP 200. Its browser API base was explicitly set to `http://127.0.0.1:8001` for the test; the development API process was configured to allow only `http://127.0.0.1:5502` through `CORS_ALLOWED_ORIGINS`.
- An older API already bound port 8000 and returned HTTP 404 for `/health/live`; it was not stopped or modified. The port-5500 listener was also left untouched; historical diagnostics identify it as serving another checkout. The alternate API on port 8001 returned HTTP 200 from `/health/live`, `/health/ready`, and `/openapi.json`.
- Real browser requests from the allowed frontend origin completed CORS preflights and actual API calls. Synthetic Student, Official, and DUGC sign-ins returned HTTP 200. Student, Official, and DUGC application lists returned HTTP 200; application detail, document metadata, status history, committee reviews, and empty ordinance context reads returned HTTP 200.
- The Official browser workflow performed five allowed synthetic status transitions and assigned a DUGC review (all HTTP 200). The DUGC browser workflow recorded a synthetic APPROVED decision (HTTP 200). The Student browser displayed that human decision and status history without exposing the reviewer identity. No AI/provider endpoint was called.
- One current TCP reachability check to institutional PostgreSQL `10.219.45.43:5432` returned `False`; no credentials or institutional SQL were used. This does not distinguish missing VPN/private routing from a stopped/filtered remote service. The local development database passed readiness; it does not establish institutional connectivity.
- Responsive checks at requested widths 376, 768, and 1281 reported no horizontal overflow; a keyboard Tab reached a button with a solid 2px focus outline. Screen-reader behavior, institutional identity-provider behavior, and real authorization policy remain unverified.

## Historical local connectivity findings — 2026-10-23

- The running API process uses the current repository checkout and its process environment reports `DB_HOST=10.219.45.43`, `DB_PORT=5432`. The current checkout has a `.env`; `backend/database/connection.py` calls `load_dotenv()` with default discovery. Credential values were not printed. The frontend API URL is `http://127.0.0.1:8000` because `frontend/config.js` leaves the override empty.
- Network diagnosis: Wi-Fi is up with a default route through `10.241.172.178`; the listed McAfee VPN adapter is disconnected and no Windows VPN profiles were returned. One ICMP probe to `10.219.45.43` timed out and TCP `10.219.45.43:5432` was unreachable. TCP `127.0.0.1:5432` works but is a separate local PostgreSQL endpoint. These observations do not identify whether the remote host is down, filtered, or reachable only through an unavailable institutional VPN.
- Required external action: ask the network/database administrator to restore the approved VPN/private-network route and verify the PostgreSQL service and firewall for `10.219.45.43:5432`. Do not point the application at loopback or change database configuration as a substitute.
- Current port-5500 owner: Python 3.12 `python.exe -m http.server 5500 --bind 127.0.0.1`, PID 4076, working directory `C:\Users\sojwa\OneDrive\Desktop\sojwal_proj\DepartmentAI-Agentic-Academic-Governance\frontend`. This is a different checkout than the current `sojwal_proj2` repository. The listener accepts TCP, then closes a raw HTTP `GET /` with zero response bytes; its specific server-side reason is not established. Do not terminate or replace it without the process owner's authorization.
- Port 5501's Python listener serves the current checkout's `frontend` directory and the UI returns HTTP 200. At the time of the earlier checks, the running API had not loaded the changed CORS configuration; its preflight from 5501 returned HTTP 400. Port 5500/localhost preflight returned HTTP 200, but the existing port-5500 listener did not serve this checkout.
- A temporary static server bound to IPv6 loopback `[::1]:5500` returned HTTP 200 directly. `localhost` resolves to both `::1` and `127.0.0.1`; browser navigation still failed a role-selector module request with `net::ERR_EMPTY_RESPONSE` while the broken IPv4 listener was present. The temporary server was stopped; this is not a viable bypass.
- Final previous check at 21:14 +05:30: port 5500 PID 4076 remains rooted in the other checkout and `GET /` again closed without an HTTP response. Browser fetch to `http://127.0.0.1:8000/openapi.json` from the current port-5501 page failed with CORS (`net::ERR_FAILED`) because the existing API process was running the prior configuration. Direct `GET /openapi.json` returned HTTP 200, but no business-data endpoint was live-verified.
- A fresh browser navigation to `http://127.0.0.1:5500/` failed with `ERR_EMPTY_RESPONSE (-324)`. The role previews on port 5501 are UI-only and are not an integration workaround.
- Current remediation: backend source now explicitly allows port 5501 for local development; backend tests verify that CORS policy. The previously confirmed API process was restarted from this checkout to load it. Port 5500 remains owned by the other checkout and must not be terminated or replaced without its owner's authorization. No frontend/API proxy or browser-security bypass was introduced.
- Latest browser verification after restarting the confirmed API from this checkout: page `http://127.0.0.1:5501/` successfully fetched `http://127.0.0.1:8000/openapi.json` with a non-simple JSON content-type request, exercising browser preflight and the actual GET; response was HTTP 200, `application/json`, OpenAPI 3.1.0 with 18 paths. This proves browser CORS and schema reachability only, not database connectivity or any business workflow. Port 5500 still fails browser navigation with `ERR_EMPTY_RESPONSE (-324)` and remains untouched.
- Latest safe API check: `GET /openapi.json` returned HTTP 200 in 73 ms and declared 18 paths / 19 operations. It is schema availability only. No authorized known application identifier was available, and no database-backed read or write was issued during this recheck.

## Local integration results — 2026-10-24

- The browser loaded this checkout's frontend from `http://127.0.0.1:5501/` (the unrelated listener on port 5500 was not stopped, changed, or reused). Actual browser `GET` requests to `http://127.0.0.1:8000` succeeded without CORS errors for `/applications/1`, `/applications/1/status-history`, `/applications/1/documents`, `/applications/1/committee-reviews`, and `/applications/1/ordinance-retrieval`; each returned HTTP 200. The application was a synthetic local development record and was removed afterward using its exact synthetic marker.
- These requests used the explicitly selected `development` profile and the isolated `departmentai_dev` database. `departmentai_test` was used by the backend integration suite. Initialization was rerun successfully and idempotently for both profiles (zero tables needed creation).
- Tests: `pytest backend\\tests -q` — 17 passed, one Starlette deprecation warning; `pytest tests\\test_guardrails.py -q` — 10 passed; JavaScript syntax — 19 files passed; API, login preview, and role-workspace Node tests passed.
- The institutional endpoint `10.219.45.43:5432` remains unreachable based on the prior bounded TCP check; no institutional database request or write was made. Local success does not establish institutional service health or production integration. Port 5500 remains unresolved; the working local browser origin is port 5501.
- Application-list and staff/committee queue routes, authentication, record-level authorization, and document-content download remain unsupported. AI/provider workflows were not run. Local integration tests use synthetic data only and do not establish live role permissions.

## Production requirements before deployment

1. Obtain explicit project-owner approval for the target environment and backend security work.
2. Implement and independently review backend authentication, role/record authorization, student ownership rules, committee assignment permissions, and audit visibility.
3. Select the hosting provider, production DNS names, TLS termination, network boundaries, and operational owner.
4. Provision a dedicated PostgreSQL database and least-privilege account. Apply only reviewed, non-destructive schema setup; confirm pgvector if the chosen features require it.
5. Store secrets in the hosting provider's secret manager. Do not copy `.env` to static hosting or include secrets in frontend assets.
6. Set `CORS_ALLOWED_ORIGINS` to the exact approved production frontend origin(s); do not use wildcard origins.
7. Set the production HTTPS API origin in `frontend/config.js` during the deployment build/release.
8. Confirm file upload size/type/path protections, retention policy, backup policy, logging redaction, incident response, and data classification.
9. Run the role-specific end-to-end and security tests in `docs/END_TO_END_VERIFICATION_REPORT.md` against an isolated staging database using approved test identities/data.
10. Obtain sign-off for accessibility, privacy, security, database recovery, and operations before any production data is used.

## Database safety, backup, and recovery

- Never run destructive schema or cleanup commands against production/shared data.
- Confirm the target database and environment before running any SQL or migrations.
- Back up with provider-approved encrypted storage and restricted access. A local PostgreSQL custom-format backup can be created with `pg_dump --format=custom --file <protected-backup-file> <database-name>` after connection variables have been securely configured.
- Verify a backup with `pg_restore --list <protected-backup-file>` and a documented restore drill into a separate recovery database.
- Do not use `pg_restore --clean` against an existing production database. Restore only to a newly provisioned, explicitly approved recovery target and follow the provider's recovery runbook.
- Define retention, encryption-at-rest, encryption-in-transit, access logging, and recovery-point/recovery-time objectives with the institution before launch.

## Health checks, logs, and smoke checks

The current API exposes `/docs`, `/redoc`, and `/openapi.json`; these are API documentation/schema endpoints, not database readiness checks. No dedicated health/readiness route was found. Do not treat HTTP 200 from `/docs` as proof that PostgreSQL, AI, or application workflows work.

For an approved staging environment, smoke-check:

- Frontend page returns HTTP 200 over HTTPS.
- API documentation/OpenAPI visibility matches the institution's publication policy.
- A documented non-sensitive read-only database check succeeds.
- Approved test identity can authenticate and can access only permitted records/actions.
- Application reads, document access, committee decisions, and audit views enforce server-side permissions.
- CORS, TLS, errors, logs, backup restore, and rollback are verified.
- M09/M10 calls are tested only with approved quotas/costs and isolated data.

Use the staging acceptance tests before production. Do not create application records or invoke AI merely to test health.

## Rollback

- Keep the previous static frontend release and API release available until smoke checks pass.
- Roll back the application release through the hosting provider's approved release mechanism.
- Treat database schema/data rollback as a separate reviewed recovery operation. Do not automatically reverse migrations or delete data.
- Record who approved the rollback, affected release identifiers, database backup/recovery point, and post-rollback checks.

## Current blockers

- Institutional identity-provider integration and trusted account provisioning are not configured. Local development bearer auth does not authorize institutional identities or records.
- Audit visibility is intentionally denied until a privacy policy and server-side redaction rules are approved.
- Production CORS origins and hosting target have not been approved/configured.
- The configured institutional PostgreSQL endpoint `10.219.45.43:5432` failed the latest TCP reachability check; a network/database administrator must restore the approved VPN/private route and verify PostgreSQL service/firewall status.
- The verified local browser integration used port 5502 and a local API on port 8001. Existing listeners on ports 5500 and 8000 were not taken over; port 8000's existing API returned 404 on `/health/live`.
- Local synthetic queues and workflow writes are implemented and browser-verified. This does not establish institutional role policy, IdP integration, audit policy, AI/provider operation, or access to real records.
- Full screen-reader testing, approved production origins, hosting target, operational controls, and deployment sign-off remain outstanding.

Until these blockers are resolved and independently verified, the application must remain a local synthetic development environment and must not be described as production-secure or deployment-ready.

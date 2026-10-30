# DepartmentAI Frontend

This folder contains the DepartmentAI browser application. It is plain HTML,
CSS, and JavaScript modules; there is no frontend package install or build step.
Run it through a local HTTP server rather than opening `index.html` directly.

## Requirements

- Python 3.10+ available on `PATH` (used only to serve the static files).
- The DepartmentAI API running and reachable from the browser.
- For local role-based development, a configured local PostgreSQL database and
  provisioned synthetic accounts are also required by the API.

## Configure the API URL

The frontend reads `globalThis.DEPARTMENTAI_API_BASE_URL` from
[`config.js`](./config.js). Its checked-in local default is:

```js
globalThis.DEPARTMENTAI_API_BASE_URL ??= "http://127.0.0.1:8002";
```

If the API runs at a different address or port, change this value to the
API's origin only (scheme, host, and optional port), for example:

```js
globalThis.DEPARTMENTAI_API_BASE_URL ??= "http://127.0.0.1:8000";
```

For HTTPS hosting, configure the HTTPS API origin. Do not put passwords,
database credentials, or API keys in this file. Configure the API's
`CORS_ALLOWED_ORIGINS` with the exact frontend origin; do not use a wildcard.

## Run locally on Windows

Open two PowerShell terminals at the repository root.

### 1. Start the API

The local development database profile reads `.env.development`, which should
contain the local `departmentai_dev` connection settings. Create it from
`.env.development.example` and configure the database before starting the API.
The development profile refuses non-loopback hosts and any database other than
`departmentai_dev`.

```powershell
$env:DEPARTMENTAI_DATABASE_ENV = "development"
$env:CORS_ALLOWED_ORIGINS = "http://127.0.0.1:5500"
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8002
```

For isolated local acceptance, use the separate `.env.test` profile only after
the application resolver confirms the loopback database is exactly
`departmentai_test`. This does not create or migrate a database; use only
synthetic test accounts/data and the existing cleanup-safe integration
fixtures. Keep Module II unconfigured unless its own isolated profile and
database are available.

```powershell
$env:DEPARTMENTAI_DATABASE_ENV = "test"
$env:CORS_ALLOWED_ORIGINS = "http://127.0.0.1:5500"
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8002
```

### Optional persistent synthetic Module I demo

The opt-in local demo provisions only the reserved `demo.*` users and DUGC
memberships in the existing `departmentai_test` database. It never creates or
migrates a database, changes existing account attributes/passwords, or adds
application records. It also writes a synthetic M.Tech rule source and
manifest under `.local-demo\sources\` and idempotently indexes its two chunks
in the test database. The source is available only through its fixed
`TEST_ONLY` policy, exact hash, explicit demo flag, and loopback test profile.
The generated application and governance policies explicitly state that they
are synthetic, not institutional approval. The demo Student identity is
recognized only for its reserved synthetic identifier when
`DEPARTMENTAI_LOCAL_DEMO=1` and the explicit test database profile is active.
The default policy files and institutional profile remain unchanged.

Run once from the repository root after verifying `.env.test` points to the
intended loopback `departmentai_test` database:

```powershell
$env:DEPARTMENTAI_DATABASE_ENV = "test"
.\.venv\Scripts\python.exe -m backend.database.seed_local_demo
```

The synthetic usernames and generated passwords are stored in the ignored
`.local-demo\credentials.json`; do not copy credentials into source, logs, or
screenshots. On Windows the file inherits access permissions from its parent
folder, so ensure the checkout is private to the current user. To start the API
with the optional demo-only policy and identity, set these variables in the
same PowerShell terminal:

```powershell
$env:DEPARTMENTAI_DATABASE_ENV = "test"
$env:DEPARTMENTAI_LOCAL_DEMO = "1"
$env:DEPARTMENTAI_APPLICATION_POLICY_CONFIG = (Join-Path (Get-Location) ".local-demo\application-policies-demo-v2.json")
$env:DEPARTMENTAI_GOVERNANCE_WORKFLOW_CONFIG = (Join-Path (Get-Location) ".local-demo\governance-workflows.json")
$env:CORS_ALLOWED_ORIGINS = "http://127.0.0.1:5500"
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8002
```

Do not configure `DEPARTMENTAI_LOCAL_DEMO` or the generated policy paths for
development, institutional, staging, or production services. The synthetic
workflow is for local demonstration only and does not verify institutional
identity, policy approval, signatory authority, or external integrations.
The seeder requires the project's embedding model to already be available
locally; it does not download model assets.

In either profile, verify `http://127.0.0.1:8002/health/ready` before using
the UI. It must return `{"status":"ready"}`; this checks the configured
database connection and required schema.

If dependencies are not installed yet, create the virtual environment and
install the repository requirements first:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

The local database/schema must already be initialized. See the root
[`README.md`](../README.md) and [`docs/DEPLOYMENT_GUIDE.md`](../docs/DEPLOYMENT_GUIDE.md)
for isolated database setup. Do not use institutional data or credentials for
local development.

### Load ordinance knowledge for local Assistant queries

The repository includes the UG, M.Tech/Masters, and Ph.D. ordinance PDFs and
validated processed assets. To load the latter two corpora into the isolated
development knowledge base, use a PowerShell terminal at the repository root:

```powershell
$env:DEPARTMENTAI_DATABASE_ENV = "development"
.\.venv\Scripts\python.exe -m backend.ingest_knowledge_base --programme MTECH
.\.venv\Scripts\python.exe -m backend.ingest_knowledge_base --programme PHD
```

The existing UG corpus is retained; ingestion of an already indexed corpus
fails rather than duplicating chunks. The Assistant's **Ordinance scope**
selector uses source-filtered UG, M.Tech/Masters, or Ph.D. retrieval. This
selector is informational only: it does not verify the signed-in student's
programme and does not enable programme-specific application forms,
eligibility checks, or DUGC/DMPC/DDPC routing. PG Diploma is not configured.
The reference snapshots also contain synthetic committee data; it is excluded
from the main application's imported knowledge assets.

### 2. Start the frontend

In the second PowerShell terminal, from the repository root:

```powershell
python -m http.server 5500 --bind 127.0.0.1 --directory .\frontend
```

The `--directory .\frontend` argument is important: without it, Python may
serve the repository root instead of this frontend.

Open:

```text
http://127.0.0.1:5500/
```

Keep both terminal processes running while using the application. Stop each
server with `Ctrl+C` in its own terminal.

## Verify startup

- Frontend: `http://127.0.0.1:5500/` should show the DepartmentAI account-type
  sign-in page.
- Backend readiness: `http://127.0.0.1:8002/health/ready` should return
  `{"status":"ready"}` when the local database is reachable and initialized.
- API documentation: `http://127.0.0.1:8002/docs`.

The app uses server-verified synthetic Student, Official, or DUGC accounts in
the local development profile. The role selector does not grant permissions.
The browser persists the bearer token in `localStorage` and `sessionStorage`
so reloads can validate and restore the session; passwords are not stored.
Signing out clears browser storage and revokes the session.

## Module II — Faculty & Research

The authenticated sidebar shows **Faculty & Research** only when
`GET /module2/capabilities` reports a supported permission for the current
account. The page uses the same bearer token and connects to
`GET /module2/faculty`, `GET /module2/faculty/{faculty_id}`,
`GET /module2/research/records/{publications,projects,achievements}`,
`GET /module2/research/statistics`, and, for explicitly granted dataset
permissions, `GET /module2/export/datasets` and
`GET /module2/export/{dataset}/download`. With the separate
`module2.data_quality.read` grant it also loads
`GET /module2/data-quality/issues`, a bounded, read-only scan of schema-backed
required values, persisted date/year inconsistencies, and heuristic duplicate
suggestions.
Accounts granted `module2.reports.generate` also see the separate **Reporting**
view. It discovers a fixed catalogue of five configurable draft templates,
requests a server-scoped preview with at most 20 sample rows, and downloads
server-generated DOCX, XLSX, or PDF files only when each renderer is available.
Report templates, data, and output columns are allow-listed by the backend;
the browser cannot choose departments. Results are labeled draft/not approved
and include the actual template version, generation time, scope, filters,
counts, and limitations. These are not official Ministry/accreditation
templates, and no report history or approval workflow exists. This Reporting
view is distinct from the existing dataset **Reports & exports** view.

The browser does not choose or submit a department scope; the server applies
the current account's exact grant. Statistics have no period-filter contract.
Data-quality findings can be inspected but cannot be reviewed/dismissed or used
to change records because no authorized persisted review/audit workflow exists.
Supervision, faculty chatbot, and formal report approval are not available.
If no Module II grant or isolated database profile is
configured, the page displays the corresponding blocked state instead of
sample records or zero counts. See the root
[`README.md`](../README.md) and [`docs/API_CONTRACT.md`](../docs/API_CONTRACT.md)
for the operator-managed profile and permission setup. No database or
institutional data was used for frontend unit tests.

## Troubleshooting

- **Directory listing or missing `app.js`/`config.js`:** restart the static
  server from the repository root using the `--directory .\frontend` command
  above.
- **Backend connection error:** confirm the API is listening on port 8002 and
  that `frontend/config.js` points to that same API origin.
- **CORS error:** restart the API with `CORS_ALLOWED_ORIGINS` set to the exact
  browser origin, including scheme and port, such as
  `http://127.0.0.1:5500`.
- **Database readiness failure:** confirm `DEPARTMENTAI_DATABASE_ENV` is
  `development`, `.env.development` points to loopback `departmentai_dev`,
  PostgreSQL is running, and the local schema has been initialized.
- **Port already in use:** choose another unused frontend port and set
  `CORS_ALLOWED_ORIGINS` to that port's exact origin. Do not stop another
  process unless you have confirmed it belongs to this project.

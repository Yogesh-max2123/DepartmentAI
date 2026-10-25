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
globalThis.DEPARTMENTAI_API_BASE_URL ??= "http://127.0.0.1:8001";
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
$env:CORS_ALLOWED_ORIGINS = "http://127.0.0.1:5502"
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8001
```

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

### 2. Start the frontend

In the second PowerShell terminal, from the repository root:

```powershell
python -m http.server 5502 --bind 127.0.0.1 --directory .\frontend
```

The `--directory .\frontend` argument is important: without it, Python may
serve the repository root instead of this frontend.

Open:

```text
http://127.0.0.1:5502/
```

Keep both terminal processes running while using the application. Stop each
server with `Ctrl+C` in its own terminal.

## Verify startup

- Frontend: `http://127.0.0.1:5502/` should show the DepartmentAI account-type
  sign-in page.
- Backend readiness: `http://127.0.0.1:8001/health/ready` should return
  `{"status":"ready"}` when the local database is reachable and initialized.
- API documentation: `http://127.0.0.1:8001/docs`.

The app uses server-verified synthetic Student, Official, or DUGC accounts in
the local development profile. The role selector does not grant permissions.
The browser keeps the bearer token in tab-scoped session storage so a reload
can validate and restore the session; passwords are not stored. Signing out
revokes the session.

## Troubleshooting

- **Directory listing or missing `app.js`/`config.js`:** restart the static
  server from the repository root using the `--directory .\frontend` command
  above.
- **Backend connection error:** confirm the API is listening on port 8001 and
  that `frontend/config.js` points to that same API origin.
- **CORS error:** restart the API with `CORS_ALLOWED_ORIGINS` set to the exact
  browser origin, including scheme and port, such as
  `http://127.0.0.1:5502`.
- **Database readiness failure:** confirm `DEPARTMENTAI_DATABASE_ENV` is
  `development`, `.env.development` points to loopback `departmentai_dev`,
  PostgreSQL is running, and the local schema has been initialized.
- **Port already in use:** choose another unused frontend port and set
  `CORS_ALLOWED_ORIGINS` to that port's exact origin. Do not stop another
  process unless you have confirmed it belongs to this project.

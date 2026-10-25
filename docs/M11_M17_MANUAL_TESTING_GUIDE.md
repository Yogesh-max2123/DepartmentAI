# M11–M17 Manual Testing Guide

This guide describes the current student frontend and the real backend contracts. Live verification is currently blocked by a PostgreSQL connection timeout. Do not treat this guide as evidence that the live workflows have passed.

## A. Prerequisites and startup

### Requirements

- Windows PowerShell and Git.
- Python with the project dependencies installed. The current workspace `.venv` is Python 3.12.0; the README also records an earlier development environment of Python 3.14.6. Use the version associated with the installed environment rather than assuming both are configured.
- Node.js for the frontend API contract test; the current workspace ran Node 22.16.0.
- PostgreSQL and the `vector` extension for database-backed routes. The README lists PostgreSQL 18 and pgvector 0.8.6.
- A reachable **isolated local test database** before creating applications, uploading files, changing statuses, assigning committees, recording decisions, or invoking analysis/assistant operations.
- The project root `.env` must define the required variable names: `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DEPARTMENTAI_DB_PASSWORD`, and (only for Gemini-backed operations) `GEMINI_API_KEY`. This list names variables only. Never print their values or commit the `.env` file.
- Backend CORS currently permits only `http://127.0.0.1:5500` and `http://localhost:5500`.

### Confirm the project root and Python environment

```powershell
$Repo = 'C:\Users\sojwa\OneDrive\Desktop\sojwal_proj2\DepartmentAI-Agentic-Academic-Governance'
Set-Location $Repo
Get-Location
.\.venv\Scripts\python.exe --version
```

If `.venv` is not present in another checkout, restore/install dependencies only according to that checkout's setup documentation. Do not copy this workspace's virtual environment.

### Check ports before starting services

```powershell
Get-NetTCPConnection -State Listen -LocalPort 5500,8000 -ErrorAction SilentlyContinue |
  Select-Object LocalAddress,LocalPort,OwningProcess
```

If a port is occupied, inspect the exact process before acting:

```powershell
$ProcessIdToInspect = 1234 # Replace with the OwningProcess reported above.
Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessIdToInspect" |
  Select-Object ProcessId,Name,CommandLine
```

Do not stop another user's process. Prefer `Ctrl+C` in the terminal that started your own server. If the process is yours and its terminal is unavailable, stop only the inspected PID with `Stop-Process -Id $ProcessIdToInspect`—never use a process name or wildcard.

### Start the backend

In a dedicated PowerShell terminal:

```powershell
Set-Location 'C:\Users\sojwa\OneDrive\Desktop\sojwal_proj2\DepartmentAI-Agentic-Academic-Governance'
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Keep the terminal open. Stop it with `Ctrl+C`.

### Start the frontend

In a second PowerShell terminal:

```powershell
Set-Location 'C:\Users\sojwa\OneDrive\Desktop\sojwal_proj2\DepartmentAI-Agentic-Academic-Governance\frontend'
python -m http.server 5500 --bind 127.0.0.1
```

Keep the terminal open. Stop it with `Ctrl+C`. Open:

- Student site: `http://127.0.0.1:5500/`
- API docs: `http://127.0.0.1:8000/docs`
- OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`

If port 5500 is unavailable, do not silently use another port for integrated browser testing: the backend CORS list does not include other ports. A different port can serve the static UI but browser API calls will be rejected unless the backend's CORS configuration is changed by an authorized maintainer.

### Verify reachability

```powershell
Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:5500/' |
  Select-Object StatusCode
Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:8000/openapi.json' |
  Select-Object StatusCode
```

Expected: HTTP 200 for both. This does not prove that PostgreSQL-backed routes or Gemini requests work. If either database-backed call times out, stop live workflow testing and resolve the isolated test database connection first.

## Safety and current blockers

- The backend routes currently have no authentication or authorization. Student/Official/DUGC role selection is local prototype UI state, not a permission check. Never test privileged write routes against production or shared data.
- `POST /applications` writes an application, initial status history, and an audit record. It is not a read-only smoke test.
- Document upload/extract, status changes, processing, committee assignment/decision, eligibility/deficiency analysis, and AI analysis can write database records. AI/assistant paths may call an external paid provider.
- The audit endpoint returns raw audit records. Student and staff frontends do not call it because client-side filtering cannot secure unauthenticated data.
- Official and DUGC currently provide read-only known-ID lookup previews, not authenticated queues. Their audit access and governance write controls are intentionally withheld.
- Do not probe `GET /applications/{id}/eligibility` or `GET /applications/{id}/deficiencies` as read-only checks: source inspection shows they delete and recreate stored records, and eligibility may call Gemini.
- CORS preflight is allowed from `http://127.0.0.1:5500` (HTTP 200) and rejected from `http://127.0.0.1:5501` (HTTP 400). Do not use a browser-security bypass or unapproved proxy.
- A create-form request during the current browser mock setup remained pending, and the read-only database check for its synthetic identifier timed out. Verify whether any `STUDENT-TEST` / `Test request` rows exist before considering any cleanup. Do not delete records blindly.

## B. Module test cases

### M11 — Status and application lifecycle

#### M11-01 — Current status and chronological status history

- [ ] PASS  [ ] FAIL
- Purpose: Confirm that the current status comes from the application record and history comes from the service, not client-generated transitions.
- Preconditions: A known application ID in the isolated test database; backend and frontend reachable.
- Browser URL: `http://127.0.0.1:5500/`
- Browser path: Sign in as Student → Create Application → create only in the isolated test DB → select **View application details** in the confirmed success panel → review **Current status** and **Status history**.
- Read-only PowerShell checks (replace `123` with the application ID):

```powershell
$Api = 'http://127.0.0.1:8000'
$ApplicationId = 123
Invoke-RestMethod "$Api/applications/$ApplicationId"
Invoke-RestMethod "$Api/applications/$ApplicationId/status-history"
```

- Expected HTTP/result: `GET /applications/{id}` returns 200 and its `status`; status-history returns 200 with `application_id` and `history[]` containing `old_status`, `new_status`, `changed_by`, `reason`, and `created_at`. Missing application returns 404.
- Expected UI: Current status agrees with the GET response. History is chronological and contains only returned data. No student status-change or process button is shown.
- Database verification, read-only:

```sql
SELECT id, status, updated_at
FROM applications
WHERE id = 123;

SELECT id, old_status, new_status, changed_by, reason, created_at
FROM application_status_history
WHERE application_id = 123
ORDER BY created_at ASC, id ASC;
```

- Negative test: Use an unused numeric ID for GET and expect 404. Do not issue an invalid PATCH against an existing record.
- Write-path test: `PATCH /applications/{id}/status` and `POST /applications/{id}/process` must only be tested on a disposable local record. The former writes status history; process runs the full pipeline and may call Gemini. The backend currently has no auth, so these are not safe on shared data.
- Contract sample for an authorized local status transition (only if explicitly approved and isolated):

```json
{
  "new_status": "SUBMITTED",
  "changed_by": "TEST-STAFF",
  "reason": "Manual M11 test"
}
```

- Failure checks: Wrong/missing ID, database timeout, invalid transition (expected 400), and absent live response must be shown as failure/unavailable—not as a successful status change.

### M12 — Committee and human decision display

#### M12-01 — Display committee record separately from AI output

- [ ] PASS  [ ] FAIL
- Purpose: Verify that human decisions are labeled as committee decisions and are not confused with AI recommendations.
- Preconditions: An application with a committee review in the isolated test database.
- Browser URL/path: `http://127.0.0.1:5500/` → open the application → **Committee decisions** and **AI-Assisted Analysis**.
- Read-only command:

```powershell
$Api = 'http://127.0.0.1:8000'
$ApplicationId = 123
Invoke-RestMethod "$Api/applications/$ApplicationId/committee-reviews"
```

- Expected response: 200 with `application_id` and `reviews[]`; each review may include `committee_type`, `assigned_at`, `review_status`, `decision`, `decision_reason`, `decided_by`, and `decided_at`.
- Expected UI: Pending/completed state and any recorded decision/reason are shown as a committee record. `decided_by` and internal identifiers are not displayed. AI analysis remains separately marked advisory.
- Database verification, read-only:

```sql
SELECT id, application_id, committee_type, assigned_at, review_status,
       decision, decision_reason, decided_at
FROM committee_reviews
WHERE application_id = 123
ORDER BY assigned_at ASC, id ASC;
```

- Negative test: Missing application returns 404; empty `reviews` shows the truthful empty state; API failure shows an error/retry state.
- Write-path test only on an isolated local DB with explicit authorization:

```json
POST /applications/123/committee
{"committee_type":"DUGC"}
```

Allowed committee types are `DUGC`, `DMPC`, and `DDPC`. Recording a decision uses `PATCH /committee-reviews/{review_id}/decision` with:

```json
{
  "decision": "APPROVED",
  "decision_reason": "Manual test reason",
  "decided_by": "TEST-COMMITTEE"
}
```

These calls change records and the decision endpoint may also update application status/history. Do not run them on real or shared applications. Student UI does not offer these write controls.

### M13 — Audit and history presentation

#### M13-01 — Student-safe activity summary

- [ ] PASS  [ ] FAIL
- Purpose: Confirm that unauthenticated raw audit records are not requested or rendered.
- Status: **BLOCKED for live API testing.** The unauthenticated audit endpoint returns raw actor IDs/details; the application activity panel must remain unavailable until server-side authentication and visibility policy exist.
- Expected UI behavior: An explicit unavailable state is shown and no audit request is made until authentication, ownership checks, and server-side audit visibility policy exist.

- Negative test: Confirm that navigating to application details does not issue a request to `/audit-logs`.
- Security limitation: The API has no authentication and returns raw values. Do not expose this route to untrusted users without backend authorization and an explicit student-visibility policy.

### M14 — Settings

#### M14-01 — Session profile and sign-out

- [ ] PASS  [ ] FAIL
- Purpose: Confirm truthful profile data and existing local sign-out.
- Preconditions: Sign into the Student role. Development login is not backend authentication.
- Browser URL/path: `http://127.0.0.1:5500/` → choose Student → enter a test name and identifier → **Sign In** → **Settings** in the sidebar.
- Expected UI: Name, role, and identifier are from the current in-memory session; prototype limitation note is visible; no password/security management is claimed.
- Click **Sign out**. Expected result: role-selection screen returns. No database request or account mutation occurs.
- Negative checks: blank identifier is rejected by the existing local login flow; refreshing returns to role selection because session restoration is not implemented.

### M15 — UX, responsive behavior, and accessibility

#### M15-01 — Page and viewport review

- [ ] PASS  [ ] FAIL
- Purpose: Review all Student pages for responsive layout, keyboard usability, labels, and truthful states.
- Preconditions: Frontend server available. Live API is not required for static pages; use a test database only for application details.
- Pages to review: Dashboard, Academic Assistant, My Applications, Create Application, Application Details, Settings.
- Test viewport widths: 1280 px desktop, 768 px tablet, 390 px mobile.
- Actions/checks:
  1. At each size, inspect headings, cards, form labels, buttons, status badges, empty/loading/error states, and long identifiers/text.
  2. At mobile width, open the hamburger menu, choose Settings, and confirm the menu closes and the selected page is operable.
  3. Use Tab/Shift+Tab/Enter/Escape; check visible focus, labels, and the menu's `aria-expanded` value.
  4. Enable the operating-system reduced-motion preference and confirm animated movement is minimized.
  5. Check `document.documentElement.scrollWidth` against `clientWidth`; expected no horizontal overflow.
- Current evidence: JavaScript syntax checks passed; browser verified the Settings profile/sign-out path and mobile menu close. Full page/device/accessibility evaluation is still required.
- Failure checks: clipped controls, keyboard traps, missing labels/focus, horizontal overflow, misleading “System Online” state, or unsupported password/security claims.

### M16 — End-to-end frontend/backend integration

#### M16-01 — Safe application journey

- [ ] PASS  [ ] FAIL
- Purpose: Verify real browser requests, responses, UI rendering, and database persistence across supported endpoints.
- Preconditions: An explicitly isolated test database, verified credentials, working PostgreSQL/pgvector, and permission to create test rows/files. Never use a production/shared database. Do not run Gemini-backed operations without explicit approval and awareness of possible cost/persistence.
- Browser URL: `http://127.0.0.1:5500/`. Keep browser DevTools → **Network** open.
- Start by creating one disposable application in the UI. This writes data. Confirm the returned HTTP 200/response before proceeding; retain the returned `id` and `application_number` as test values.
- Expected browser/API sequence, where supported:
  1. Local Student login and Dashboard.
  2. Create Application → `POST /applications` (body contains `applicant_identifier`, `application_type`, optional `title` and `description`); expect `id`, `application_number`, `status: DRAFT`.
  3. **View application details** → `GET /applications/{id}`; confirm returned fields and current status.
  4. Upload one safe test PDF/JPG/PNG → `POST /applications/{id}/documents` with multipart `file` and optional `document_type`; then `GET /applications/{id}/documents`.
  5. For a PDF only, exercise `GET /applications/{id}/documents/{document_id}/validate`, `POST .../extract`, and `POST .../classify`; confirm visible result/error states.
  6. Read only the known-ID application, document metadata, ordinance retrieval, status-history, and committee-review routes where connectivity and authorization permit. Do not call eligibility/deficiency GETs as reads; they mutate stored results. Do not request raw audit records until a server-side visibility policy is implemented.
  7. Test Academic Assistant `/ask` and AI analysis only after explicit approval for external provider calls and writes.
  8. Open Settings and sign out.
- Sample create payload for a disposable local test DB only:

```json
{
  "applicant_identifier": "MANUAL-TEST-IDENTIFIER",
  "application_type": "Manual test request",
  "title": "M16 isolated test",
  "description": "Disposable local verification record"
}
```

- Safe read-only PowerShell checks after an application ID is known:

```powershell
$Api = 'http://127.0.0.1:8000'
$ApplicationId = 123
Invoke-RestMethod "$Api/applications/$ApplicationId"
Invoke-RestMethod "$Api/applications/$ApplicationId/documents"
Invoke-RestMethod "$Api/applications/$ApplicationId/status-history"
Invoke-RestMethod "$Api/applications/$ApplicationId/committee-reviews"
```

- Expected: Network panel shows actual method/path/status/body; UI mirrors returned data only. Record each request and response. A 4xx/5xx, timeout, CORS failure, or database error is a failure, not a pass.
- Negative tests: Unknown application/document ID (expected 404), unsupported upload extension (400), invalid status transition (400 only on disposable data), malformed inputs, and unavailable backend. Do not retry a write after an ambiguous timeout; inspect the DB first.
- Database verification is read-only. Use the table queries in M11–M13 plus:

```sql
SELECT id, application_id, file_name, document_type, upload_status, uploaded_at
FROM application_documents
WHERE application_id = 123
ORDER BY uploaded_at ASC, id ASC;
```

Confirm the actual document table/columns against the initialized schema before running this query; the source route returns the fields shown in the API contract. Never delete test data until a human confirms the exact row and that it is disposable.
- Current result: Not verified end-to-end. Live application reads and a database connection timed out. A create-form request during mock setup remained pending and possible persistence could not be confirmed; see the safety note above.

### M17 — Final QA and backend-change audit

#### M17-01 — Worktree, test, and handoff checks

- [ ] PASS  [ ] FAIL
- Run from the repository root:

```powershell
Set-Location 'C:\Users\sojwa\OneDrive\Desktop\sojwal_proj2\DepartmentAI-Agentic-Academic-Governance'
git status --short --branch
git diff --name-only
git diff --name-only -- backend
git diff --check -- frontend
node --check frontend\app.js
node --check frontend\services\api.js
node frontend\services\api.test.mjs
.\.venv\Scripts\python.exe -m pytest backend\tests -q
.\.venv\Scripts\python.exe -m pytest tests\test_guardrails.py -q
```

- Search for leftover debug statements:

```powershell
rg -n --glob '*.js' 'console\.log|debugger' frontend
```

- Review every changed path. Preserve existing user changes and untracked files. A nonempty `git diff --name-only -- backend` is not proof that this implementation edited backend code; compare against the pre-task worktree record. Do not run `git clean`, reset, or destructive cleanup.
- Current results: Frontend syntax checks, frontend API tests, backend retrieval tests (2), and guardrail tests (10) passed. `pytest tests -q` did not pass: `tests/test_qa_pipeline.py` could not connect to PostgreSQL. At task start there were already backend modifications and an untracked backend test directory. The full repository is therefore not clean and the literal zero-modified-backend-worktree condition is not met.
- Readiness sign-off: Do not declare ready to proceed beyond M17 until M16 live tests pass in an isolated reachable database, the ambiguous create attempt is checked read-only, the M15 accessibility matrix is completed, and the backend authorization/audit-visibility limitations are resolved by the project owner.

## Test matrix

| Module | Automated check | Browser/live check | Current status |
|---|---|---|---|
| M11 | API helper route/method/payload tests pass | Live DB-backed status/history not verified | Partial; DB blocked |
| M12 | API helper route/method/payload tests pass | Live committee review not verified | Partial; DB blocked |
| M13 | API helper GET contract passes | Live audit route not verified; UI allowlist requires browser-data exercise | Partial; auth limitation |
| M14 | No backend request required | Settings/profile/sign-out checked | Implemented; browser checked |
| M15 | Frontend JS syntax passes | Mobile Settings/menu and no-overflow spot-check; full matrix outstanding | Partial |
| M16 | API helpers tested with local mock server | Real DB/API journey not completed; no live Gemini claim | Blocked |
| M17 | Focused frontend/backend tests pass; full suite blocked | Worktree reviewed; backend changes pre-existed | Partial |

## C. Supported end-to-end journeys

1. **Student session**: local role selection → Student dashboard → Settings/profile → sign out. Authentication is prototype-only.
2. **Application review**: create a disposable test application → open the ID returned by the service → view application data, documents, current status/history, committee review, activity summary, and AI advisory panels where their services are available.
3. **Document review**: upload a test document → list → validate → extract PDF text where supported → classify. These operations may persist data.
4. **Academic guidance**: open Academic Assistant → submit a question → review answer and source display. Live use may contact Gemini; use mocks for routine testing.
5. **Official decision flow**: backend contracts support staff/committee writes, but the student UI does not perform them and current backend routes have no auth. Test only against an isolated DB with explicit authorization.

## D. Final sign-off checklist

- [ ] Automated frontend API tests pass.
- [ ] Relevant backend unit/regression tests pass.
- [ ] Full backend test suite passes with a reachable test database.
- [ ] M09/M10 frontend regressions pass; live AI evidence is recorded separately from historical notes.
- [ ] M11 status/history and M12 reviews are verified against real isolated test data.
- [ ] M13 student visibility policy and backend authorization are confirmed.
- [ ] M14 Settings and logout pass in browser.
- [ ] M15 desktop/tablet/mobile, keyboard, focus, labels, reduced motion, and overflow checks pass.
- [ ] M16 request/response, persistence, and safe negative cases are verified end-to-end.
- [ ] Any ambiguous write is reconciled with a read-only DB check before cleanup.
- [ ] M17 diff/worktree audit is complete and all pre-existing user changes are preserved.
- [ ] No claim of M11–M17 completion is made until the corresponding evidence above exists.

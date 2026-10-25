# Manual End-to-End Workflow Test

This guide is for the local synthetic development environment only. It walks through the Student, Official, and DUGC workspaces using an explicit Student submission and a first-Official-claim shared queue.

> **Queue policy:** Drafts remain private to the owning Student until explicitly submitted. A submitted application enters a shared queue visible to authenticated Officials; the first Official to claim it becomes the assigned processor. This is a local development workflow and does not replace institutional routing or identity policy.

## 1. Safety and test boundaries

- Use only the isolated `departmentai_dev` database and synthetic accounts/data. Never select the institutional profile or use real student information.
- Confirm `DEPARTMENTAI_DATABASE_ENV=development` in the backend terminal before starting FastAPI.
- The seeder creates synthetic accounts, an active draft application, an Official assignment, and DUGC committee membership. It reuses an active draft and does not reset terminal applications.
- Status changes, committee assignment/decisions, uploads, eligibility/deficiency operations, and AI analysis write local records. Use only the synthetic demo application.
- Eligibility and deficiency actions can replace stored records; eligibility can call Gemini. AI analysis contacts Gemini and stores an analysis. The guide identifies those actions before you run them.
- Do not use the app for institutional decisions. AI output is advisory; only a human DUGC decision records approval or rejection.

## 2. Start and verify the local services

Open PowerShell in the repository root:

```powershell
$Repo = 'C:\Users\sojwa\OneDrive\Desktop\sojwal_proj2\DepartmentAI-Agentic-Academic-Governance'
Set-Location $Repo
```

Check the explicit local database profile file exists without printing its contents:

```powershell
Test-Path .env.development
```

If it returns `False`, follow the local PostgreSQL setup in [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md). Never copy institutional credentials into the development profile.

Initialize the additive local schema:

```powershell
$env:DEPARTMENTAI_DATABASE_ENV = 'development'
.\.venv\Scripts\python.exe -m backend.database.initialize_local_database
```

The initializer must report `departmentai_dev`. It is additive and must not be used with the institutional profile.

### Seed or refresh the synthetic demo accounts

The usernames are `synthetic.student`, `synthetic.official`, and `synthetic.dugc`. When these accounts are first created, set three synthetic-only passwords in the current PowerShell process. Enter them at the masked prompts; do not use institutional passwords:

```powershell
$env:DEPARTMENTAI_DATABASE_ENV = 'development'
$env:DEPARTMENTAI_SEED_STUDENT_PASSWORD = [System.Net.NetworkCredential]::new('', (Read-Host -AsSecureString 'Synthetic Student password')).Password
$env:DEPARTMENTAI_SEED_OFFICIAL_PASSWORD = [System.Net.NetworkCredential]::new('', (Read-Host -AsSecureString 'Synthetic Official password')).Password
$env:DEPARTMENTAI_SEED_DUGC_PASSWORD = [System.Net.NetworkCredential]::new('', (Read-Host -AsSecureString 'Synthetic DUGC password')).Password
.\.venv\Scripts\python.exe -m backend.database.seed_local_development
```

Save the passwords in an approved local password manager. The seeder does not print passwords or change passwords on existing accounts. If an account already exists, use the password originally set for it; the seeder will refuse to overwrite the account's password.

### Start FastAPI

In the first PowerShell terminal, keep the development selector set and start the API on the verified development port:

```powershell
Set-Location $Repo
$env:DEPARTMENTAI_DATABASE_ENV = 'development'
$env:CORS_ALLOWED_ORIGINS = 'http://127.0.0.1:5502'
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8001
```

Do not stop another process if port 8001 is occupied. Inspect its owner and choose an available port only after updating both CORS and `frontend/config.js`.

### Start the frontend

In a second PowerShell terminal:

```powershell
Set-Location "$Repo\frontend"
python -m http.server 5502 --bind 127.0.0.1
```

The local [frontend config](../frontend/config.js) should point to `http://127.0.0.1:8001`. Open:

- Website: <http://127.0.0.1:5502/>
- API readiness: <http://127.0.0.1:8001/health/ready>
- API documentation: <http://127.0.0.1:8001/docs>

Expected: the website and API readiness check both return HTTP 200. Readiness verifies the selected local database only; it says nothing about institutional PostgreSQL.

## 3. Test Student sign-in and create form

1. Open the website and select **Student**.
2. Sign in as `synthetic.student` using the locally stored synthetic password.
3. Verify the Student dashboard loads the account's application list and shows only records belonging to that synthetic Student.
4. Open **Create Application**.
5. Enter synthetic-only information:
   - Application type: a short test label such as `LOCAL_MANUAL_TEST`.
   - Title: `Synthetic manual workflow test`.
   - Description: state that this is a synthetic development record.
6. Submit once. Record the returned application ID and application number.
7. Open the new application and confirm its status is `DRAFT`; verify status history begins with `DRAFT`.
8. If testing uploads, use a disposable synthetic PDF or image no larger than 10 MiB. Confirm it appears in the document list. Do not upload real student documents.
9. When the draft is ready for staff review, select **Submit to Official queue**. Confirm the status changes to `SUBMITTED` and history records the transition.
10. Sign in as an Official and open **Applications**. Confirm the submission appears under **Unassigned submissions**. This shared queue is visible to authenticated Official accounts.
11. Select **Claim application**. Confirm the item leaves the unassigned queue and appears under **My assigned applications**. Only the first Official claim succeeds; another claim receives a conflict response.
12. Open the claimed application and continue the supported processing/committee workflow below.

Unsubmitted `DRAFT` applications remain visible only to their owning Student. Do not manually insert assignment rows to bypass the submit-and-claim workflow.

## 4. Continue the claimed application through the synthetic workflow

The submitted and claimed application from the preceding steps can continue through the staff workflow. A separately seeded active application may also be used for the workflow demonstration.

If the seeded application is already `APPROVED`, `REJECTED`, or `CLOSED`, it is a completed record and must not be reset. Rerun the development seeder to create a fresh synthetic draft, then use the new active draft. Never reuse a terminal record for the write steps below.

### Student review before staff processing

On the seeded draft:

1. Confirm the application content and `DRAFT` status.
2. Optionally upload synthetic evidence, then verify metadata and download.
3. Optionally run **Run eligibility analysis**. Confirm the warning, then verify the page displays the returned requirements/results or a truthful empty state. This operation can call AI and replaces prior eligibility results.
4. Optionally run **Refresh deficiency analysis**. Confirm the warning, then verify the findings or a truthful empty state. This operation replaces stored findings.
5. Optionally run **Generate AI analysis**. Confirm the warning and verify that an analysis is displayed with its generated time and metadata. Treat it as advisory, never as the official decision. This action contacts Gemini and stores a new analysis.
6. Open **Status history**, **Documents**, and **Committee decisions**. Check that each view reflects returned data and does not reveal reviewer identity to the Student.

The synthetic demo draft has no copied ordinance knowledge. Empty requirements or findings are valid empty states, not evidence of eligibility.

### Official review and committee assignment

1. Sign out; choose **Official**; sign in as `synthetic.official`.
2. Open **Assigned applications**. Confirm that the seeded synthetic application is listed. If it is not, stop: the Official assignment/session/database configuration needs investigation.
3. Open the exact application ID from the Student view. Confirm the title, current status, documents, and status history match.
4. In **Authorized workflow actions**, advance the record one transition at a time. The ordinary path is:

   `DRAFT → SUBMITTED → DOCUMENT_VALIDATION → PROCESSING → UNDER_REVIEW → COMMITTEE_REVIEW`

   Select only a transition offered by the server. Optionally add a synthetic review note. After each update, verify the new status and refreshed history before proceeding.
5. At `COMMITTEE_REVIEW`, choose **DUGC** and **Assign committee**. Verify a pending review appears in committee records.
6. Sign out of Official.

The current UI/API lets an Official advance `DRAFT` to `SUBMITTED`; there is no Student submit action in this implementation. This is the implemented local test path, not a claim that institutional submission policy is complete.

### DUGC committee decision

1. Choose **DUGC** and sign in as `synthetic.dugc`.
2. Open **Assigned committee applications** or **Committee review**.
3. Look up the same application ID if needed. Verify that the assigned DUGC review is visible.
4. Choose either `APPROVED` or `REJECTED` for this synthetic test and enter a meaningful synthetic rationale. The rationale is required.
5. Select **Record human decision** once. Verify the review becomes completed and the application status matches the human decision.
6. Verify **Decision history**, **Status history**, and the application details show the recorded human outcome. AI recommendations must remain labeled separately.
7. Sign out of DUGC.

The DUGC decision endpoint accepts only `APPROVED` or `REJECTED` and requires committee membership and an assigned review. It is a human decision, not an AI action.

### Official closes the decided application

1. Sign in again as `synthetic.official`.
2. Open **Assigned applications** and the same application ID.
3. Confirm the DUGC decision and current application status (`APPROVED` or `REJECTED`).
4. The server should offer `CLOSED` as the next allowed status. Select `CLOSED`, submit once, and verify the current status and status-history entry.
5. Confirm the record remains visible as a closed assigned record and no further status transitions are offered.

`CLOSED` is terminal. Do not try to reopen or reset the record. Rerun the development seeder for another fresh synthetic draft.

## 5. Alternate status path: corrections

The backend permits this alternate route:

`DOCUMENT_VALIDATION` or `PROCESSING` or `UNDER_REVIEW` → `DEFICIENCY_FOUND` → `CORRECTION_REQUIRED` → `RESUBMITTED` → `PROCESSING`

Only the Official workspace can change status in the current UI. Therefore, use this only to test the implemented status-control API with synthetic data; it does **not** currently provide a Student correction-submission/resubmission UI. After resubmission, continue through `PROCESSING`, `UNDER_REVIEW`, and `COMMITTEE_REVIEW` before committee decision and closure.

Other allowed transitions are returned by the server at each step. `ON_HOLD` can be used only when it appears in the offered transition list; the server defines which statuses can leave hold.

## 6. Read-only checks after each role

Use the application ID from the seeded test and the authenticated UI pages. Confirm:

- Student list/detail are limited to the Student's own records.
- Official queue/detail/actions are limited to assigned records.
- DUGC sees only applications with a review for a committee the user belongs to.
- Current application status agrees with the latest status-history entry.
- Committee review shows `PENDING` before the human decision and `COMPLETED` afterward.
- Student-facing decision/history does not expose `decided_by` or `changed_by`.
- Requests without a valid session or outside the role's assigned scope fail; do not attempt to bypass these checks.
- Audit access remains unavailable until an approved audit-visibility policy exists.

## 7. Current supported flow and gaps

| Stage | Current local status |
|---|---|
| Synthetic Student sign-in | Supported with a provisioned local account |
| Student creates a draft | Supported |
| Student uploads/lists synthetic documents | Supported; 10 MiB upload cap |
| Student submits newly created application to shared Official queue | Supported by explicit Student submission; backend integration test passed |
| Official claims a submitted application | Supported; backend integration test verifies assigned queue visibility and duplicate-claim conflict |
| Seeded synthetic application assigned to Official | Supported by development seeder |
| Official transitions through review and assigns DUGC | Supported for assigned synthetic application |
| DUGC records approval/rejection | Supported for matching membership and assigned review |
| Official closes approved/rejected application | Supported as terminal transition |
| Eligibility/deficiency | Supported locally after analysis tables are initialized; mutating, and eligibility may call AI |
| AI-assisted analysis | Supported locally when Gemini is configured; contacts external AI and persists an advisory analysis |
| Institutional IdP, institutional PostgreSQL, real account/committee provisioning | **Not verified / deployment blockers** |
| Audit log visibility | **Unavailable** pending an approved visibility policy |

Do not interpret the local synthetic demonstration as a fully deployable institutional workflow. Institutional identity, trusted account provisioning, database access, and deployment policy remain unverified.

## 8. Finish safely

- Do not delete database rows or uploaded files manually as routine cleanup. The synthetic records are isolated local development data and can be left for repeatable testing.
- Keep the completed application history intact. Use the seeder to produce another active synthetic draft when needed.
- Stop only the API and static server from the terminals where you started them (`Ctrl+C`).
- Remove seed-password variables from the current PowerShell session when finished:

```powershell
Remove-Item Env:DEPARTMENTAI_SEED_STUDENT_PASSWORD -ErrorAction SilentlyContinue
Remove-Item Env:DEPARTMENTAI_SEED_OFFICIAL_PASSWORD -ErrorAction SilentlyContinue
Remove-Item Env:DEPARTMENTAI_SEED_DUGC_PASSWORD -ErrorAction SilentlyContinue
```

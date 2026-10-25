# DepartmentAI Frontend — Master Implementation & Handoff Plan

## Purpose

This file is the persistent execution plan for completing the **Student frontend of DepartmentAI** while integrating it with the **existing backend without modifying the backend**.

The project uses a plain HTML/CSS/JavaScript frontend. The backend, RAG pipeline, database, and AI functionality already exist and are **READ-ONLY** for this task.

This document is intentionally designed for AI coding agents with limited message/context budgets. Work must be completed in **small, independently verifiable modules**.

---

# 0. NON-NEGOTIABLE PROJECT RULES

## Rule 0.1 — ZERO BACKEND EDITING

The `backend/` directory is strictly read-only.

AI agents MAY:

- inspect backend code
- inspect API routes
- inspect request/response schemas
- inspect models
- run the backend
- call/test APIs
- use backend behavior as the source of truth

AI agents MUST NOT:

- edit `backend/`
- create files in `backend/`
- delete files in `backend/`
- change routes
- change database logic
- change authentication
- change RAG
- change AI logic
- change CORS
- change backend business rules

If a backend issue blocks frontend functionality, document it in the handoff instead of changing the backend.

---

## Rule 0.2 — NO FABRICATED DATA

Never create fake:

- applications
- application numbers
- application counts
- statuses
- student records
- committee records
- AI decisions
- API responses

When backend data is unavailable, use a truthful loading/empty/dependency/error state.

---

## Rule 0.3 — AI IS NOT THE FINAL AUTHORITY

The UI must distinguish:

- AI-Assisted Analysis
- AI Recommendation
- AI-Identified Deficiencies
- AI Confidence

from:

- Official Human Decision
- Committee Decision
- Authorized Approval/Rejection

Never present AI as independently approving/rejecting an academic application.

---

## Rule 0.4 — PRESERVE THE EXISTING ARCHITECTURE

Frontend remains:

- HTML
- CSS
- JavaScript

Do NOT introduce:

- React
- Vue
- Angular
- Tailwind
- Bootstrap
- other frontend frameworks

Keep the existing app shell, routing/navigation conventions, API service architecture, auth scaffolding, design tokens, and modular file structure.

---

## Rule 0.5 — ONE MODULE AT A TIME

An AI coding session must implement **ONE module at a time**.

Do NOT ask an agent to implement Modules 1–10 together.

For every module:

1. Read the master plan.
2. Read `PROJECT_STATE.md`.
3. Inspect current implementation.
4. Implement only the current module.
5. Run/check the relevant functionality.
6. Verify imports/navigation/API calls.
7. Check that `backend/` remains untouched.
8. Update `PROJECT_STATE.md`.
9. Mark the module `DONE`.
10. Commit the completed module when practical.
11. STOP.

Only after the module is verified should the next module begin.

---

# 1. PROJECT STATE FILE

Create and maintain:

`PROJECT_STATE.md`

This is the most important continuity file.

It must always contain:

```text
CURRENT MODULE:
STATUS:
LAST COMPLETED MODULE:
NEXT MODULE:
FILES CHANGED:
APIs VERIFIED:
KNOWN ISSUES:
BACKEND CHANGES: MUST SAY "NONE"
LAST TEST PERFORMED:
NEXT ACTION:
```

Example:

```text
CURRENT MODULE: M05 — Create Application
STATUS: DONE
LAST COMPLETED MODULE: M05
NEXT MODULE: M06 — Application Details
FILES CHANGED:
- frontend/pages/student/create-application.js
- frontend/styles/applications.css

APIs VERIFIED:
- POST /applications

KNOWN ISSUES:
- None

BACKEND CHANGES:
NONE

LAST TEST PERFORMED:
Created a real application through the UI and verified the POST request in Browser Network tab.

NEXT ACTION:
Implement M06 only.
```

An AI agent starting from a new account must read this file before doing anything else.

---

# 2. MODULE STATUS LEGEND

Use only these statuses:

- `NOT_STARTED`
- `IN_PROGRESS`
- `BLOCKED`
- `DONE`
- `VERIFIED`

Recommended progression:

`NOT_STARTED → IN_PROGRESS → VERIFIED`

Do not mark a module `DONE` merely because code was written.

A module is `VERIFIED` only after its acceptance criteria have been checked.

---

# 3. MASTER MODULE ROADMAP

## M00 — Repository Baseline & Architecture Audit

### Objective

Understand the actual repository before changing code.

### Inspect

Frontend:

- `frontend/index.html`
- `frontend/app.js`
- `frontend/services/api.js`
- `frontend/services/auth.js`
- `frontend/components/layout/sidebar.js`
- `frontend/components/layout/topbar.js`
- login files
- student pages
- relevant CSS

Backend:

- application routes
- API schemas
- request/response structures
- server port
- API prefix
- CORS behavior
- application workflow
- existing AI/RAG APIs

### No implementation yet

This module is primarily an inventory/audit.

### Acceptance criteria

- Actual frontend architecture documented
- Actual backend API contracts documented
- Frontend startup command known
- Backend startup command known
- API base URL known
- Existing working files identified
- Backend confirmed READ-ONLY

### Deliverable

Create/update:

`docs/API_CONTRACT.md`

Do not modify backend.

---

# M01 — Frontend API Integration Foundation

### Objective

Ensure the frontend has a clean and reliable way to communicate with the existing backend.

### Work

Inspect and improve `frontend/services/api.js` only where necessary.

Establish:

- API base URL handling
- reusable request helper
- JSON parsing
- error normalization
- loading/error handling conventions
- request method helpers where useful
- safe handling of failed requests

Do not introduce unnecessary dependencies.

### Verify

Make at least one real request from the frontend to the backend.

### Acceptance criteria

- Frontend can reach backend
- Real backend response received
- API errors are handled
- No backend files changed
- Existing architecture preserved

---

# M02 — Student Shell, Auth & Navigation Verification

### Objective

Stabilize the Student shell before building individual pages.

### Verify

Flow:

Role Selection
→ Student Login
→ Student Shell
→ Dashboard
→ Sidebar
→ Topbar
→ Logout

### Verify

- role state
- user information
- initials
- sidebar active state
- page title
- breadcrumbs
- dashboard reachability
- mobile sidebar behavior

Do not redesign already-good login functionality unless necessary.

### Acceptance criteria

All Student navigation items are reachable:

- Dashboard
- Academic Assistant
- My Applications
- Create Application
- Settings
- Sign Out

---

# M03 — Student Dashboard

### Objective

Deliver a professional institutional Student Dashboard.

### UI sections

- Student Workspace
- Personalized welcome
- Student identity information when actually available
- Application overview
- Recent Applications
- Quick Actions
- Academic Assistant panel

### Critical restriction

There is currently no general `GET /applications`.

Therefore:

- no fake counts
- no fake recent applications
- no fake application status statistics

Use truthful empty/dependency states.

### Acceptance criteria

- Dashboard visually polished
- Uses real user data where available
- Quick actions actually navigate
- No fabricated backend data
- Responsive
- Loading/error/empty states work

---

# M04 — My Applications

### Objective

Create a professional applications page without inventing backend records.

### First inspect

Confirm whether a real list endpoint exists.

If no list endpoint exists:

Show a professional empty/dependency state such as:

> No application records are currently available.
>
> Applications you create will appear here when application records are available.

Provide:

`Create Application`

### Acceptance criteria

- No fake applications
- No fake counts
- Correct navigation
- Empty state looks intentional
- If a genuine list API exists, integrate actual data only

---

# M05 — Create Application

### Objective

Connect the frontend to the REAL:

`POST /applications`

### Before coding

Inspect the actual backend request schema.

Do not guess field names.

### UI

- application type/category where supported
- required fields from real schema
- title/description only if backend supports them
- validation
- submit
- loading
- success
- failure
- duplicate-submit prevention

### Important

The student does NOT manually create the application number.

The backend generates it.

### Acceptance criteria

- Real POST request
- Request body matches backend schema
- Backend response rendered correctly
- Created application can be opened where an ID is returned
- Network tab confirms the request
- No backend modification

---

# M06 — Application Details

### Objective

Connect:

`GET /applications/{application_id}`

### UI sections

- application information
- status
- documents
- requirements
- eligibility
- deficiencies
- AI analysis
- status history
- committee information when available
- official decision information when available

### Acceptance criteria

- real application ID used
- real backend response shown
- missing application handled
- loading/error states
- no fake values
- human decision separated from AI assistance

---

# M07 — Document Management

### APIs

- `POST /applications/{application_id}/documents`
- `GET /applications/{application_id}/documents`
- `GET /applications/{application_id}/documents/{document_id}/validate`
- `POST /applications/{application_id}/documents/{document_id}/extract`
- `POST /applications/{application_id}/documents/{document_id}/classify`

### UI

Show:

- file name
- type
- size
- upload state
- validation state
- extraction state
- classification state

### States

- Uploaded
- Processing
- Validated
- Needs Attention
- Failed

Only display confirmed backend states.

### Acceptance criteria

- upload works where supported
- documents reload correctly
- operations reflect real backend responses
- errors handled
- no fake status

---

# M08 — Ordinance Retrieval, Eligibility & Deficiencies

### APIs

- `GET /applications/{application_id}/ordinance-retrieval`
- `GET /applications/{application_id}/eligibility`
- `GET /applications/{application_id}/deficiencies`

### UI

Create clean sections for:

- Ordinance retrieval remains available through the API, but its context panel is intentionally omitted from Student, Official, and DUGC application-detail views.
- Requirements
- Eligibility Analysis
- AI-Identified Deficiencies

### Governance

Never convert AI analysis into a final official decision.

### Acceptance criteria

- real backend data shown
- citations/context handled where backend supplies them
- loading/errors work
- AI analysis visually separated from official decisions

---

# M09 — AI-Assisted Application Analysis

### API

`POST /applications/{application_id}/ai-analysis`

### UI

Show:

- AI-Assisted Analysis
- AI Recommendation
- AI Confidence
- AI-Identified Deficiencies
- relevant evidence/context if supplied

Include a subtle human-review note where appropriate:

> AI-generated assistance; final academic decisions remain with authorized officials/committees.

### Acceptance criteria

- real AI API call
- actual response rendered
- no AI final-decision language
- failure state handled

---

# M10 — Academic Assistant

### API

`POST /ask`

### First inspect

Determine actual request and response schema.

### UI

- welcome state
- conversation area
- input
- send
- loading
- error
- response rendering
- clear academic/institutional context

### Acceptance criteria

- real `/ask` request
- actual response
- loading state
- errors handled
- no fake conversation
- assistant does not imply autonomous authority

### Verified implementation status

- Frontend page and interaction flow have been implemented in `frontend/app.js` using the existing backend `/ask` contract.
- Request format: `{ question, conversation_history }` as defined by `backend/api/routes.py` and `frontend/services/api.js`.
- Response format: `{ answer, sources }` with safe rendering for question/answer text and source metadata.
- Empty input, in-flight loading, request error states, clear-conversation behavior, and safe text rendering are handled in the UI.
- A JavaScript runtime bug (`escapeHTML is not defined`) was corrected during verification.
- Browser automation validation was performed against the local frontend using a controlled `/ask` response, confirming navigation, login flow, empty-input validation, error rendering, successful answer rendering, and source display.
- Automated frontend checks passed, and the backend is reachable on the expected local URL.
- The initial live `/ask` smoke test returned HTTP 500 with `{"detail":"connection already closed"}` because semantic retrieval reused a module-level PostgreSQL connection. The retrieval code was then fixed to acquire and close a connection per request; `backend/tests/test_semantic_search.py` passed with 2 tests.
- A subsequent live `/ask` smoke test was reported as HTTP 200 with a real answer and retrieved sources. This is recorded prior-session evidence and was not rerun during this documentation reconciliation.
- Frontend syntax (`node --check frontend/app.js`) and API contract tests (`node frontend/services/api.test.mjs`) passed.
- Final status: `PASS`. The earlier live failure is resolved by the connection-lifecycle fix; the successful live result is recorded evidence, not a test rerun in this update.

---

# M11 — Status & Application Lifecycle

### Current implementation status — PARTIAL / LIVE VERIFICATION BLOCKED

- The student application-details view now displays the current backend-sourced status and chronological status history.
- Student-facing status changes and processing controls are intentionally absent; status mutation and processing are not student actions.
- API helper contracts are covered by the frontend mock-server test. Live database verification timed out.

### APIs where supported

- `PATCH /applications/{application_id}/status`
- `GET /applications/{application_id}/status-history`
- `POST /applications/{application_id}/process`

### Workflow

Respect the backend lifecycle.

Known states include:

- DRAFT
- SUBMITTED
- DOCUMENT_VALIDATION
- PROCESSING
- UNDER_REVIEW
- COMMITTEE_REVIEW
- APPROVED
- REJECTED
- CLOSED
- ON_HOLD
- DEFICIENCY_FOUND
- CORRECTION_REQUIRED
- RESUBMITTED

### Critical

Frontend must never bypass backend status rules.

### Acceptance criteria

- current status displayed correctly
- history displayed correctly
- controls only appear when backend/state permits
- no client-side fake transitions

---

# M12 — Committee / Human Decision Display

### Current implementation status — PARTIAL / LIVE VERIFICATION BLOCKED

- The student application-details view displays read-only committee review state, human decision, decision reason, and dates.
- Reviewer identifiers are omitted. AI analysis remains separately labeled advisory output.
- No committee assignment or decision-write controls are exposed in the student workspace.
- API helper contracts are covered by the frontend mock-server test. Live database verification timed out.

### APIs where relevant

- `POST /applications/{application_id}/committee`
- `GET /applications/{application_id}/committee-reviews`
- `PATCH /committee-reviews/{review_id}/decision`

### Student-side goal

Only show legitimate committee/human decision information available to the student.

Never make AI output look official.

### Acceptance criteria

- human/committee decisions clearly labeled
- AI recommendation clearly separate
- no authority confusion

---

# M13 — Audit / History Presentation

### Current implementation status — PARTIAL / LIVE VERIFICATION BLOCKED

- A chronological activity summary renders only recognized student-facing action labels and timestamps; it omits actor IDs and raw `details`.
- The backend route still returns the unfiltered audit response and has no authentication/authorization. UI filtering is not a security boundary; backend authorization remains a prerequisite for production student access.
- API helper contract is covered by the frontend mock-server test. Live database verification timed out.

### API

`GET /applications/{application_id}/audit-logs`

### Goal

Where student visibility is appropriate, display relevant history professionally.

Do not expose internal/security-sensitive details that the backend does not intend for the student.

### Acceptance criteria

- actual backend data
- chronological presentation
- readable labels
- no fabricated history

---

# M14 — Settings

### Current implementation status — IMPLEMENTED / BROWSER CHECKED

- Settings shows the available page-session profile and the existing sign-out action.
- The page explicitly states that backend account, password, and security management are not available.
- Browser navigation to Settings and sign-out were exercised. Mobile navigation was also checked after fixing the menu to close when a page is selected.

### Goal

Complete Student Settings without pretending unsupported functionality exists.

Possible sections:

- profile
- role
- session information
- safe local UI preferences
- sign out

Do not invent password/security management.

### Acceptance criteria

- useful
- professional
- truthful
- no fake backend functionality

---

# M15 — Full UX / Responsive / Accessibility Polish

### Current implementation status — PARTIAL

- Added responsive styles for workflow and settings panels, a reduced-motion preference, explicit mobile-menu ARIA state, and mobile-menu close behavior after navigation.
- Escaped the topbar profile name/role before inserting them into markup and replaced the unsupported “System Online” sidebar claim with “Local preview”.
- A mobile viewport check measured equal document and viewport widths and verified that selecting Settings closes the menu. The full page-by-page desktop/tablet/mobile and assistive-technology matrix remains outstanding.

### Review

Every Student page.

Check:

- desktop
- laptop
- tablet
- mobile
- spacing
- typography
- button alignment
- cards
- forms
- status badges
- empty states
- loading states
- error states
- keyboard focus
- labels
- accessibility
- horizontal overflow

### Acceptance criteria

All pages look like one coherent institutional product.

---

# M16 — End-to-End API Verification

### Current implementation status — BLOCKED

- Uvicorn starts and `/docs` plus `/openapi.json` return HTTP 200.
- Live read-only application/status-history/committee/audit requests and a read-only database query timed out because PostgreSQL was unreachable.
- Mock-server API helper tests pass. A complete browser-to-live-database flow, persistence verification, live Gemini path, and write-path verification are not claimed.
- Confirm database state before running further writes; see `docs/M11_M17_MANUAL_TESTING_GUIDE.md`.

### Goal

Prove that frontend and backend actually work together.

### Test

1. Student login
2. Dashboard
3. Create Application
4. POST `/applications`
5. Open returned application
6. GET application
7. Upload document where supported
8. Get documents
9. Validate/extract/classify where supported
10. Ordinance retrieval
11. Eligibility
12. Deficiencies
13. AI analysis
14. Academic Assistant
15. Status/history where applicable
16. Settings
17. Logout

### Browser verification

Use Browser DevTools → Network.

For each request verify:

- method
- URL
- request body
- status code
- response
- frontend rendering

### Acceptance criteria

Real requests are visible and work.

---

# M17 — Final QA & Zero-Backend-Change Audit

### Current implementation status — PARTIAL

- No backend file was edited in this implementation.
- The worktree already contained modified backend files and an untracked `backend/tests/` directory before this implementation; the repository therefore does not meet the literal “zero modified backend files” worktree check.
- Frontend syntax, API contract tests, backend retrieval tests, and guardrail tests passed. The full test suite and database audit remain blocked by PostgreSQL connectivity.
- A create request during browser-mock setup remained pending without a confirmed response. A subsequent read-only query for the test identifier timed out, so potential persistence is unresolved; do not perform blind cleanup.

### Run

```powershell
git status
git diff --name-only
```

### Verify

There are ZERO modified files under:

`backend/`

### Search frontend for

- fake data
- fake application numbers
- fake statistics
- AI Decision wording
- debugging leftovers
- console logs
- broken imports
- dead navigation
- placeholder UI

### Acceptance criteria

- Student frontend complete
- frontend/backend integration verified
- no fake data
- professional visual quality
- no obvious runtime errors
- backend untouched

---

# 4. DEFINITION OF A COMPLETED MODULE

A module is NOT complete just because the AI says:

> "Implemented successfully."

A module can be marked `VERIFIED` only when:

[ ] Code implemented
[ ] Imports verified
[ ] Navigation verified where applicable
[ ] Relevant API contract checked
[ ] Real API request tested where applicable
[ ] UI response verified
[ ] Loading state checked
[ ] Error state checked
[ ] Empty state checked where applicable
[ ] No fake data
[ ] AI governance checked
[ ] Responsive behavior checked where relevant
[ ] `backend/` untouched
[ ] `PROJECT_STATE.md` updated
[ ] Module marked `VERIFIED`

---

# 5. REQUIRED END-OF-MODULE HANDOFF

At the END of every module, the AI agent MUST:

1. Update `PROJECT_STATE.md`.
2. State the exact module completed.
3. State the exact next module.
4. List changed files.
5. List APIs verified.
6. List known issues.
7. Explicitly state:

`BACKEND CHANGES: NONE`

8. STOP.

Do NOT automatically continue to the next module.

---

# 6. EMERGENCY RECOVERY WHEN A CLAUDE/ANTIGRAVITY SESSION ENDS

If the AI session ends unexpectedly or message limits are reached:

Open a NEW AI session/account and send:

```text
Read these files first:

1. PROJECT_STATE.md
2. docs/API_CONTRACT.md
3. docs/FRONTEND_IMPLEMENTATION_PLAN.md

This is an existing DepartmentAI project.

Do not ask me to explain the project again.

The previous AI session has already completed everything recorded as VERIFIED.

Your job is:

1. Inspect PROJECT_STATE.md.
2. Inspect the actual current code.
3. Run git status.
4. Verify the last completed module if necessary.
5. Identify NEXT MODULE from PROJECT_STATE.md.
6. Implement ONLY that next module.
7. Do NOT redo completed modules.
8. Do NOT modify backend/.
9. Test the relevant frontend/API flow.
10. Update PROJECT_STATE.md.
11. Mark the module VERIFIED if all acceptance criteria pass.
12. State the next module.
13. STOP.

ZERO BACKEND EDITING.
```

---

# 7. IF THE PREVIOUS AI DIED MID-MODULE

Use this recovery prompt instead:

```text
Read:

- PROJECT_STATE.md
- docs/API_CONTRACT.md
- docs/FRONTEND_IMPLEMENTATION_PLAN.md

The previous AI session ended unexpectedly during the current module.

Do NOT assume the current module is complete.

1. Inspect PROJECT_STATE.md.
2. Inspect the git diff.
3. Inspect all files changed for the current module.
4. Determine exactly what is complete and what is unfinished.
5. Do NOT redo completed work.
6. Finish ONLY the current module.
7. Test it.
8. Update PROJECT_STATE.md.
9. Mark VERIFIED only after acceptance criteria pass.
10. Do not modify backend/.
11. STOP after the current module.

Never move to the next module until the current one is verified.
```

---

# 8. GIT CHECKPOINT STRATEGY

After every `VERIFIED` module, create a commit.

Suggested style:

```text
feat(student): complete M03 dashboard
feat(student): complete M05 create application
feat(student): complete M07 document management
feat(student): complete M10 academic assistant
```

This gives you another recovery mechanism.

You can always inspect:

```powershell
git log --oneline
```

and see:

```text
M10 Academic Assistant
M09 AI Analysis
M08 Ordinance Eligibility
M07 Documents
M06 Application Details
...
```

---

# 9. IMPORTANT AGENT BEHAVIOR

NEVER tell the AI:

> "Implement the entire frontend."

Instead say:

> "Read PROJECT_STATE.md and implement ONLY M05."

This is the key to surviving message limits.

The AI should never have to remember 17 modules in its context because the files preserve the state.

---

# 10. NEXT-MODULE PROMPT TEMPLATE

For ordinary continuation, use:

```text
Read:
- PROJECT_STATE.md
- docs/API_CONTRACT.md
- docs/FRONTEND_IMPLEMENTATION_PLAN.md

Continue the project from the exact recorded state.

Implement ONLY the module identified as NEXT MODULE.

Rules:
- inspect current implementation first
- do not redo VERIFIED modules
- do not modify backend/
- use actual backend API contracts
- do not fabricate data
- verify real API calls where applicable
- update PROJECT_STATE.md
- mark the module VERIFIED only after testing
- commit the completed module if practical
- state the next module
- STOP
```

---

# 11. FINAL PROJECT COMPLETION

The Student frontend is complete only when:

`M00 → M17`

have all reached:

`VERIFIED`

Then perform one final:

```powershell
git status
git diff --name-only
git log --oneline
```

And confirm:

`backend/ = untouched`

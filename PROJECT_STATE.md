# DepartmentAI — Current Project State

CURRENT FOCUS: Role-scoped Official meeting scheduling; Module II FAQ source and isolated acceptance still blocked
STATUS: Earlier browser checks exercised the synthetic application workflow against `departmentai_test`. The updated meeting UI is now live on loopback; the DUGC application view and empty linked-meeting response were browser-checked, but creating and confirming a new proposal was not exercised. Module II remains unassigned, its dedicated test database is absent, and no FAQ chatbot has been exposed. This is not institutional acceptance.
LAST IMPLEMENTED MODULE: M18 — Programme-Scoped Ordinance Knowledge (partial; Assistant selector remains informational)
NEXT: Obtain an approved, non-sensitive FAQ corpus before implementing the all-role FAQ assistant. Provision Module II only after an authorized local database-admin mechanism is available; complete real API/browser reporting acceptance without substituting Module I. Obtain trusted identity, approved institutional policies, governance/signatory authority, and external integrations separately before claiming institutional readiness.

## Module II local demo provisioning attempt — 2026-10-30

- The resolver requires `DEPARTMENTAI_MODULE2_DATABASE_ENV=test` and an
  ignored `.env.module2.test` containing `DB_HOST`, `DB_PORT`,
  `DB_NAME=departmentai_module2_test`, `DB_USER`, and `DB_PASSWORD` (or
  `DEPARTMENTAI_DB_PASSWORD`). The profile must target loopback. The existing
  `.env.module2.test.example` documents this shape; the actual profile and
  dedicated database are absent.
- After explicitly selecting the local application `test` profile, a
  read-only connection confirmed `departmentai_test` at `127.0.0.1`. Its
  database role has `CREATEDB=false` and is not a superuser;
  `departmentai_module2_test` does not exist. Provisioning stopped here:
  no alternate account was tried, no Module I tables or records were changed,
  and no Module II profile, schema, fixtures, or permission grants were
  created.
- An initial inspection command accidentally inherited the main resolver's
  default `institutional` profile and attempted a connection; it timed out
  before connecting or authenticating. No institutional data was read or
  changed. All subsequent database inspection explicitly selected the
  loopback `test` profile.
- The main app already mounts the Module II API, but the live browser's
  synthetic Student account still receives “Module II is not assigned” and
  has no Module II navigation. Student, Official, and DUGC Module II access
  and real data rendering therefore remain unverified and unavailable.
- Focused isolated Module II tests passed: backend **88 passed** (10
  deprecation warnings) and frontend **2 passed**. The browser frontend
  returned HTTP 200; API liveness/readiness returned HTTP 200 with
  `ok`/`ready`. Existing dirty worktree changes were preserved; no commit or
  push was made.

## Current working-tree continuation — meeting roles and FAQ boundary

- Meeting creation and slot selection are now Official-only. The backend checks
  that each linked application is assigned to the Official and has the
  corresponding committee assignment; the Official can only list and edit
  their own current assigned proposals.
- DUGC no longer has a standalone Meeting Governance navigation entry.
  Assigned committee members see linked proposals, submit their own
  availability, and receive policy-gated approval or Confirm/Decline controls
  in the application review. The API checks the application-meeting link,
  committee membership, and configured approver before each action.
- Focused validation: governance service/API tests **15 passed**; frontend role
  workspace and governance workspace Node tests passed; edited Python modules
  compiled; edited JavaScript passed `node --check`; `git diff --check` passed.
- In the actual browser, the DUGC navigation no longer shows Meeting
  Governance, and an assigned application renders the new meeting
  confirmation/availability section. After authorized API restart, its
  OpenAPI document included the new application-meeting route, and the real
  browser received the correct empty state for application 166. A read-only
  application-profile connection check returned `departmentai_test` at
  `127.0.0.1`; no meeting was created and no database records were written.
  The new Official proposal/slot and DUGC approval/confirmation sequence is
  still not live-browser-verified.
- Inspection of `module2/` found no FAQ corpus or approved FAQ file. The
  existing temporary assistant explicitly answers questions about CSED faculty
  profiles, research, publications, and thesis supervision; its API calls
  Module II retrieval/database services and requires
  `module2.faculty.chat`. That private-data assistant was not exposed to all
  roles and no broad grant was added. No Module II database was provisioned.
  An approved public/administrative FAQ corpus is still needed before an
  all-role assistant can provide sourced answers.
- The API is running on `127.0.0.1:8002` using the explicit test profile and
  exact frontend CORS origin. No database was changed by this continuation.
  Pre-existing worktree edits were preserved; no commit or push was made.

## Local Yogesh adapter and website check — 2026-10-30

- The main checkout contains a test-only M.Tech/PhD advisory adapter and a
  meeting-options adapter. Both require the explicit `departmentai_test`
  profile, the synthetic local demo, an opt-in environment flag, a
  runtime-only shared token, and loopback-only reference-service URLs.
- A runtime connection through the application's profile resolver returned
  database `departmentai_test` and server address `127.0.0.1/32`. The API
  readiness endpoint on `127.0.0.1:8002` and frontend at `127.0.0.1:5500`
  returned HTTP 200. The browser displayed the role-selection/login screen;
  no authenticated browser session or live RAG/scheduler request was run.
- The initial browser page was blank because of an unmatched closing brace in
  `frontend/app.js`. Removing the extra brace restored the login screen and
  eliminated the browser parse error.
- The local reference-service checks on ports 8003 and 8004 were unavailable.
  Therefore the adapter's real upstream response validation, persisted live
  advisory, and scheduler candidate intersection remain unverified.
- Focused backend regressions passed (**58 passed**); the focused RAG/adapter
  subset passed again (**25 passed**). Frontend Node tests passed (**10
  passed**), and `git diff --check` passed. The wider 58-test run reported one
  existing Starlette/AnyIO deprecation warning.
- This continuation did not provision or modify a database. No credentials
  were displayed, and no commit or push was made. Module II remains
  unprovisioned, and institutional readiness is not established.

## Live browser application-to-approval workflow — 2026-10-30

- The existing frontend at `http://127.0.0.1:5500/` and API at
  `http://127.0.0.1:8002/` were exercised in the shared browser against the
  application's loopback test database, `departmentai_test`. No database,
  schema, institutional policy, or identity configuration was provisioned.
- Using only the pre-existing synthetic accounts and the ignored
  `TEST_ONLY` M.Tech demo policy, Student `demo.student` created application
  `APP-2026-00163` (ID 166). The Student uploaded the two existing synthetic
  PDF fixtures through the real UI. The persisted readiness check matched
  both configured demo requirements and reported `READY`, with zero
  deficiencies.
- The Student submitted the draft. Official `demo.official` claimed it and
  advanced it through `DOCUMENT_VALIDATION`, `PROCESSING`, `UNDER_REVIEW`,
  and `COMMITTEE_REVIEW`, then assigned it to DUGC. DUGC `demo.dugc` saw the
  item in the membership-scoped queue and recorded the human
  `APPROVED` decision with an explicit test-only rationale.
- The Student then reopened the persisted record in the browser and saw
  `APPROVED`, both uploaded documents, the status history, and the DUGC
  decision/rationale. The approval is only a synthetic test record, not an
  institutional academic decision. The standalone Yogesh RAG/scheduler
  services were not used; Module II remains unprovisioned.
- The Student, Official, and DUGC sessions were established using local
  synthetic credentials without displaying credential or token values.
  No commit or push was made, and unrelated worktree changes were preserved.

## Optional persistent synthetic local demo — 2026-10-28 (updated)

The existing loopback `departmentai_test` database was reused; no database was
created, migrated, or initialized. The explicit test profile resolved to
`departmentai_test`, and its runtime PostgreSQL server address was verified as
loopback. The dedicated `departmentai_module2_test` database and private
`.env.module2.test` profile remain absent. No Module II database was created
or substituted.

The opt-in seeder at `backend/database/seed_local_demo.py` provisions or
verifies only the reserved synthetic accounts `demo.student`,
`demo.official`, `demo.dugc`, and `demo.dugc.member`, plus their two DUGC
memberships. It refuses non-test/non-loopback targets, preserves existing
account attributes, and is idempotent. It also writes an ignored synthetic
M.Tech rules source and manifest and indexes exactly two embedding chunks in
`departmentai_test`. The source is accepted only under its fixed source ID,
hash, `TEST_ONLY` scope, explicit demo flag, and loopback test profile.
Checked-in institutional policy/source files remain unchanged. The generated
policy, workflow, source manifest, fixtures, and credentials live under the
ignored `.local-demo/` directory. On Windows, keep the checkout private
because generated credentials inherit its folder permissions.

The frontend is available at `http://127.0.0.1:5500/`; the API is available at
`http://127.0.0.1:8002/` with the explicit test profile and generated demo
policy/identity. Both services returned HTTP 200 and the API readiness check
reported ready. The browser signed in as synthetic Student, Official, and DUGC
accounts and made authenticated requests to the real API. No credential value
is included in this report. The generated Student password was rotated after
the browser acceptance run.

| Live browser/API scenario | Verified result |
|---|---|
| Source registration and retrieval | Registry resolved `LOCAL_DEMO_MTECH_RULES`; source inventory reported **2/2** expected chunks indexed and verified. Scoped retrieval returned two results with verified source metadata and section `DEMO-1`. |
| Student identity and readiness | `demo.student` was server-verified as the synthetic M.Tech identity. Application 154 began with two missing-document deficiencies. The two generated PDFs were uploaded, classified by the real document classifier (`APPLICATION_FORM` and `MARKSHEET`), and extracted. The authenticated UI then showed current `READY`, zero deficiencies, verified `TEST_ONLY` policy, and both matched requirements. |
| Submission and Official review | The Student submitted application 154 only after current readiness. `demo.official` claimed it and used allowed transitions through `DOCUMENT_VALIDATION`, `PROCESSING`, `UNDER_REVIEW`, and `COMMITTEE_REVIEW`, then assigned DUGC. |
| Meeting, minutes, and committee outcome | Synthetic DUGC members recorded overlapping availability; candidate-slot generation returned valid slots. Meeting 41 was approved by the configured TEST_ONLY approver and reached `CONFIRMED` after **2/2** confirmations. Human minutes version 2 were submitted, reviewed, and finalized. The authorized synthetic DUGC account recorded an explicitly TEST_ONLY approval; application 154 now has `APPROVED` status solely as a demonstration record, not an institutional academic decision. No external AI generation, email, calendar, or notifications were used. |
| Module II isolation | The Student's `/module2/capabilities` request returned HTTP 403 because no Module II grant exists. `departmentai_module2_test` and `.env.module2.test` remain absent; no Module II database was substituted or modified, and live Module II reporting acceptance remains blocked. |
| Regression tests | Targeted backend tests: **65 passed**, 0 failed, 0 skipped, with one existing Starlette/AnyIO deprecation warning. The cold first readiness request timed out; a subsequent authenticated UI analysis completed successfully after retry. |

This local setup is a synthetic development aid, not production readiness.
Trusted institutional identity, approved policy mappings, authorized
governance/signatory policy, real committee membership, and external
integrations remain separate prerequisites. No commit or push was made, and
pre-existing worktree changes were preserved. The worktree remains dirty;
generated credential, policy, source, and fixture files are ignored.

## Prompt 4 authenticated browser acceptance — 2026-10-28

The real frontend and API were exercised together on loopback ports 5500 and
8002 against only `departmentai_test`. Temporary synthetic accounts and
application/policy records were removed after the run. The positive readiness
path used the existing synthetic integration fixture through a runtime-only
`TEST_ONLY` policy and identity override; neither the default configuration nor
institutional policy was changed.

| Browser/API scenario | Verified result |
|---|---|
| Default Student submission gate | With identity and application policy unresolved, readiness remained blocked; the authenticated submit request returned HTTP 409 and the persisted application stayed `DRAFT`. |
| Test-only positive Student flow | The isolated UG fixture returned `READY`; the frontend enabled Submit only after the backend response, and persisted submission returned HTTP 200. |
| Official processing | The submitted record appeared in the authenticated Official queue, was claimed, moved through the offered workflow statuses, and was assigned to DUGC. Saved analysis remained advisory; Official reads did not trigger a new analysis. |
| DUGC decision | The assigned review was visible only in the matching DUGC workspace. An invalid decision returned HTTP 400 without changing the pending review; the valid human decision returned HTTP 200, persisted the completed review and application status, and refreshed the browser record/history. |
| Role and state boundaries | A second Student received HTTP 404 for the first Student's application and documents. The owner’s post-submission upload returned HTTP 409 and left the document list unchanged. Assignment to an unconfigured committee was rejected without replacing the existing pending review. |
| Governance limits | Proposal, availability, and candidate-slot state persisted. Notice remained a draft/not-sent preview; meeting approval was blocked by the unconfigured policy, and minutes creation was rejected before meeting confirmation. Controls hidden by workflow policy were verified not to render visibly. |
| Frontend defect found | Added a scoped `[hidden]` display rule to `frontend/styles/governance.css`; live browser inspection confirmed unavailable governance actions no longer appear. |
| Focused regressions | Backend: **33 passed**, with one existing Starlette/AnyIO deprecation warning. Frontend: **7 Node test files passed**. All frontend `.js`/`.mjs` syntax checks, `python -m compileall -q backend module2`, and `git diff --check` passed. |
| Cleanup | Both local servers were stopped; ports 5500 and 8002 were verified not listening. Temporary test accounts, applications, meeting, availability, fixture knowledge rows, uploaded synthetic file, and runtime policy/evidence files were removed. The pre-existing DDPC membership and unrelated files in the application documents directory were preserved. |

This acceptance does not verify institutional identity, production policy,
committee provisioning, notification/calendar providers, AI availability, or
signatory configuration. No commit or push was made.

## Prompt 3 integration-test repair and acceptance — 2026-10-28

The test-profile DDPC governance lifecycle and local Student/Official workflow
now isolate their committee membership assumptions from persistent
`departmentai_test` data. The local workflow snapshots and temporarily removes
committee memberships, inserts its own test members, and restores the snapshot
during fixture teardown; production committee assignment behavior was not
changed.

| Verification | Result |
|---|---|
| Focused backend regressions | **33 passed** across governance lifecycle/workflow, application policy registry, local database integration, and guardrails. One existing Starlette/AnyIO deprecation warning remains. |
| Repeatability | The local Student/Official workflow passed **3 consecutive runs**; after each run, the pre-existing single DDPC membership was restored. The DDPC governance lifecycle had also passed **3 consecutive runs**. |
| Frontend | **7 Node test files passed**; `node --check` passed for **18** frontend JavaScript files. |
| Python and patch checks | `python -m compileall -q backend module2` and `git diff --check` passed. |
| Live test-profile/browser smoke check | API `/health/ready`, `/openapi.json`, and `/docs` returned HTTP 200; the frontend returned HTTP 200 and rendered the account-type and Student sign-in views. Swagger UI opened in the browser. No authenticated browser workflow was attempted; database-backed behavior is covered by the isolated integration tests. |
| Safety and cleanup | API ran with `DEPARTMENTAI_DATABASE_ENV=test` against loopback `departmentai_test`; both temporary servers were stopped. No commit, push, or reference-worktree changes were made. |

## Prompt 2 frontend integration follow-up — 2026-10-28

The existing authenticated Module I endpoints remain the source of application,
review, committee, governance, and minutes state. The frontend follow-up made
Student submission gating stricter when identity or policy evidence is absent,
refreshes the application after server-side `409` conflicts, orders the
Student detail workflow as application/documents/readiness/history/submit, and
gates governance mutations using persisted meeting state, workflow policy,
provider status, minutes inputs, and the authenticated username. Meeting
creation now selects the persisted meeting returned by the API and retains its
idempotency key across a failed retry.

| Workflow | Current UI and API state |
|---|---|
| Student draft and documents | Existing create/edit, upload/list, saved analysis/readiness, and submit APIs remain connected. Editing/uploading are draft-only; server `409` triggers a detail refresh. Missing identity/policy, source, match, freshness, or blocker fields cannot enable Submit. |
| Official and committee review | Existing backend queue, claim, saved record/analysis, status, committee review, decision, and history calls remain connected. Queues and decisions use persisted responses; allowed status transitions come from the backend. No explicit approve-directly-versus-meeting endpoint or formal deficiency response workflow is available. |
| Meeting governance | Existing authenticated `/governance` endpoints remain connected for configuration, proposals, availability, candidate slots, slot selection, approval, member responses, agenda, notice preview, records, and minutes. Approval and confirmation controls are state/policy scoped; a proposal or selected slot is not presented as confirmed. Notices remain previews, not sent messages. |
| Minutes | Existing version/read/create/generate/revise/comment/submit/approve APIs remain connected. Drafting controls require confirmed meetings and complete recorded inputs; AI generation requires the backend-reported approved provider state; final approval is shown only for a configured signatory. |
| Operational blockers | The default application-policy registry has no active application-type mappings and the default student-programme identity provider is unconfigured. The governance workflow registry is empty; notification/calendar/timetable providers are unconfigured and finalized-minutes indexing is not implemented. These are not bypassed by the UI. |
| Validation | Frontend Node tests: **7 passed**. Focused test-profile backend policy/governance/guardrail tests: **30 passed**; one governance integration case is excluded after repeat failure. That fixture submits availability for its two temporary DDPC members, but the test profile also has one existing active DDPC member, and candidate calculation requires availability from every active member. The run including that case was **30 passed, 1 failed**. JavaScript syntax checked for **25** frontend files; `python -m compileall -q backend module2` passed. |
| Browser acceptance | Not run. The frontend at `http://127.0.0.1:5506/`, API at `http://127.0.0.1:8002/health/ready`, and Swagger at `http://127.0.0.1:8002/docs` were unavailable during this follow-up. No end-to-end success is claimed. |

Frontend files changed for this follow-up: `frontend/app.js`,
`frontend/pages/governance-workspace.js`,
`frontend/pages/governance-workspace.test.mjs`,
`frontend/utils/application-readiness.js`,
`frontend/utils/application-readiness.test.mjs`, and
`frontend/styles/application-details.css`. No backend endpoints, workflow
policies, identities, or application mappings were changed.

## Prompt 4 governance-workflow integration

| Capability | Status | Current implementation / boundary |
|---|---|---|
| M.Tech/Ph.D. ordinance retrieval | `INTEGRATED; APPLICATION POLICY STILL FAIL-CLOSED` | Existing programme-aware authenticated knowledge retrieval remains the target. Retrieval citations used during minutes drafting are candidates, not committee decisions or authoritative precedents. |
| Meeting proposal, availability, and candidate slots | `DATABASE INTEGRATION AND BROWSER CHECK PASSED` | Authenticated `/governance` routes persist meetings and member-submitted availability. Isolated API tests cover persistence, and the real browser created a proposal, submitted availability, searched slots, and proposed a candidate against `departmentai_test`. |
| Approval, confirmations, records, and audit | `POLICY-GATED` | Meeting approval and confirmation thresholds require an approved scoped workflow registry entry. The default registry is empty; notices are previews and are not sent. |
| Versioned minutes review | `IMPLEMENTED; FINALIZATION POLICY-GATED` | Meeting notes, observations, human decisions, attendance, drafts, revisions, reviewer comments, and sign-off state are persisted. Contradictory decision terms and unresolved agenda items are surfaced for human review. |
| AI minutes generation | `OPT-IN; PROVIDER NOT HEALTH-CHECKED` | Gemini generation requires explicit `DEPARTMENTAI_MINUTES_LLM_APPROVED=true` and a user action; provider credentials/availability are checked on request. AI does not create attendance or decisions. |
| Finalized-minutes indexing | `NOT IMPLEMENTED` | Even when a policy requests indexing, finalization reports `INDEXER_NOT_IMPLEMENTED`; the system does not claim successful indexing or retrieval. |
| Calendar, timetable, email, messaging | `NOT CONFIGURED` | The UI and API state these limits explicitly. No simulated reference implementation is presented as an institutional integration. |
| Frontend | `IMPLEMENTED; PARTIAL BROWSER/API CHECK` | DUGC workspace offers committee selection, proposal creation, availability, candidate slots, agenda/notice preview, records, minutes editing/review, comments, and policy-gated actions. The real browser verified proposal/availability/slot operations; the full minutes lifecycle is covered by isolated API/database integration tests. |

Reference-to-target feature mapping, exact route contracts, and verification
status are recorded in `docs/INTEGRATION_INVENTORY.md`,
`docs/API_CONTRACT.md`, `docs/ROLE_PERMISSION_MATRIX.md`,
`docs/MODULE1_PROGRAMME_COVERAGE_AUDIT.md`, and
`docs/END_TO_END_VERIFICATION_REPORT.md`. The M.Tech and Ph.D. reference
checkouts remain unchanged. No operational browser-to-backend governance
workflow or institutional provider integration is claimed until tested.

## Module status

| Module | Status | Evidence / outstanding work |
|---|---|---|
| M09 — AI-Assisted Application Analysis | Student and reviewer views use one policy-aware saved analysis contract. Legacy eligibility remains separately labeled advisory data with freshness untracked; Official-side reprocessing is disabled. |
| M10 — Academic Assistant | Assistant supports authenticated source-filtered UG, M.Tech/Masters, and Ph.D. ordinance retrieval. Provenance-bearing citations and `/knowledge/sources` / `/knowledge/search` are wired; focused and isolated API/database tests pass. Live browser/API answer generation was not exercised in this integration. |
| M11 — Status & Application Lifecycle | Draft editing, upload, lifecycle history, and human review remain implemented. Submission is now intentionally blocked unless a current verified `READY` analysis exists; current policy configuration cannot produce one. The earlier Prompt 4 successful submission occurred before this gate and is not evidence that the present configuration can submit. |
| M12 — Committee / Human Decision Display | `VERIFIED` for the local synthetic configuration: the real DUGC queue loaded, an assigned application and document/history were reviewed, an authorized decision persisted with status history and audit, and the Student saw the outcome without reviewer identity. Cross-committee access was denied. |
| M13 — Audit / History Presentation | Audit route returns 403 until a visibility policy is approved. Student activity UI states this clearly and does not request raw audit data. |
| M14 — Settings | Authenticated session settings and server-revoking logout are implemented. Prompt 4 confirmed browser storage clearing, HTTP 204 logout, and HTTP 401 when the revoked token was reused. |
| M15 — UX / Responsive / Accessibility | Browser checks at requested widths 376/768/1281 had no horizontal overflow; keyboard focus was visible with a solid 2px outline. Screen-reader behavior and full assistive-technology review remain unverified. |
| M16 — End-to-End API Verification | Prompt 4 historically verified the checked-in frontend at port 5506 against the actual API at port 8002 using the explicitly isolated loopback `departmentai_test`; that successful submission predates the new readiness gate. This is local synthetic integration only. Institutional PostgreSQL and institutional authentication remain unverified. |
| M17 — Final QA / Backend Audit | Earlier acceptance counts below are historical. Prompt 3 validation is recorded below. No institutional integration or production security certification is claimed. |
| M18 — Programme-Scoped Ordinance Knowledge | **Partial.** Authenticated candidate search and source inventory cover UG/M.Tech/Masters/Ph.D.; exact source ID/version/hash provenance is surfaced. A default policy registry catalogs approved ordinance files but activates no application types. Trusted identity, portal mappings, eligibility evaluators, and automatic routing remain unconfigured; PGD is unsupported. |

## Prompt 2 readiness workflow — fail-closed implementation

| Capability | Status | Evidence / boundary |
|---|---|---|
| Persisted readiness analysis | `IMPLEMENTED FAIL-CLOSED` | `GET /applications/{id}/readiness` is read-only. `POST /applications/{id}/readiness/analyze` validates/classifies draft documents, records rule-scope diagnostics and blockers in `ai_analyses`, and is idempotent for unchanged non-unavailable inputs. |
| Analysis freshness | `IMPLEMENTED` | Application type/title/description/status and document metadata/content SHA-256 are fingerprinted. The saved result is stale after an edit, upload, file change, or lifecycle status change. |
| Atomic submission enforcement | `IMPLEMENTED FAIL-CLOSED` | Submission rechecks current fingerprint and readiness fields inside the existing row-locked transaction; stale, pending, unavailable, unresolved, deficient, or incomplete results return structured HTTP 409. |
| Student analysis UI | `IMPLEMENTED` | Documents precede one consolidated AI-Assisted Analysis panel. Draft edits/uploads trigger reanalysis; Submit is placed after the analysis and remains disabled except for a current, provenance-verified `READY` result with zero deficiencies and no blockers. |
| Authoritative rules and successful READY path | `BLOCKED` | The profile has no verified programme and free-text application types have no approved mapping to ordinance sources or required-document checklists. Retrieval is not run against an assumed UG default; empty rules do not mean zero requirements. Current results remain `RULES_UNRESOLVED`; the service cannot produce `READY`. |
| OCR and unsupported documents | `NOT CONFIGURED` | Scanned/image documents are reported as unsupported/no-text; processing cannot be represented as complete and blocks submission. |

Earlier validation counts are historical; see the Prompt 3 verification
section below for the current run.

## Prompt 3 policy-aware analysis — 2026-10-28

| Capability | Status | Evidence / boundary |
|---|---|---|
| Approved policy registry | `IMPLEMENTED FAIL-CLOSED` | `backend/config/application_policies.json` records three Board-approved 2023 ordinance sources with source versions and SHA-256 checks; `application_types` is intentionally empty. No portal category is activated. |
| Trusted programme identity contract | `IMPLEMENTED; PROVIDER NOT CONFIGURED` | Student identity resolves to `NOT_CONFIGURED` by default. A provider must return a verified subject, programme, source ID, and source version; conflicting or incomplete provenance fails closed. No institutional identity source is claimed. |
| Policy/RAG resolution | `IMPLEMENTED FAIL-CLOSED` | Exact application-type and verified-programme mapping is required. Existing semantic retrieval is called only after resolution and its source-file metadata is checked against the policy registry. The checklist comes from an explicitly approved registry mapping; retrieval does not automatically extract or approve policy rules. |
| Combined analysis API and UI | `IMPLEMENTED` | Authorized read-only `GET /applications/{id}/analysis` returns readiness plus stored eligibility, with `formal_decision: false` and eligibility freshness `NOT_TRACKED`. Student and reviewer workspaces show one AI-Assisted Analysis view; policy evidence is collapsed by default. |
| Official reprocessing | `DISABLED FAIL-CLOSED` | `POST /applications/{id}/process` returns structured HTTP 409; no legacy default-programme analysis or mutation runs. Officials read saved analysis. |
| Submission gate | `IMPLEMENTED FAIL-CLOSED` | The existing row-locked gate still rechecks the current analysis, identity, registry, documents, and input fingerprint. With no active default policy mapping, real submissions cannot reach `READY`. |

Validation: `DEPARTMENTAI_DATABASE_ENV=test` and
`pytest backend\\tests tests\\test_guardrails.py -q` — **64 passed**, one
existing Starlette/AnyIO deprecation warning; all six frontend Node suites
passed; `node --check` passed for all **23** frontend `.js`/`.mjs` files;
`python -m compileall -q backend` and `git diff --check` passed. The two
isolated integration tests include a test-only provider/mapping, semantic
search with a real ordinance chunk, combined-analysis access/cross-owner
denial, and disabled Official processing. Test activation is restricted to the
test database profile and is not production policy. No real browser-to-backend
Prompt 3 or institutional workflow was performed.

## Prompt 1 workflow hardening — 2026-10-28

| Capability | Status | Evidence / boundary |
|---|---|---|
| Draft-only Student document upload | `VERIFIED` in isolated integration tests | The upload service locks the application row and permits uploads only in `DRAFT`; a post-submission upload returns HTTP 409 and does not add a document. |
| Integrated Official document processing | `DISABLED` pending policy-aware reprocessing | The legacy pipeline is no longer available from the Official workspace and the route returns structured HTTP 409. Officials can read saved Student analysis; no default-programme reprocessing occurs. |
| Saved reviewer eligibility results | `VERIFIED` in isolated integration tests | The authorized read-only endpoint returns `NOT_GENERATED`/`PARTIAL`/`AVAILABLE` and stored results without calling an AI provider or mutating records. Existing analysis GET behavior remains side-effecting. |
| Student and reviewer presentation | `IMPLEMENTED`; automated regression checks pass | Student document rows no longer expose per-document Download/Validate/Extract/Classify buttons; draft upload availability is tied to server-confirmed status. Student and reviewer panels now share the policy-aware analysis contract and show legacy eligibility as advisory with untracked freshness. |
| Policy and OCR completeness | `NOT CONFIGURED` | Required-document policy, programme eligibility, automated routing, formal deficiency response, and image OCR are not inferred or represented as complete. |

Prompt 1 validation from the project directory: `DEPARTMENTAI_DATABASE_ENV=test`
and `pytest backend\\tests -q` — **44 passed** (one existing Starlette/AnyIO
deprecation warning); `pytest tests\\test_guardrails.py -q` — **13 passed**;
all five focused frontend Node suites passed; `node --check` passed for all
**21** frontend JavaScript files. The frontend module also passed Node's
browser-module syntax check. No AI provider or institutional data was used.

## Prompt 2 identity and routing — 2026-10-27

| Capability | Status | Evidence / dependency |
|---|---|---|
| Trusted student programme identity source | `BLOCKED` | `auth_users` stores server-provisioned role and subject only. No student profile/programme relation, institutional IdP, or authorized profile-provisioning role/workflow exists. Existing users are not assigned a programme. |
| Safe authenticated programme claim | `PARTIAL` | Student `/auth/login` and `/auth/me` responses now state `programme_identity_status: NOT_CONFIGURED` and `verified_programme: null`. Existing inactive auth accounts remain rejected. This is a fail-closed declaration of missing configuration, not verified identity. |
| Browser programme spoof resistance | `VERIFIED` for local tests | Application create/edit/committee-assignment schemas reject undeclared identity and committee-ID fields; program/committee query parameters do not affect server-derived applicant ownership or assignment. |
| Institutional committee scope | `VERIFIED` as committee-body scope only | UG Ordinance §1.6 describes DUGC and its UG-student academic responsibilities; 2023 Masters Ordinance §1.3 describes DMPC in the Masters programme; 2023 Doctoral Ordinance §1.3 describes DDPC in the doctoral programme. These establish body scope, not portal-specific application-routing authority. |
| Automatic application routing UG→DUGC, Masters→DMPC, PhD→DDPC | `BLOCKED` | No approved application categories, trusted student programme, or rule authorizing these generic application transitions is documented. Manual Official assignment is retained; no mapping is activated. |
| Official committee assignment | `VERIFIED` for the local synthetic configuration | Existing Official-only assignment remains limited to assigned applications in `COMMITTEE_REVIEW`. Backend requires at least one configured membership for the target committee and records the authenticated Official as the audit actor in the same transaction. |
| Formal provisioning/change audit | `BLOCKED` | No administrative role or authorized institutional profile-provisioning workflow exists; no profile modification endpoint was added. |

Prompt 2 verification: isolated `pytest backend\tests -q` with
`DEPARTMENTAI_DATABASE_ENV=test` — 31 passed (one existing deprecation
warning); `pytest tests\test_guardrails.py -q` — 13 passed; frontend
`api.test.mjs`, `auth.test.mjs`, `login.test.mjs`, `role-workspaces.test.mjs`,
and `student-dashboard.test.mjs` passed. Browser exercised sign-in,
unverified-programme dashboard, application-creation notice, and sign-out
against an in-page synthetic fetch mock, not a live backend.

## Current application lifecycle verification — 2026-10-27

| Capability | Status | Evidence / dependency |
|---|---|---|
| Create, list, retrieve, and edit owned drafts | `VERIFIED` for synthetic local accounts | Backend database integration tests passed; Prompt 4 also created and edited a draft in the real browser against the isolated test API/database. |
| Supported text field validation and submit | `VERIFIED` for generic supported fields | Backend rejects blank/oversized fields and refuses submission when the type is invalid. No category eligibility is implied. |
| Upload/list/download and ownership checks | `VERIFIED` for synthetic local accounts | Prompt 4 browser/API verification covered upload, list, authorized retrieval, and cross-user denial; Prompt 1 additionally enforces DRAFT-only upload with a row lock and HTTP 409 after submission. Isolated integration tests cover the lifecycle guard, traversal-name sanitization, duplicate-name file isolation, and download integrity. |
| Student submission and Official assignment | `VERIFIED` for the local shared-queue workflow | Prompt 4 verified submission, Official claim, and manual assignment in the real browser/API workflow; integration tests cover duplicate denial and role/ownership boundaries. |
| Authorized committee review and decision | `VERIFIED` for the local synthetic configuration | Prompt 4 verified committee queue/review/decision and applicant-visible outcome/history; cross-committee denial, authenticated actor, status history, and audit persistence were confirmed through HTTP/database checks. |
| Required-document rules, categories, and eligibility | `NOT SPECIFIED` | No approved category list or required-document/eligibility rules are configured; the portal does not mark applications complete or verified against policy. |
| Formal deficiency request and applicant response | `MISSING` | Existing deficiency analysis is system-generated; no formal request/response endpoint or approved response policy exists. |
| Trusted programme identity and automatic routing | `BLOCKED` | No trusted student programme profile, provisioning source, or approved portal routing policy is available; manual Official assignment remains. |

## Prompt 4 end-to-end verification — 2026-10-27

- Actual browser/API/test-database flow completed with synthetic data:
  Student draft create/edit/upload/submit; Official claim, legal status
  transitions, and manual DUGC assignment; DUGC queue and `APPROVED` decision;
  Student status/history/outcome/next-action display. The Student dashboard
  continued to report programme identity as unverified.
- Cross-student document/application access and cross-committee record,
  document, review, download, and decision attempts were denied. Duplicate
  submission returned 409, an invalid status transition returned 400, an
  unauthorized Student assignment returned 403, and authorized document
  download returned 200. Database verification confirmed the final review,
  status history, and audit event belonged to the synthetic DUGC action.
- API logout returned 204 and the revoked token returned 401 from `/auth/me`;
  the browser returned to the account chooser and cleared both storage areas.
  An instrumentation-only `net::ERR_ABORTED` during page navigation did not
  reflect a failed server logout.
- Synthetic data and the exact generated PDFs were removed from the isolated
  test database/storage. The shared storage directory and its unrelated
  pre-existing file were preserved. No external AI or institutional service
  was called.
- Validation: backend tests **31 passed** (one existing deprecation warning),
  guardrails **13 passed**, all five focused frontend Node test files passed,
  and syntax checks passed for all frontend `.js`/`.mjs` files. Exact commands
  and the full evidence boundary are recorded in
  [the end-to-end verification report](./docs/END_TO_END_VERIFICATION_REPORT.md).
- Current blockers remain: trusted student programme identity and automatic
  committee routing `BLOCKED`; categories, eligibility, and required
  documents `NOT SPECIFIED`; formal deficiency request/response `MISSING`;
  institutional IdP/database, production authorization governance, and audit
  visibility are not verified. These are prerequisites for Prompt 5, not
  claims that the local workflow is production-ready.

## Module 1 final acceptance — 2026-10-27

- Final automated rerun: backend `31 passed` (one existing deprecation
  warning), guardrails `13 passed`, all five requested frontend Node suites
  passed, and syntax checks passed for all 21 frontend JavaScript/module files.
- Final browser UI smoke against the local static frontend confirmed the
  account chooser, labeled Student credential fields, role-choice return
  action, and no horizontal overflow at the measured responsive widths.
  The complete real-backend Student/Official/DUGC journey and authorization
  checks remain the Prompt 4 evidence above; they were not repeated against
  newly seeded records in this acceptance pass.
- No additional application-code or visual redesign change was justified by
  the acceptance review. Existing loading/error/empty states, disabled
  in-flight submission controls, status/next-action display, and explicit
  programme/policy notices were retained.
- Conclusion: `READY FOR LOCAL SYNTHETIC DEMONSTRATION` only. Trusted
  programme provisioning, application policy, committee-routing approval,
  deficiency-response rules, audit visibility policy, and live institutional
  identity/database integration remain prerequisites before institutional
  staging. PGD remains unsupported.

## Prompt 4 shared retrieval and safe ingestion — 2026-10-28

- The new `backend/services/knowledge_retrieval_service.py` facade is shared
  by the Academic Assistant and application readiness/retrieval paths. It
  allows only approved, registered ordinance sources and returns explicit
  candidate versus policy-scoped applicability, source ID/version/hash, and
  retrieval status. Retrieval failures are not converted into successful
  empty results.
- Authenticated `GET /knowledge/sources` reports discovered, fully indexed,
  or stale/unverified sources against the expected processed chunk manifest.
  Authenticated `POST /knowledge/search` accepts an explicit programme for
  general candidate search; application-scoped search additionally requires
  record access, trusted programme identity, and a resolved approved policy.
  The current default registry has no active application-type mappings, so
  application-scoped production use remains blocked.
- `/ask` now requires authentication. The Student Assistant renders
  expandable citations with source provenance. The CLI ingestion path checks
  the approved source hash and approval, preserves source/version/chunk
  provenance in index metadata, and skips unchanged complete indexes.
- PDF extraction now checks application ownership before opening a file and
  enforces 10 MiB, 100-page, and 1,000,000-character limits. It extracts
  embedded text only; OCR is not configured.
- The active CLI ingests existing programme-specific processed JSON/vector
  artifacts. PDF parsing/chunking/embedding generation is not yet a
  generalized three-programme pipeline. The reference M.Tech/Ph.D. checkouts
  remain unimported: their retrieval patterns were inspected, but their
  scheduling is simulated/in-memory and their minutes/case data is not an
  approved institutional archive. The active application has no meeting
  scheduling or minutes-generation module.
- Final validation: backend plus guardrails **76 passed** (one existing
  Starlette/AnyIO deprecation warning); all six frontend Node suites and
  syntax checks for 23 JavaScript files passed. Python compilation and
  `git diff --check` passed. The isolated `departmentai_test` workflow
  exercised authenticated application-scoped knowledge search, provenance,
  unauthenticated denial, cross-owner denial, and scope mismatch. This is not
  a browser-to-knowledge-endpoint run or production integration.

## Prompt 3 committee review workspace — 2026-10-27

| Capability | Status | Evidence / dependency |
|---|---|---|
| Membership-scoped committee queue on Committee Review page | `VERIFIED` for rendering and backend access control | The existing paginated `GET /applications` feed now appears on the DUGC Committee Review page as well as Assigned Applications. Backend integration tests verify committee-member access and denial to a non-member. Frontend rendering tests pass. |
| Open an assigned application and review its existing records | `VERIFIED` for backend integration | Existing application, document, status-history, and committee-review endpoints remain reused; no duplicate endpoint was added. |
| Human committee decision and status-history recording | `VERIFIED` for isolated test configuration | Existing `PATCH /committee-reviews/{review_id}/decision` remains the decision endpoint. Its decision, status transition/history, and audit event now commit in one transaction. Database-backed integration verifies the decision and audit actor/details. |
| Browser verification of the full committee decision journey | `PARTIAL` | Browser inspection confirmed the updated committee queue UI rendered, but the mocked API interactions did not complete because the temporary browser origin was outside the running API's CORS allowlist. Do not treat this as a verified browser workflow. |
| Formal reviewer deficiency requests and applicant responses | `MISSING` | No approved response policy or request/response endpoint exists. Existing system-generated deficiency analysis is not a formal reviewer request. |
| Trusted programme identity and automatic committee routing | `BLOCKED` | No trusted student-programme provisioning source or approved application-routing policy exists. |

Prompt 3 validation: isolated `pytest backend\tests -q` with
`DEPARTMENTAI_DATABASE_ENV=test` — 31 passed (one existing deprecation
warning); `pytest tests\test_guardrails.py -q` — 13 passed; frontend
`node .\frontend\pages\role-workspaces.test.mjs`,
`node .\frontend\services\api.test.mjs`,
`node .\frontend\services\auth.test.mjs`,
`node .\frontend\components\auth\login.test.mjs`, and
`node .\frontend\pages\student\student-dashboard.test.mjs` passed. The
committee browser check was incomplete; no live institutional integration was
performed.

Focused validation: `$env:DEPARTMENTAI_DATABASE_ENV='test'; .\.venv\Scripts\python.exe -m pytest backend\tests -q` — 31 passed (one existing Starlette/AnyIO deprecation warning); `.\.venv\Scripts\python.exe -m pytest tests\test_guardrails.py -q` — 13 passed; `node .\frontend\services\api.test.mjs`, `node .\frontend\services\auth.test.mjs`, `node .\frontend\components\auth\login.test.mjs`, and `node .\frontend\pages\role-workspaces.test.mjs` passed; `node --check .\frontend\app.js` and `node --check .\frontend\services\api.js` passed. Browser verification used the actual frontend on port 5503 with an in-memory synthetic API on port 8002; no real backend/database or institutional integration was used for that browser journey.

## Current-session verification — 2026-10-26

- Integrated authoritative 2023 M.Tech/Masters and Ph.D. ordinance assets and indexed them into isolated loopback-only `departmentai_dev`; counts were UG 246, M.Tech 105, Ph.D. 143. No application records or institutional/reference databases were changed.
- Direct local semantic searches returned five results per programme, each from only its selected source. Focused tests cover source-file filtering, corpus compatibility, `/ask` scope validation and forwarding (stubbed answer generation), and the related guardrails.
- Validation rerun: `pytest backend\tests -q` with `DEPARTMENTAI_DATABASE_ENV=test` — 31 passed (one existing Starlette/AnyIO deprecation warning); `pytest tests\test_guardrails.py -q` — 13 passed; the focused frontend API/auth/login/workspace Node tests — 4 passed; `git diff --check` — passed.
- No live authenticated browser Assistant request or external AI answer-generation call was made; do not interpret the direct retrieval check as full HTTP/RAG answer-generation or application-workflow verification.
- Updated API/frontend guidance and the [Module 1 coverage audit](./docs/MODULE1_PROGRAMME_COVERAGE_AUDIT.md) document the scope and limitations.

## Previous current-session verification — 2026-10-25

- `node --check` for all 20 frontend `.js`/`.mjs` files — passed.
- Frontend `frontend/services/api.test.mjs`, `frontend/components/auth/login.test.mjs`, `frontend/services/auth.test.mjs`, and `frontend/pages/role-workspaces.test.mjs` — passed.
- `.\.venv\Scripts\python.exe -m pytest backend\tests -q` with `DEPARTMENTAI_DATABASE_ENV=test` — 19 passed, one Starlette deprecation warning.
- `.\.venv\Scripts\python.exe -m pytest tests\test_guardrails.py -q` — 10 passed.
- Browser loaded this checkout's frontend from `http://127.0.0.1:5502/` and called the separate local dev API at `http://127.0.0.1:8001` with exact-origin CORS configuration. Liveness, readiness, OpenAPI, all three synthetic logins, role-scoped lists, application detail, document metadata, status history, committee reviews, and empty ordinance retrieval returned HTTP 200.
- Official browser workflow completed five allowed synthetic status transitions and DUGC assignment, each HTTP 200. DUGC recorded a synthetic human decision, HTTP 200. Student subsequently saw the decision/history without reviewer identity. No AI, assistant, eligibility, deficiency, or processing endpoint was invoked.
- Responsive browser checks at requested widths 376/768/1281 reported no horizontal overflow; keyboard Tab reached a button with a visible solid 2px focus outline. Screen-reader and live institutional authorization behavior remain unverified.
- `Test-NetConnection 10.219.45.43 -Port 5432 -InformationLevel Quiet` returned `False`. No institutional DB query was made. The development DB readiness route returned HTTP 200; that does not indicate institutional health.
- The existing port-8000 API returned HTTP 404 for `/health/live`; it was left untouched. Port 8001 served the new local development API. Port 5500 was not taken over; this checkout was served on port 5502 for browser integration.
- Earlier sections below are historical snapshots and may describe the pre-authentication state. Current capability and verification status is summarized here and in the linked verification/gaps reports.

## Master implementation prompt re-audit — 2026-10-23

### Baseline and roles

- Repository: `C:\Users\sojwa\OneDrive\Desktop\sojwal_proj2\DepartmentAI-Agentic-Academic-Governance`; branch `f-santosh`, already ahead of its remote by two commits at baseline.
- The worktree was already modified at baseline, including `PROJECT_STATE.md`, `README.md`, `docs/API_CONTRACT.md`, `docs/FRONTEND_IMPLEMENTATION_PLAN.md`, `frontend/app.js`, frontend styles/API tests, and two tracked backend files. Untracked baseline items included `.venv/`, `backend/tests/`, an existing patch/model archive, a document PDF, and the M11–M17 guide. None were discarded.
- Role selector and login code define exactly three UI role labels: `STUDENT`, `OFFICIAL`, and `DUGC`. Login is local prototype state; passwords are not verified with the backend. There is no dedicated Committee Member login role. API committee types `DUGC`, `DMPC`, and `DDPC` are assignment values, not user roles.
- The original frontend plan scoped work to frontend changes; the later user instruction authorized a narrowly scoped exact-origin CORS backend change. Student features are preserved; Official/DUGC have read-only known-ID lookup previews, not authenticated queues or governance writes. See `docs/ROLE_PERMISSION_MATRIX.md` and `docs/FRONTEND_BACKEND_GAPS.md`.

### Runtime and database evidence

- Local browser loaded `http://127.0.0.1:5501/` with HTTP 200. The CORS preflight returned 200 for 5500 and 400 for 5501. Port 5500 later had a shared/intermittent listener; do not stop it or use an unapproved proxy. Browser-to-backend API integration from 5501 remains blocked by CORS.
- `GET /docs` and `GET /openapi.json` returned HTTP 200. `GET /applications/2` did not respond before timeout.
- The PostgreSQL Windows service was running and loopback port 5432 was reachable. The `.env`-configured host/port was not TCP-reachable; a read-only connection using those settings timed out. A separate loopback PostgreSQL read-only query found zero rows matching applicant `STUDENT-TEST` and type `Test request`. Because loopback is not the configured database endpoint, the uncertain prior browser submission state remains unresolved there.
- No create, upload, lifecycle, committee, analysis, or AI write was issued during this re-audit. Do not clean up records without a read-only check against the configured database and explicit authorization.

### Work performed in this re-audit

- Added an environment-safe `.env.example` and ignored `.venv/` without deleting the existing environment.
- Added `frontend/config.js` and API URL validation: deployments can configure an absolute HTTP(S) API URL; embedded credentials, query/fragment parts, invalid protocols, and HTTPS-to-HTTP mixed content are rejected. Local development still defaults to `http://127.0.0.1:8000`.
- Added API-base configuration tests.
- Changed role selection/sign-in copy to mark it as a local preview, removed password fields that were never validated, and added read-only Official/DUGC known-ID review pages. Unsupported queues, audit access, and governance writes remain clearly unavailable or withheld.
- Added source-render tests for the local login warning and password-free forms.
- Added role/permission and deployment preparation documents; updated README setup instructions to match actual environment variable names and linked the evidence documents.
- No backend file was edited, and no external deployment/infrastructure was changed.

### Re-audit validation

- `node --check` for all 17 frontend `.js`/`.mjs` files — passed.
- `node frontend/services/api.test.mjs` — passed, including API-base URL default/configured/invalid/mixed-content cases and mocked request contracts.
- `node frontend/components/auth/login.test.mjs` — passed; local preview warning and password-free forms verified.
- `.\.venv\Scripts\python.exe -m pytest backend\tests -q` — 2 passed.
- `.\.venv\Scripts\python.exe -m pytest tests\test_guardrails.py -q` — 10 passed.
- Full `pytest tests -q` was not rerun in this pass: the configured DB endpoint is unreachable, and `tests/test_qa_pipeline.py` executes live question-answering calls at module import, so running it could invoke unavailable or billable AI/database paths. A prior full-suite attempt is recorded above as blocked during collection by PostgreSQL.
- Browser automation opened the landing page but rendered stale role-selector copy despite the local listener serving updated files; that earlier result is not accepted as verification of the latest UI. Later UI-only checks covered Official/DUGC dashboard navigation and application-processing page, settings, Student dashboard/unavailable application list, and a DUGC mobile viewport with no horizontal overflow. No backend request, persistence, keyboard/accessibility matrix, or authorization check was established.

### Role-workspace implementation update — 2026-10-23

- Implemented Official and DUGC governance dashboards, navigation, known-numeric-ID application lookup, read-only document/ordinance/status/committee panels, truthful unavailable states, settings, and sign-out. No staff queue endpoint exists; no processing, assignment, status, or decision write controls are exposed. Audit access is withheld for staff because the endpoint returns raw internal details without authorization.
- Preserved Student application creation/details and M09/M10 surfaces. The application-list view reports that the backend has no list endpoint; it does not fabricate counts or rows.
- The role lookup uses only application detail, document metadata, ordinance retrieval, status history, and committee-review GETs. Eligibility/deficiency GETs are intentionally excluded from that lookup because source inspection shows database writes; eligibility may also invoke Gemini.
- Verified from source/OpenAPI: no general or assigned application-list route, no authentication/session route, and no document-content download route. Existing app-specific route availability does not mean the configured DB is reachable.
- Runtime evidence: `/docs` and `/openapi.json` HTTP 200; safe probe `GET /applications/0` timed out without a response; CORS preflight 200 at port 5500 and 400 at port 5501. No database-backed role lookup or write was run.
- Passed: syntax checks for 19 frontend JS/MJS files; API, login preview, and role-workspace Node tests; backend focused tests (2); guardrails (10). Full pytest suite not run because the QA pipeline imports live database/AI behavior and the configured DB is unavailable.
- Changed in this implementation: `frontend/app.js`, `frontend/index.html`, `frontend/services/api.js`, `frontend/services/api.test.mjs`, `frontend/pages/role-workspaces.js`, `frontend/pages/role-workspaces.test.mjs`, `frontend/styles/role-workspaces.css`, `docs/FRONTEND_BACKEND_GAPS.md`, `docs/ROLE_PERMISSION_MATRIX.md`, `docs/END_TO_END_VERIFICATION_REPORT.md`, `docs/M11_M17_MANUAL_TESTING_GUIDE.md`, `docs/DEPLOYMENT_GUIDE.md`, `docs/API_CONTRACT.md`, `README.md`, and `PROJECT_STATE.md`.
- No backend file was edited by this implementation. Pre-existing tracked/untracked backend changes remain in the shared worktree and are not attributable to this work.

### Master prompt re-verification — 2026-10-23

- Configured database host `10.219.45.43`, port `5432` (credentials omitted), failed a TCP reachability probe. API remains listening on `127.0.0.1:8000`; `/docs` and `/openapi.json` returned HTTP 200; `GET /applications/0` timed out after about 4.16 seconds.
- CORS OPTIONS requests returned HTTP 200 and matching allow-origin headers for `127.0.0.1:5500` and `localhost:5500`, and HTTP 400 for `127.0.0.1:5501`. Browser fetch from 5501 failed CORS. Port 5500 was occupied by a Python listener that returned an empty response for `/`; the listener was not stopped or replaced.
- A temporary `[::1]:5500` frontend server responded directly with HTTP 200, but browser navigation through `localhost:5500` failed loading the login-role-selector module (`net::ERR_EMPTY_RESPONSE`). The temporary server was stopped; the existing IPv4 listener remains untouched, so this is not a usable browser workaround.
- Browser-only navigation visited all Student, Official, and DUGC pages; measured CSS widths 376/768/1281 had no horizontal overflow. No real application ID or write/AI operation was used.
- Updated local preview selector wording so Official and DUGC explicitly advertise read-only status and unavailable processing/decisions. Mock API contract tests now exercise application detail, ordinance, eligibility, and deficiency request helpers.
- Student activity timeline now presents an unavailable state and does not call the raw unauthenticated audit endpoint.
- Detailed 19-route inventory and status are recorded in `docs/FRONTEND_BACKEND_GAPS.md`. No live database-backed endpoint returned successfully; endpoint wrappers and UI integration remain unverified live.
- Files changed in this continuation: `frontend/app.js`, `frontend/components/auth/login-role-selector.js`, `frontend/components/auth/login.test.mjs`, `frontend/services/api.test.mjs`, `README.md`, `PROJECT_STATE.md`, `docs/FRONTEND_BACKEND_GAPS.md`, `docs/API_CONTRACT.md`, `docs/END_TO_END_VERIFICATION_REPORT.md`, `docs/M11_M17_MANUAL_TESTING_GUIDE.md`, `docs/DEPLOYMENT_GUIDE.md`, and `docs/ROLE_PERMISSION_MATRIX.md`.
- Pre-existing at continuation start: the shared worktree was already dirty, including `backend/retrieval/semantic_search.py`, `backend/services/ai_analysis_service.py`, untracked `backend/tests/`, prior frontend implementation files, docs, and artifacts. No backend file was changed by this continuation.

### Current readiness

**NOT READY FOR DEPLOYMENT.** Missing server-side authentication/authorization is a material privacy/security blocker. Official/DUGC pages are read-only previews without queue/list or governance write support; live database integration is blocked, port 5501 is not CORS-allowed, and full accessibility/role verification is outstanding. See `docs/FRONTEND_BACKEND_GAPS.md`, `docs/END_TO_END_VERIFICATION_REPORT.md`, and `docs/DEPLOYMENT_GUIDE.md`.

## Database safety note

During browser mock setup, a few create-form submissions remained pending because an interception pattern did not match the exact `/applications` path. Their backend response and persistence could not be confirmed. A read-only query for `applicant_identifier = 'STUDENT-TEST'` and `application_type = 'Test request'` against the configured database timed out. A later read-only query against the separate local loopback database returned zero matching rows; this does not establish the configured database state. Do not assume those attempts were harmless or delete records blindly. When the configured database is reachable, inspect matching rows read-only and decide whether any confirmed test rows should be retained or cleaned up.

## M09 — Historical verification

- The existing frontend renders the analysis result as advisory text and displays model/result metadata.
- Prior-session notes record a successful live `POST /applications/1/ai-analysis` returning HTTP 200 and a read-only persistence check. This was not rerun in the current session; the operation may call an external AI service and persists a record.
- Current frontend API contract checks still cover the empty-body POST path.
- Do not claim current live Gemini or database success based solely on this historical evidence.

## M10 — Historical verification

- The Academic Assistant page, request contract, safe text/source rendering, loading/error handling, empty-input handling, and clear-conversation behavior are recorded as implemented.
- Prior-session notes record mocked browser checks and a live `/ask` success after a retrieval connection-lifecycle fix. That live result was not independently repeated in this session.
- Current semantic-search regression tests passed (2 tests); the broader QA pipeline test could not reach PostgreSQL.
- No paid/external Gemini request was made for this task.

## Changed files for this implementation

- `frontend/app.js`
- `frontend/services/api.test.mjs`
- `frontend/components/layout/sidebar.js`
- `frontend/components/layout/topbar.js`
- `frontend/styles/application-details.css`
- `frontend/styles/layout.css`
- `frontend/styles/global.css`
- `docs/API_CONTRACT.md`
- `docs/FRONTEND_IMPLEMENTATION_PLAN.md`
- `docs/M11_M17_MANUAL_TESTING_GUIDE.md`
- `README.md`
- `PROJECT_STATE.md`

## Known limitations and next actions

- The backend has no authentication or authorization; role selection is prototype-only and cannot secure student-visible data.
- The audit route returns raw internal records. The UI hides actor IDs/details and filters actions, but that does not protect the underlying endpoint.
- Browser-to-backend CORS permits only frontend origins on port 5500. A different frontend port can render the site but is not an allowed browser API origin.
- There is no student application-list endpoint; applications can currently be opened from a confirmed create response, not from a populated list.
- Official and DUGC application queue endpoints, document-content download, and backend authentication/session endpoints are also absent. Application-specific lookups exist in the contract but have not been verified against the configured database.
- `GET /applications/{id}/eligibility` and `GET /applications/{id}/deficiencies` mutate database records and are not suitable for implicit/read-only review loads.
- The mandatory role-by-role evidence and next actions are in `docs/FRONTEND_BACKEND_GAPS.md`.
- Confirm database state before running any write-path tests or further create requests.
- Complete M16 only against an explicitly isolated local test database; then finish the full M15 device/accessibility review and M17 audit.
- Do not begin M18 or later.

## Prompt 5 - Isolated Module II security boundary

- Added explicit Module II database profiles with no fallback to Module I/root configuration, and a fail-closed server-side permission policy keyed to authenticated account IDs with exact department scopes.
- Added authenticated, read-only faculty/research/statistics endpoints and secured export endpoints with fixed datasets/columns, department scoping, and bounded result sizes. Removed the public Module II export UI route and did not add Module II frontend navigation.
- The standalone chatbot endpoint remains denied pending a supported department-scoped retrieval capability. Supervision access remains denied.
- Spreadsheet exports prefix formula-like text values to prevent CSV/XLSX formula interpretation.
- Verification in the isolated test profile: 182 backend tests passed across Module I regressions and Module II suites; focused Module II security/export tests passed again (44 tests). All 7 frontend Node tests, frontend JavaScript syntax checks, Python compilation, and `git diff --check` passed.
- No Module II database was connected, created, or changed; no real Module II credentials or policy grants were added. Existing unrelated worktree changes were preserved; no commit or push was made.

## Prompt 6 — Module II Faculty & Research frontend

- Added authenticated `GET /module2/capabilities`; it returns only the current authenticated account's effective permissions and exact department scope, plus a non-connecting indicator for whether the selected isolated database profile is configured. No grant still returns 403; invalid policy remains fail-closed.
- Integrated a permission-gated **Faculty & Research** area into the existing SoStudy shell. It provides an overview, scoped faculty directory and detail, bounded publications/projects/achievements explorer, scoped persisted statistics, and permission-discovered allowlisted exports through the shared bearer API client.
- The browser does not submit department parameters or infer authorization from a selected role. Search/year filters, pagination, stale-response protection, retry/error/empty states, and export format/dataset display follow the active API contract.
- Data quality, patents/consultancy as separate record categories, period-filtered statistics, student supervision, chatbot, CRUD, and formal report review/approval remain unavailable; the UI labels unsupported features rather than fabricating records or counts.
- Verification: **185 backend tests passed** across relevant Module I regressions and Module II suites; **9 frontend Node test files passed**. All frontend `.js`/`.mjs` syntax checks, Python compilation, and `git diff --check` passed. Six dependency/framework deprecation warnings remain.
- Browser-to-backend Module II acceptance was not run: this checkout has no private `.env.module2.test` or provisioned loopback `departmentai_module2_test` database, and no runtime grant/records for browser acceptance were provisioned. Route-level tests use temporary permission-policy fixtures and mocked database access; no Module II or institutional database was connected.
- The requested `module2/README.md` does not exist in this checkout; updated `docs/API_CONTRACT.md`, `docs/INTEGRATION_INVENTORY.md`, `docs/ROLE_PERMISSION_MATRIX.md`, `docs/SOSTUDY_SOURCE_INTEGRATION_MAP.md`, the root README, and `frontend/README.md` instead.
- Preserved the existing `f-santosh` worktree, including unrelated changes. No commit or push was made.

## Prompt 7 — Module II data-quality inspection

- Added the separate, fail-closed `module2.data_quality.read` permission and authenticated `GET /module2/data-quality/issues`. The endpoint accepts only a supported record-category filter and bounded pagination; department scope is always derived from the authenticated grant and applied in SQL.
- Added read-only checks for blank values in schema `NOT NULL` text fields, reversed project/achievement date ranges, publication date/year mismatches, and explainable potential-duplicate groups. Duplicate matches are explicitly heuristic, include comparison rules/evidence, and cap candidate-value/ID previews. Scans are capped at 5,000 records per category and fail with HTTP 503 rather than return partial counts.
- Added a permission-gated, responsive Data Quality view with category filtering, objective/heuristic labels, evidence details, summary counts, pagination, empty/error/retry states, stale-response protection, and no simulated review controls. No persisted review/audit workflow exists, so marking reviewed, dismissal, correction, and sign-off are not implemented.
- The administrative assistant remains unavailable: `module2.faculty.chat` is unsupported, the temporary standalone chatbot is not mounted in the main API, and its current retrieval/aggregate paths are not bound to the authenticated department grant. The SoStudy UI does not call it or send retrieved content to a model.
- The local PostgreSQL service and loopback port are available, but `.env.module2.test` and dedicated test credentials/profile are absent. Did not guess credentials, use the existing root `.env`, create a database, or access an institutional database. Live browser-to-backend acceptance could not run; API tests mock database rows.
- Validation: **60 Module II security/export tests passed** (0 failures, 7 existing dependency deprecation warnings); **109 safe Module I unit/regression tests passed** (0 failures, 1 dependency deprecation warning); all **9 frontend test files passed**. Python compilation, formatting checks for newly added Python files, editor problem checks, syntax checks for 28 frontend JS files, and `git diff --check` passed.
- Broader pre-existing test coverage surfaced two unrelated failures in already-dirty files: `tests/test_source_formatter.py` expects the old citation response shape, and `backend/tests/test_application_policy_registry.py` expects `RESOLVED` where current code returns `UNVERIFIED`. They were not changed because they are outside this task. A separate broad test-directory invocation also reached a collection-time side effect in `tests/test_qa_pipeline.py`, which attempted the existing configured database and timed out; no database session or write completed. That test and database integration tests were excluded from the final safe regression runs.
- Preserved all pre-existing worktree changes. No commit or push was made.

## Prompt 8 — Module II configurable draft reporting

- Added the separate `module2.reports.generate` permission and authenticated `/module2/reports/templates`, `/preview`, and `/generate` routes, mounted below `/module2/reports`. The fixed catalogue covers faculty directory, publication, project, achievement, and department research overview drafts.
- Report SQL uses fixed query/column mappings, the caller's server-authorized department scope, only advertised persisted-year filters, a 5-second query timeout, and a 2,000-row cap that rejects rather than returns partial results. Preview returns metadata/counts and at most 20 allowlisted sample rows.
- Added server-side DOCX, XLSX, and PDF output with dependency availability reported per template, bounded cell text, spreadsheet formula escaping, and draft/not-approved status, timestamp, template version, authorized scope, filters, counts, and limitations. Generated files are sent directly with no-store headers; no report history, official template, or approval/sign-off workflow was invented.
- Integrated a separate Reporting view into the authenticated Module II frontend, with server-discovered templates, supported filters/formats, escaped previews, errors/retries, stale-response protection, and downloads initiated only after a successful non-empty server file response. Existing dataset exports remain separate.
- Updated the API contract, permission matrix, frontend guide, SoStudy source integration map, and this project state.
- Verification: **88 Module II security/export tests passed**, including report route, scope, invalid input, limits, and rendered DOCX/XLSX/PDF content. **All 9 frontend Node test files passed.** Python compilation, Pylance syntax/diagnostic checks, JavaScript syntax checks, and `git diff --check` passed. Ruff is not installed in the project virtual environment. Existing Starlette/ReportLab deprecation warnings remain.
- Live browser/database acceptance remains unavailable: no private `.env.module2.test`, dedicated test credentials, or provisioned Module II test database/grant/data were available. Tests use synthetic policy/database fixtures; no Module II or institutional database was accessed.
- Preserved all pre-existing worktree changes. No commit or push was made.

## Follow-up — Module II isolated acceptance and live UI check (2026-10-28)

- Inspected the full dirty worktree before editing: 95 status entries (53 tracked changes and 42 untracked entries). Preserved all existing changes; no commit or push was made.
- The Module II resolver requires the explicit `DEPARTMENTAI_MODULE2_DATABASE_ENV=test` selector and private `.env.module2.test`, validates loopback and exact database name `departmentai_module2_test`, and does not create a database/schema or fall back to Module I. The private profile and runtime grant policy were absent. Existing Module II security/export fixtures use temporary synthetic permission policies and mocked database cursors; no database-seeding or integration fixture exists in those suites.
- Verified that an absent selector and a selected-but-missing Module II test profile both fail closed, even with Module I selectors present. A read-only catalog query through the verified `departmentai_test` profile confirmed `departmentai_module2_test` does not exist; the connected test role has neither `CREATEDB` nor superuser privileges. No authorized Module II credentials or database-administrator credential were available, so provisioning stopped before any database mutation. The existing `departmentai_test` database was queried read-only only and was not modified.
- Current Module II live-user, scope, capability, and persisted-record acceptance was not run. Unit fixtures use synthetic principals such as user IDs 701, 902, and 905 with `Synthetic Department` grants; tests cover individual faculty/research/statistics/data-quality/export/report permission paths and scope denial using mocked rows. These IDs/grants were not created in any database. No report files were generated from live records or inspected through the UI.
- The browser navigation to `http://127.0.0.1:5500/` returned connection refused. Ports 5500, 5506, 8000, and 8002 had no active HTTP service at the check; there was no running SoStudy UI/API to authenticate against. Standalone assistant unavailability and unsupported editing/approval remain contract-level behavior, not live-browser checks in this follow-up.
- Module II security/export/report tests: **88 passed, 0 failed, 0 skipped**, with 10 dependency deprecation warnings. Frontend Node tests: **9 passed, 0 failed, 0 skipped**. `compileall` passed for `backend` and `module2`; JavaScript syntax checks passed for 28 frontend files. These are isolated test results, not live acceptance.
- PostgreSQL 18 is installed locally and its Windows service was running. The effective `listen_addresses` is `*`, with sockets on `0.0.0.0:5432` and `[::]:5432`. Windows firewall profiles were enabled; inspection found a Public-profile inbound TCP/5432 allow rule scoped to one private remote address. `pg_hba.conf` allows loopback SCRAM connections and has one separate host rule for database `departmentai`, user `postgres`, and one private address. This is evidence of a locally hosted database service with a specifically permitted network path, not proof of Internet reachability; routing, remote-host identity, effective policy/GPO, and end-to-end reachability were not tested. No firewall or network settings were changed.
- Institutional readiness remains blocked pending authorized trusted student identity, approved application-policy mappings, governance approval/signatory policy, and separately verified external integrations.

## Local website/API startup — 2026-10-28

- The frontend was already serving on `127.0.0.1:5500` and was preserved. The frontend client is configured for API origin `http://127.0.0.1:8002`.
- The existing `.env.development` resolves as loopback `departmentai_dev`, but a prior read-only connection probe reported a non-loopback PostgreSQL server address. The backend source resolver itself validates the configured client host and exact profile database; the earlier manual server-address guard rejected the development target. No development-profile server was started.
- The existing `.env.test` passed the source resolver's explicit test-profile checks and the application's `get_connection()` path. A read-only identity query returned `departmentai_test`, PostgreSQL server address `127.0.0.1/32`, and 24 public tables. No credential values were printed.
- Started Uvicorn using the repository virtual environment, `DEPARTMENTAI_DATABASE_ENV=test`, exact CORS origin `http://127.0.0.1:5500`, and bind `127.0.0.1:8002`. API PID at verification: 2652. `/health/ready` returned HTTP 200 `{"status":"ready"}`; `/openapi.json` returned HTTP 200 with the expected API title and 12 Module II route declarations. The process is intended to remain running.
- Frontend returned HTTP 200 and rendered the normal signed-out account chooser. After browser reload, the actual frontend `/auth/me` call reached the backend and received HTTP 401 because there is no signed-in session; it no longer reports a connection failure. An exact-origin CORS preflight returned HTTP 200 with the expected origin and methods. No credentials were used, and no authenticated Student/Official/committee workflow was exercised.
- Module II remains without its own profile, database, or runtime grant; it was not pointed at the Module I test database. Its absence did not prevent API startup.
- Validation: focused Module I DB-profile/CORS/governance/application-policy suites and cleanup-safe synthetic DB integration tests: **36 passed**, one Starlette/AnyIO deprecation warning. Module II fail-closed/security tests: **58 passed**, nine Starlette deprecation warnings. Frontend Node tests: **9 passed**. Python `compileall` passed; `node --check` passed for 28 frontend JS/MJS files. No tests failed or skipped.
- Existing tracked/untracked work was preserved. No application config/security checks were weakened, no database was created or migrated, and no commit or push was made.

## Follow-up — Live demo, Module II blocker, and host boundary (2026-10-28)

- Rechecked the running site and API: `http://127.0.0.1:5500/` and
  `http://127.0.0.1:8002/health/ready` both returned HTTP 200. Both listeners
  are bound to loopback. The real authenticated synthetic M.Tech browser flow
  described above remains persisted in `departmentai_test`; afterward,
  `/auth/logout` returned 204 and a read-only query found zero unexpired,
  non-revoked sessions for each of the four reserved demo accounts.
- Module II remains unprovisioned: `.env.module2.test` is absent and a
  read-only catalog check confirmed `departmentai_module2_test` is absent.
  The available local role lacks `CREATEDB` and superuser privileges; no
  authorized database-admin credential or provisioning path is available.
  No substitute database, grant, account, schema, or fixture was created.
  The synthetic browser principal received 403 from `/module2/capabilities`;
  there was no live Module II data, export, or report acceptance.
- Module II security/export/report tests: **88 passed, 0 failed, 0 skipped**,
  with 10 dependency deprecation warnings (AnyIO, Starlette status-code, and
  ReportLab). These tests use synthetic principals and mocked database
  cursors. Renderer tests opened and inspected unit-fixture CSV, XLSX, DOCX,
  and PDF output; no live report files were generated. Frontend Node tests:
  **9 passed, 0 failed, 0 skipped**. Earlier targeted backend tests: **65
  passed** with one Starlette/AnyIO deprecation warning. Python compilation,
  JavaScript syntax checks for 28 files, and `git diff --check` passed.
- Effective PostgreSQL `listen_addresses` is `*`, with wildcard IPv4 and IPv6
  listeners on port 5432. The active Public-profile Windows Firewall has an
  enabled inbound TCP/5432 allow rule named `DepartmentAI PostgreSQL from
  current laptop`, scoped to remote IPv4 `10.219.45.224`; its local-address,
  program, service, and interface filters are `Any`. The demo application
  itself connects to the database through `127.0.0.1/32`. The firewall rule
  shows a host-level allow for that one remote address, but does not prove a
  successful remote or Internet connection. Routing, remote-host identity,
  upstream/NAT policy, and external reachability require authorized
  host/network verification. No firewall or network settings were changed.
- Existing worktree changes were preserved. No commit or push occurred.
  Institutional readiness remains blocked on trusted identity, approved
  policy mappings, governance/signatory authority, and external integrations.

# SoStudy Source-to-Frontend Integration Map

**Review date:** 2026-10-28  
**Project:** `DepartmentAI-Agentic-Academic-Governance`  
**Branch at review:** `f-santosh`  
**Scope:** Source-grounded integration map. This document was updated after the
Prompt 6 Module II frontend implementation; the separate reference checkouts
remain read-only and were not changed.

## 1. Scope and evidence

The active checkout is
`C:\Users\sojwa\OneDrive\Desktop\sojwal_proj2\DepartmentAI-Agentic-Academic-Governance`.
The separate read-only references are
`C:\Users\sojwa\OneDrive\Desktop\sojwal_proj2\review-yogesh-mtech` and
`C:\Users\sojwa\OneDrive\Desktop\sojwal_proj2\review-yogesh-phd`. Neither
reference is imported into the active runtime.

The worktree was already substantially modified and contained untracked files
before this review. Those changes were preserved. The report below is based on
route declarations, request models, service implementations, schema, frontend
call sites, tests, and current documentation. Historical verification is
identified as historical rather than treated as proof of the current
configuration.

### Markdown instructions and evidence read

**Active project**

- `README.md` — quick start, module scope, roadmap, and stated deliverables.
- `frontend/README.md` — browser architecture, API origin, local startup, and
  authentication behavior.
- `PROJECT_STATE.md` — current readiness, policy, retrieval, and governance
  implementation status and blockers.
- `docs/INTEGRATION_INVENTORY.md` — current M.Tech/Ph.D. source-to-target
  mapping and Module II/export boundaries.
- `docs/API_CONTRACT.md` — current authentication, retrieval, application,
  document, queue, role, and governance API contracts.
- `docs/ROLE_PERMISSION_MATRIX.md` — role and record-level access, committee
  memberships, and known missing workflows.
- `docs/MODULE1_PROGRAMME_COVERAGE_AUDIT.md` — current Module I lifecycle,
  policy/identity boundary, committee mapping, and scheduling/minutes status.
- `docs/END_TO_END_VERIFICATION_REPORT.md` — latest governance/readiness
  status and explicit limits on prior browser checks.
- `docs/MANUAL_END_TO_END_WORKFLOW_TEST.md` — local synthetic setup, startup,
  and Student-to-Official-to-committee demonstration steps.
- `docs/FRONTEND_IMPLEMENTATION_PLAN.md` — existing plain-JS design and
  no-fabricated-data rules. Its “zero backend editing” and module-status text
  predates the current backend work; use actual current source and the newer
  state documents for present contracts.
- `module2/thesis_data/source_repository/README.md` — source-preservation and
  data-validation boundaries for thesis source files.

**M.Tech reference, read-only**

- `review-yogesh-mtech/README.md`
- `review-yogesh-mtech/BUILD_HISTORY.md`
- `review-yogesh-mtech/SCHEDULING_README.md`
- `review-yogesh-mtech/SCHEDULING_BUILD_HISTORY.md`

**Ph.D. reference, read-only**

- `review-yogesh-phd/README.md`
- `review-yogesh-phd/BUILD_HISTORY.md`
- `review-yogesh-phd/SCHEDULING_README.md`
- `review-yogesh-phd/SCHEDULING_BUILD_HISTORY.md`

## 2. Source implementation map

| Capability | M.Tech reference | Ph.D. reference | Active backend status | Active frontend status and integration direction |
|---|---|---|---|---|
| Ordinance Q&A and source retrieval | `backend/api/routes.py`, `backend/rag/qa_pipeline.py`, and `backend/retrieval/semantic_search.py`; local PostgreSQL/pgvector and embedding-model configuration | Same general path in the separate Ph.D. tree | Authenticated `/ask`, `/knowledge/sources`, and `/knowledge/search`; active retrieval uses registered UG/M.Tech/Ph.D. ordinance corpora and provenance checks | Academic Assistant uses `frontend/services/api.js` and renders citations. Keep the existing shared active retrieval; do not mount the reference servers or import their synthetic cases as authority. |
| Student/application creation and document processing | No corresponding application-intake workflow established in the inspected reference scope | No corresponding application-intake workflow established in the inspected reference scope | Existing `/applications` routes, document service, PDF embedded-text extraction, classification, and persisted policy-aware readiness in `backend/api/routes.py` and `backend/services/` | Student application form, upload, document list, readiness, details, and submit actions already call active endpoints. Use those contracts; do not add a parallel application workflow. |
| Required documents and application readiness | Retrieved ordinance and synthetic examples are not an approved application-specific checklist | Same limitation; retrieval includes synthetic examples in its separate corpus | `application_policy_registry.py`, `programme_identity.py`, and `application_readiness_service.py` require verified identity and exact approved mappings; the checked-in registry has no active application types | Readiness status and blockers are displayed in one Student draft analysis panel. The current deployment cannot produce operational readiness because identity and application-type policy are unconfigured. Never infer a checklist from generic RAG results. |
| Official queue and human decision | Not the focus of the references | Not the focus of the references | Shared queue, atomic first-Official claim, application access, status history, committee assignment, and committee decision routes are persisted and authenticated | Existing role workspace consumes queue/list/detail/history/decision calls. Expose backend-authorized actions only; do not simulate state changes in the browser. |
| Meeting scheduling | `POST /schedule/propose` and `/schedule/approve`; synthetic timetable/calendar constraints; proposal store is process-local; fixed frontend date range and simulated dispatch | Same API shape and transient proposal model; hard-coded frontend range/slot and simulated HoD consent/dispatch | Persistent authenticated `/governance` routes with availability, candidate-slot checks, agendas, records, confirmations, audit, and policy-gated approval | DUGC Meeting Governance page and API helpers exist. It is the integration target; do not use the reference scheduler's fixed dates, in-memory state, or mock messaging. |
| Minutes | Draft Markdown generation; provider setup/import mismatch noted in reference docs; filesystem output | Draft Markdown generation with fallback/Gemini path; filesystem output | Versioned persisted manual minutes, revisions, comments, review/sign-off, conflict indicators, and optional explicitly approved Gemini generation | Governance UI and helpers are present. Approval/finalization remain blocked by the empty default workflow registry; final-minutes indexing is not implemented. |
| Module II faculty/reporting | No Module II faculty/reporting implementation found in either inspected reference | No Module II faculty/reporting implementation found in either inspected reference | Active checkout has an isolated Module II database profile, fail-closed account/department permissions, authenticated capability discovery, and read-only faculty, publication, project, achievement, statistics, data-quality, and fixed export routes | SoStudy has permission-gated `Module II — Faculty & Research` views in the existing authenticated shell. Data-quality checks are bounded and read-only; no database or user-provided department scope is sent by the browser. |

### Reference behavior that must not be presented as institutional workflow

Both references contain useful retrieval and scheduling examples, but their
scheduler proposals are process-local, dates/committee choices are hard-coded
in the demo frontends, communications are simulated, and consent is represented
by an API boolean rather than authenticated HoD identity. The references do
not provide the active application's document intake/readiness gate, verified
identity, or a governed finalized-minutes archive. Their retrieval includes
synthetic cases/minutes, which are not imported as active institutional
precedent.

## 3. API-to-frontend inventory

All active application and governance operations below require a bearer
session. The application router applies `get_current_user`; role and record
scope are enforced in the route/service. The frontend API client attaches the
stored bearer token and centralizes JSON/multipart errors.

| Workflow | Actual endpoint and contract | Authorized scope | Existing frontend use / remaining connection |
|---|---|---|---|
| Authentication | `POST /auth/login` `{username,password}` → token and server-provisioned user; `GET /auth/me`; `POST /auth/logout` → 204 | Server-provisioned Student, Official, or DUGC identity; local password auth only in explicit development/test profiles | `frontend/services/auth.js` and `api.js`; role selection is not authorization. No institutional IdP is configured. |
| Application list | `GET /applications?limit=20&offset=0` → `{items,limit,offset}` | Student by subject, Official by assignment, DUGC by committee membership/review | Student and role queues use the existing paginated API client. |
| Create/edit | `POST /applications` `{application_type,title?,description?}` → `{id,application_number,status,created_at}`; `PATCH /applications/{id}` `{application_type,title,description}` | Student only; authenticated subject supplies owner; edit only own `DRAFT` | Create form and draft editor call existing helpers. Type is intentionally free text because no approved category allowlist exists. |
| Details/history | `GET /applications/{id}`; `GET /applications/{id}/status-history` → `{application_id,history}` | Own Student record, assigned Official record, or committee-scoped record; out-of-scope returns 404 | Student details and Official/committee record lookup call these routes. Student history omits actor identity. |
| Upload/list/download | `POST /applications/{id}/documents` multipart `{file,document_type?}`; `GET /applications/{id}/documents`; `GET /applications/{id}/documents/{document_id}/download` | Student upload only on own draft; application access required for list/download; 10 MiB cap; upload after submission returns 409 | Student upload/list are wired. Student rows render metadata without Download/Validate/Extract/Classify buttons; authorized reviewer workflow retains document access. |
| Readiness and analysis | `GET /applications/{id}/readiness`; Student-only `POST /applications/{id}/readiness/analyze`; read-only `GET /applications/{id}/analysis` | Application-access scope; analysis and upload are Student draft operations | Student uses readiness endpoint and `canSubmitApplication`; reviewer loads saved combined analysis. Legacy eligibility remains advisory and freshness is `NOT_TRACKED`. |
| Submit and Official queue | Student `POST /applications/{id}/submit`; Official `GET /official/applications/unassigned?limit&offset`; Official `POST /applications/{id}/claim` | Student owns draft; Official role for queue/claim; atomic row lock prevents duplicate claim | Existing helpers and queue UI. Successful submission is persisted before showing confirmation; claim creates an assignment while status remains `SUBMITTED`. |
| Official status/committee | Official `PATCH /applications/{id}/status` `{new_status,reason?}`; Official `POST /applications/{id}/committee` `{committee_type}`; `GET /applications/{id}/committee-reviews` | Official must have record access; committee target must have configured members | Role workspace consumes existing status and assignment actions; actual allowed transitions are supplied by backend and must not be invented in the UI. |
| Committee decision | `PATCH /committee-reviews/{review_id}/decision` `{decision,decision_reason}`; `GET /applications/{id}/committee-reviews` | DUGC role plus matching membership/review; actor is derived from session | Current committee UI exposes human decision controls and refreshes persisted state. DUGC/DMPC/DDPC are committee types, not separate login roles. |
| Knowledge source/search | `GET /knowledge/sources`; `POST /knowledge/search` with `{domain,query,programme?,application_id?,source_ids?,source_types?,source_version?,section_numbers?,limit?}` | Authenticated; application-scoped search additionally needs record access, verified identity, and resolved approved policy | Assistant/source UI uses the active retrieval helpers. General programme selection is candidate search scope only, never identity or application authorization. |
| Assistant | `POST /ask` `{question,conversation_history?,programme?}` → `{answer,sources}` | Authenticated; programme is `UG`, `MTECH`, or `PHD` informational corpus | Academic Assistant uses current API and source citations. It does not determine eligibility or route a record. |
| Meeting workspace/configuration | `GET /governance/configuration`, `GET /governance/integrations`, `GET /governance/meetings?committee_type?`, `POST /governance/meetings` (`MeetingCreateRequest`), `GET /governance/meetings/slots?committee_type&range_start&range_end&duration_minutes&exclude_meeting_id?`, `POST /governance/availability` (`AvailabilityRequest`) | DUGC login role plus a matching DUGC/DMPC/DDPC membership; create/availability are scoped to that committee | Existing governance workspace uses these API client methods. Proposals require timezone-aware future ranges, 30–240 minute duration, agenda, and optional idempotency key. |
| Meeting operations | `GET /governance/meetings/{id}`, `PATCH /governance/meetings/{id}/slot` `{proposed_slot_start}`, `POST .../{id}/approve`, `POST .../{id}/response` `{response: CONFIRMED\|DECLINED}`, `GET .../{id}/agenda`, `PATCH .../{id}/agenda` `{agenda}`, `GET .../{id}/notice`, `POST .../{id}/records` `{agenda_item_index?,record_type,content}` | Matching committee membership; linked application IDs require matching committee access; approval additionally requires configured policy | Existing frontend uses these operations. Notice is a preview; it is not dispatched. |
| Minutes review | `GET /governance/meetings/{id}/minutes`, `POST .../minutes`, `POST .../minutes/generate`, `PATCH .../minutes/{version_id}` `{content}`, `POST /governance/minutes/{version_id}/submit`, `POST .../comments` `{comment}`, `POST .../approve` | Matching committee membership; configured policy/signatory for final approval | Existing frontend renders versioned manual/optional AI draft lifecycle. AI is opt-in; indexing is not implemented. |
| Legacy processing/advisory | `POST /applications/{id}/process` is Official/assigned-record scoped and the service returns HTTP 409 while processing is unavailable; Student-owned `POST /applications/{id}/ai-analysis` is a separate persisted AI advisory operation; `GET /applications/{id}/eligibility/results` reads saved legacy results | Route-specific checks: Official assignment for `/process`, Student ownership for `/ai-analysis`, application access for stored eligibility | Neither legacy processing nor eligibility should replace the consolidated readiness contract or satisfy the submission gate. |
| Module II capabilities | `GET /module2/capabilities` → `{permissions,departments,database_profile_configured}` | Existing bearer session plus a server-side grant for the authenticated account ID; no database connection is opened | SoStudy uses the returned effective permissions for sidebar and feature visibility. Department scope is displayed only as server-supplied context and is not an editable filter. |
| Module II faculty and research | `GET /module2/faculty`, `GET /module2/faculty/{faculty_id}`, and `GET /module2/research/records/{publications,projects,achievements}` | Exact `module2.faculty.read` or `module2.research.read` permission; database queries enforce exact grant departments | Directory/detail and bounded research pages use the shared authenticated API client. Search and year filters match backend parameters; page size is 50. |
| Module II statistics and exports | `GET /module2/research/statistics`, `GET /module2/export/datasets`, and `GET /module2/export/{dataset}/download` | Separate statistics/export permissions; static datasets and columns, bound to grant department scope | The statistics view reports persisted counts without time filters. The export UI discovers only the caller's permitted datasets and downloads through the authenticated client. These are not reviewed or approved formal reports. |
| Module II data quality | `GET /module2/data-quality/issues?category=&limit=50&offset=0` | Separate `module2.data_quality.read` permission; exact authenticated grant departments; 5,000-record/category scan cap | The SoStudy view distinguishes empty data, no findings, objective checks, and heuristic duplicate suggestions. It is read-only because no review/audit persistence model exists. |
| Module II faculty chatbot | Separate standalone `module2.chatbot_ui.server`; its POST remains denied pending a supported authenticated retrieval permission | No supported permission or authorized retrieval route | Remains unavailable in SoStudy and is not mounted in the main app; current standalone retrieval/count paths are not bound to the signed-in department grant. |

**Not found as active API routes:** faculty profile CRUD/search, research-record
CRUD, ingestion job control, persisted data-quality review actions, period-filtered formal
reports, report-template selection, report preview/review, or human
verification/sign-off of generated institutional reports. No separate
Official “approve directly versus schedule meeting” decision endpoint was
found; Official status changes and committee assignment are the implemented
operations.

## 4. Workflow-state map

| Stage | Current state | Actual action | Backend next state / effect | Frontend requirement |
|---|---|---|---|---|
| Student begins | No application | `POST /applications` | Creates persisted `DRAFT`, server binds applicant identity | Show returned ID and number; no fabricated type/category choices. |
| Draft changes | `DRAFT` | `PATCH /applications/{id}` or upload document | Persisted fields/documents change; prior analysis becomes stale | Keep controls limited to draft; show processing progress and any API error. |
| Readiness check | `ANALYSIS_PENDING` or stale | Student `POST .../readiness/analyze` | Persists processing outcomes, identity/policy resolution, required-doc matches/deficiencies, citations, blockers and input fingerprint | Render actual state; null/unknown deficiency data is not zero. `DRAFT` is not a deficiency. |
| Submission gate | `READY` only if all checks pass | `POST /applications/{id}/submit` | In a row-locked transaction, backend rechecks current fingerprint, approved policy/identity, source evidence, document processing, zero deficiencies and no blockers, then writes `SUBMITTED`, history, audit | Frontend gate is advisory only. Current configuration lacks identity and active category policy, so real production submission stays blocked. |
| Official queue | `SUBMITTED`, unassigned | Official reads unassigned queue and `POST .../claim` | Creates one Official assignment; application remains `SUBMITTED` | Show real server rows/ID and refresh after claim; do not insert local queue entries. |
| Official review | `SUBMITTED` or later allowed status | Assigned Official `PATCH .../status` | Enforces `ALLOWED_TRANSITIONS`, records status history/audit | Offer only transitions allowed by the returned record; show persisted history. |
| Committee assignment | `COMMITTEE_REVIEW` | Assigned Official `POST /applications/{id}/committee` | Creates pending review for configured DUGC/DMPC/DDPC membership | Keep programme-to-committee mapping explicit; no automatic routing from Assistant scope. |
| Committee decision | Review `PENDING` | Matching DUGC member `PATCH /committee-reviews/{id}/decision` | Human `APPROVED`/`REJECTED`; review, application status/history and audit are persisted | Label as human decision, never AI output. |
| Meeting proposal | `PROPOSED` | Matching committee creates proposal, records availability, calculates/selects candidate slot | Persistent proposal and availability; approval remains fail-closed without policy | Explain that candidate slots use member submissions, not an institutional calendar. |
| Meeting approval/confirmation | `PROPOSED` / `APPROVED_PENDING_CONFIRMATIONS` | Configured policy approver approves; members confirm/decline | `CONFIRMED` only when policy threshold is satisfied; conflicts are rechecked | Do not imply notices were sent; provider status remains `NOT_CONFIGURED`. |
| Minutes | Confirmed meeting; versioned draft/review | Add attendance/notes/observations/human decisions, create or opt-in generate draft, revise, submit, comment, sign | Versioned persistent review; finalization requires configured signatory/policy | Surface unresolved agenda/decision conflict indicators; AI does not invent attendance or decisions. |
| Final archive | Finalized minutes | Policy may request indexing | Current implementation reports `INDEXER_NOT_IMPLEMENTED`; no shared archive search | Do not offer searchable finalized minutes or claim an index exists. |

## 5. Module II coverage and integration boundary

The active checkout contains a distinct Module II schema and ingestion/retrieval
code. The schema is not the Module I schema. `module2/database/connection.py`
requires an explicit `DEPARTMENTAI_MODULE2_DATABASE_ENV` and
`.env.module2.<profile>` file; it never falls back to Module I or root
configuration.

| Feature | Evidence in active checkout | Actual exposure/status | Frontend implication |
|---|---|---|---|
| Faculty profiles and education/courses/research areas/memberships/IDs/responsibilities | `module2/database/schema.sql`; `module2/ingestion/faculty_*`; faculty persistence uses inserts/upserts into `m2_*` | Read-only list/detail APIs return allowlisted profile fields; no CRUD API found | SoStudy provides a scoped directory and detail view for authenticated grants only. |
| Publications | `m2_publications`, `m2_faculty_publications`; `publication_persistence.py` deduplicates by DOI or normalized title/type/year and avoids duplicate links | Read-only publication API returns linked records and provenance fields | SoStudy displays actual API fields, source links, bounded pagination, and optional search/year filters; no edit or source-verification controls. |
| Projects and achievements | `m2_projects`, `m2_faculty_projects`, and generic `m2_achievements` columns | Read-only APIs support `projects` and `achievements`; generic categories are not evidence of complete patent/consultancy workflow | SoStudy offers only Projects and Achievements. Patents, consultancy, conferences, and workshops are not separate supported categories. |
| Thesis supervision | `m2_thesis_supervision` and reconciliation/ingestion scripts; source README says supplied files remain source-preserving and are not themselves a normalized import | Persistence/reconciliation exists; source completeness and per-faculty validation remain data tasks | No student-name-sensitive supervision view is exposed in SoStudy. |
| Ingestion and data quality | Python discovery/ingestion/reconciliation/inspection scripts under `module2/ingestion/`; publication dedupe and thesis reconciliation are implemented in code | Scripts/CLI, not authenticated ingestion endpoints or a job/status API | Do not turn scripts into browser actions without a reviewed operation model and permissions. |
| Reporting periods and statistics | Faculty assistant/search includes year-range and count/list query helpers | Statistics API returns only department-scoped publication/project/achievement counts and has no reporting-period parameters | SoStudy reports those exact counts; it does not offer a period filter or compute totals client-side. |
| Administrative chatbot | `module2/chatbot_ui/server.py` with `/api/chat`; uses `faculty_assistant`, `faculty_search`, PostgreSQL, and Gemini path | Standalone prototype; not mounted in main FastAPI and has no authentication dependency | Not safe to connect to the shared website as-is. |
| Exports | `module2/data_export/router.py` and `service.py`; fixed `faculty_profiles` / `publications` datasets and columns, bounded CSV/XLSX/PDF/DOCX output | Requires exact dataset permission and department-scoped query; dataset exports remain separate from configurable reports | SoStudy keeps the secured dataset discovery/download view separate from the report-template catalogue. |
| Configurable draft reporting | `module2/reporting.py` and `module2/report_routes.py`; five fixed faculty/research templates, template version, scope and filter metadata, bounded preview, 2,000-row/5-second query bound, and DOCX/XLSX/PDF renderer checks | Requires `module2.reports.generate`; scope comes only from the authenticated grant. A template's persisted year expression governs filter availability; no report is saved or approved. | The Reporting view previews at most 20 scoped rows and starts a direct download only after successful server generation. Every output is draft/not approved and discloses limitations. |
| Human verification/templates | No official Ministry/institute/accreditation template, report history, or report approval/review endpoint exists | Five templates are configurable draft material only; no institutional sign-off or approval is implied | Required before any generated output can be represented as a formal institutional submission. |

## 6. Current SoStudy frontend and readiness assessment

- The frontend is plain HTML, CSS, and JavaScript modules; navigation is
  controlled by `frontend/app.js`, role menus by
  `frontend/components/layout/sidebar.js`, and API/auth handling by
  `frontend/services/api.js` and `frontend/services/auth.js`.
- The existing Student, Official, and generic DUGC workspaces use the
  authenticated API. `DMPC` and `DDPC` are committee memberships/types, not
  separate authentication roles.
- Student application UI already supports create/edit, draft-only upload,
  compact uploaded-document metadata, persisted readiness analysis, prominent
  application ID/status, and server submission. Student document rows do not
  render Download/Validate/Extract/Classify controls.
- `frontend/utils/application-readiness.js` checks readiness status/freshness,
  application version, verified source provenance, mapped required-document
  matches, completed processing, zero deficiencies, and no blockers. The
  server repeats the substantive checks atomically in the existing submit
  operation.
- Application details render documents and upload before a single
  `AI-Assisted Analysis` panel, with submission controls after it. Status,
  committee, and activity sections currently appear before readiness in the
  page markup, so strict future ordering/compactness requirements should be
  checked during the implementation phase rather than presumed complete.
- Official and committee record lookup reads actual application details,
  documents, saved analysis, status history, and committee reviews. The
  combined analysis is advisory and separately shows legacy eligibility
  freshness as untracked. A legacy Official `/process` action is disabled with
  a conflict response; it does not rerun default-programme analysis.
- The sidebar adds Module II only when the authenticated capability response
  includes a supported feature permission. `frontend/services/api.js` now
  provides the bearer-authenticated Module II client methods.

## 7. Exact blockers and smallest next integration

| Blocker | Evidence | Can frontend alone resolve it? | Smallest safe next step and test |
|---|---|---|---|
| Application categories, required-doc rules, eligibility evaluator, and trusted programme identity are unconfigured | `backend/config/application_policies.json` has no active `application_types`; default identity provider returns `NOT_CONFIGURED` | No | Obtain approved category/rule mapping and trusted identity/provisioning source; add only policy-backed config/provider support, then isolated tests for provenance, `READY`, stale analysis, and direct submit rejection. |
| Current production readiness cannot reach `READY` | Readiness requires verified identity, approved exact policy, verified sources/retrieval, full document matches/processing, and zero blockers; default config meets neither identity nor category mapping | No | Keep the current truthful blocked state. Use only explicit test-profile identity/policy fixtures for a local positive-path acceptance test; do not weaken operational gates. |
| Full post-gate Student → Official browser acceptance has not been demonstrated | `END_TO_END_VERIFICATION_REPORT.md` says the earlier browser submission predates the readiness gate; current checks cover gate implementation but not that new complete browser journey | No | Run synthetic browser acceptance against an isolated test DB after test-only fixtures are explicitly established; prove both blocked and authorized test-only ready/submit/queue states. |
| Formal deficiency request/response is absent | No route/schema for reviewer deficiency requests or Student responses | No | Decide approved policy/state semantics, then add a minimal endpoint/workflow only if institutionally required; test ownership and status transitions before adding UI. |
| Isolated Module II database profile is not yet provisioned for acceptance | The connection resolver requires explicit `.env.module2.<profile>` settings; no real Module II test database/profile was provisioned during Prompt 6 | No | Keep the UI in an honest configuration state. Provision a separate loopback test database and synthetic fixture only before any browser-to-backend data acceptance. |
| No approved Module II account grants are configured by default | Permission policy is fail-closed and keyed to authenticated numeric user IDs with exact department scopes | No | An operator must approve and maintain grants outside the browser; role selection and department edits cannot grant access. |
| Former embedded export UI was removed | The public `/module2/export/ui` route is absent; the active SoStudy export view calls authenticated dataset discovery and download routes | Yes, for UI transport | Export controls are shown only for server-reported dataset permissions. |
| Formal Module II reports/templates/human verification not found | Current export API offers fixed faculty/publication datasets and formats; no template or formal approval workflow exists | No | The frontend labels exports as data downloads, not formal ministry/accreditation reports. Add a report workflow only after its contract and human sign-off policy are approved. |
| Existing plan/documentation has stale statements | `FRONTEND_IMPLEMENTATION_PLAN.md` describes pre-current backend and zero backend editing; older end-to-end sections predate latest readiness gate | No | Keep this map as source-grounded current plan; reconcile older docs in a later documentation-only cleanup after product scope is agreed. |

## 8. Recommended implementation sequence

1. **Resolve policy and identity prerequisites** for operational Student
   readiness; keep fail-closed behavior until authorized configuration exists.
2. **Re-run full isolated Module I acceptance** against the current readiness
   gate, including blocked submission and (only if existing test-only policy
   fixtures allow it) a real persisted test-only submission, Official claim,
   record opening, and upload denial after submission.
3. **Address small verified Student UI ordering gaps** using current API
   responses only; retain one consolidated analysis, no fabricated checklist,
   and a server-authoritative submit.
4. **Keep the Module II security boundary fail-closed.** Maintain the explicit
   database profile and account/department permissions; no browser role or
   department selection can grant access.
5. **Extend Module II only through reviewed APIs.** A bounded, permission-gated
   read-only data-quality inspection API is now available. Auditable review
   actions, supervision, authenticated chatbot retrieval, CRUD, and formal
   reports remain unavailable; do not call ingestion scripts from the browser.
6. **Keep acceptance isolated.** Browser-to-backend data verification needs a
   separately provisioned loopback `departmentai_module2_test` database and
   runtime-only synthetic grants/records; do not use institutional data.

## 9. Baseline checks

These are inspection baselines, not a claim that the full end-to-end workflow
was rerun:

| Check | Result |
|---|---|
| Branch/worktree before inspection | `f-santosh`; substantial tracked and untracked pre-existing changes. Preserved. |
| `node --test` over `frontend/**/*.test.mjs` | **7 passed, 0 failed.** |
| Focused backend/test-profile and Module II CSV-safe baseline | **43 passed, 9 deselected**, 1 existing Starlette/AnyIO deprecation warning. Run with `DEPARTMENTAI_DATABASE_ENV=test`; deselections include tests requiring optional file-format modules. |
| Initial combined unit pass before selecting test profile | **45 passed, 7 failed**: one test-only policy test was run outside its required `test` profile and returned `UNVERIFIED`; six XLSX/DOCX/PDF cases lacked `openpyxl`, `python-docx`, or `reportlab`. After setting the correct profile, the policy test passed; missing export dependencies remain unresolved. |
| `node --check frontend/app.js` and `node --check frontend/services/api.js` | Passed. |
| `python -m compileall -q backend module2` | Passed. |
| Unauthenticated Module II route probe | `GET /module2/export/datasets` returned HTTP **401**, confirming inherited bearer authentication; route source still has no Module-II-specific role/data scope. |
| Browser-to-backend acceptance for the current readiness gate | Not performed in this discovery pass. Prior browser submission evidence predates the gate. |
| Git changes | No application/reference changes made; this document is the only requested discovery deliverable. See final worktree output after report creation. |

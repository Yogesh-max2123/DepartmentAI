# DepartmentAI Role and Permission Matrix

## Evidence boundary

This matrix describes the current backend and frontend. `STUDENT`, `OFFICIAL`, and `DUGC` are authenticated account roles in the API, not powers granted by the frontend selector. The browser sends credentials to `POST /auth/login`; the API checks the provisioned account, issues a short-lived bearer token, and applies record-level checks on protected routes.

Local password authentication and the seeded identities are available only when `DEPARTMENTAI_DATABASE_ENV` explicitly selects `development` or `test`. The institutional profile rejects local password sign-in with HTTP 503 until an approved institutional identity provider and account-provisioning process exist. The development seeder is for synthetic accounts only. Do not use institutional accounts or real student records in the local workflow.

## Prompt 4 meeting and minutes permissions

| Capability | Student | Official | DUGC role with matching membership | Enforcement / status |
|---|---|---|---|---|
| Meeting scheduling frontend | No access | Schedule Meetings workspace | Linked application shows proposal, availability, policy-gated approval, and Confirm/Decline controls | DUGC no longer has a Meeting Governance navigation item; browser controls are backed by application-scoped API checks. |
| Create and revise proposals | No access | Only for applications assigned to the Official and their existing committee assignment | No proposal creation or agenda editing | Backend rejects unlinked proposals and validates the Official assignment and committee membership before linking applications. |
| Submit availability | No access | Cannot submit on behalf of members | Only the caller's availability for the linked proposal and a matching committee membership | Persisted entries are member-owned; no timetable or external calendar is consulted. |
| Select candidate slot | No access | Only for the Official's own persisted proposal | No slot selection | Candidate slots require current explicit member availability and no overlapping persisted meeting. A slot search is not approval. |
| Approve and confirm meeting | No access | Cannot approve or respond on behalf of committee members | Configured policy approver can approve from the linked application; assigned member can confirm/decline there | App-specific routes verify the meeting/application link and committee membership. Default approval policy is empty and fails closed. |
| Add meeting records and draft minutes | No access | No access | Committee members can record attendance, notes, observations, and human decisions after meeting confirmation workflow | AI may summarize notes only with explicit data-sharing opt-in and user request; AI cannot author decisions or attendance. |
| Review and comment on minutes | No access | No access | Matching committee members can submit drafts/revisions and comment on submitted versions | Versioned and audited. Review issues are indicators requiring human resolution. |
| Finalize minutes | No access | No access | Only a configured committee signatory with matching membership | Default signatory policy is empty. Only latest version can be finalized; finalization is not an index operation. |
| Search finalized minutes | No access | No access | Not available | Shared minutes indexer is not implemented. No claim that finalized minutes are searchable. |
| Notices/calendar/timetable | No access | No access | Preview only; no dispatch or external calendar access | Providers are explicitly `NOT_CONFIGURED`; no simulated dispatch is represented as sent. |

Earlier isolated tests covered meeting creation/idempotency,
committee-membership isolation, explicit availability, candidate-slot
selection, policy-gated approval, confirmation, meeting records, manual
minutes revisions/comments/sign-off, final record immutability, and accurate
indexing-disabled status. The current role change has focused unit/UI coverage;
the new Official scheduling and linked-application DUGC workflow has not yet
been browser-verified. No real accounts or records were used.

## Current role matrix

| Capability | Student | Official | DUGC | Enforcement / evidence |
|---|---|---|---|---|
| Sign in and sign out | Local provisioned account | Local provisioned account | Local provisioned account | `POST /auth/login`, `/auth/me`, and `/auth/logout`; opaque bearer token, hashed in the database, 30-minute expiry, server-side revocation |
| Verified programme identity | Not configured by default; response says `NOT_CONFIGURED` and no programme | Not applicable | Not applicable | `/auth/login` and `/auth/me` report the identity state. An injectable trusted provider contract requires matching subject and provenance; no institutional provider is configured, and no programme is inferred from username or Assistant selector |
| Dashboard and application list | Lists applications matching the account's `subject_identifier` | Lists applications assigned to this `user_id` | Lists applications assigned to a committee matching the user's membership; available from both Assigned Applications and Committee Review pages | `GET /applications` is paginated and role-scoped; no fabricated counts or rows |
| Create an application | Yes; server uses the authenticated Student subject identifier | Not permitted | Not permitted | `POST /applications`; client cannot choose the applicant identity |
| Edit/save a draft | Edit owned applications only while status is `DRAFT` | Not permitted | Not permitted | `PATCH /applications/{id}` validates fields, records same-status history, and writes an audit event atomically |
| Submit draft to Official queue | Yes; explicitly submits an owned `DRAFT` | Sees unassigned submitted items in the shared queue; first claim assigns the record | Not permitted | `POST /applications/{id}/submit`, `GET /official/applications/unassigned`, and atomic `POST /applications/{id}/claim`; one Official wins a concurrent claim |
| Read an application | Own records only | Explicitly assigned records only | Records with a review for a committee the account belongs to | `GET /applications/{id}` returns 404 for records outside the caller's scope |
| Documents | Upload only while own application is `DRAFT`; list metadata and download within own application | Read metadata for assigned records | Read metadata for assigned committee records | Upload is Student-only, capped at 10 MiB, and returns 409 after draft state; stored paths are not exposed; downloads are application-scoped. Required-document policy is `NOT SPECIFIED`; upload does not prove completeness |
| Status and history | Read own current status and history; actor name is omitted | Read assigned history and update only server-allowed transitions | Read assigned committee application's history | Server derives staff actor from the account. Status writes are tested only against synthetic local data |
| Committee assignment | Read committee decisions; reviewer identity is omitted | Assign DUGC/DMPC/DDPC after authorization to assigned application, only where target committee has configured members | No assignment permission | `POST /applications/{id}/committee` is Official-only and server-scoped; request rejects extra committee identifiers; assigning Official is recorded in the same transaction |
| Committee decision | Read human decisions; `decided_by` is omitted | Read assigned review metadata | Record a decision only for a matching committee membership and assigned review | Decision actor comes from the authenticated DUGC account, not the request body. Decision, application status/history, and audit event are committed together. |
| Unified policy-aware analysis | Read own combined readiness and saved eligibility advisory | Read combined saved readiness and eligibility for assigned records | Read combined saved readiness and eligibility for assigned records | `GET /applications/{id}/analysis` is read-only and returns readiness plus stored eligibility; the shared UI does not regenerate analysis. Legacy eligibility freshness is `NOT_TRACKED`; it is not a formal determination |
| M.Tech/PhD ordinance advisory | Manually request for an owned `DRAFT` only when verified programme identity and a resolved `TEST_ONLY` application policy are present | No permission | No permission | `/applications/{id}/yogesh-advisory` is disabled by default and sends only application type, title, and description to a loopback reference service. Output is source-validated, persisted as advisory, and never a formal decision. No live reference-service or authenticated-browser run has been verified. |
| Reprocessing | No separate legacy reprocessing action | Disabled; route returns structured HTTP 409 | No reprocessing permission | `POST /applications/{id}/process` does not run legacy default-programme analysis or mutate results |
| Formal deficiency request and applicant response | Not available | No dedicated deficiency-request action | No dedicated deficiency-request action | `MISSING`: current deficiencies are system-analysis results; no formal request/response endpoint or approved response policy is configured |
| AI analysis / Academic Assistant | Advisory analysis and assistant routes are distinct from human decisions | Assistant available; processing action not exposed in the workspace | Assistant available | AI/provider calls are not part of the verified local browser workflow |
| Knowledge-source inventory and search | Authenticated; global search requires an explicit programme and returns candidate citations | Same | Same | `/knowledge/sources` is authenticated. Application-scoped `/knowledge/search` additionally applies the caller's application access, trusted identity, and approved-policy checks; an unresolved identity or policy is rejected. |
| Audit/history | Unavailable | Unavailable | Unavailable | `/applications/{id}/audit-logs` returns 403 until a reviewed visibility policy exists |
| Settings / sign out | View current session and revoke it | Same | Same | No password-management or institutional profile-management feature is claimed |

## Role and committee types

The authenticated application supports three roles: `STUDENT`, `OFFICIAL`, and `DUGC`. `DUGC`, `DMPC`, and `DDPC` are committee types stored in explicit committee memberships and review assignments; they are not separate login roles. The current development seeder creates a synthetic DUGC account with DUGC membership only.

The current generic application workflow supports Student draft creation, owned draft edits, document storage, policy-gated submission, Official claim, status history, Official-controlled committee assignment, and membership-scoped decisions in the local synthetic configuration. The DUGC Committee Review page reuses the paginated, server-filtered `GET /applications` response to display assigned records; selecting a queue item opens existing review details and the combined analysis. Application create/edit and committee assignment bodies reject undeclared fields so clients cannot supply programme identity or committee IDs. The policy registry catalogs approved ordinance files but activates no application types; no trusted institutional identity provider is configured, so the readiness gate remains fail-closed.

## Module II authorization boundary

The existing application roles do not imply Module II rights. The main API
requires both an authenticated bearer session and a separate host-managed
permission grant keyed to the authenticated database user ID. No permission
policy is active by default, so every Module II data operation is denied until
an approved account-to-permission-and-department mapping is configured.
Browser-supplied role names, user IDs, departments, and faculty IDs cannot
grant or widen access.

| Capability | Current access | Required explicit permission | Scope / boundary |
|---|---|---|---|
| List/detail faculty profiles | Disabled unless individually granted | `module2.faculty.read` | Exact grant departments; inaccessible IDs return 404. Phone/email are omitted. |
| Read publications, projects, achievements | Disabled unless individually granted | `module2.research.read` | Records must link to active faculty in an exact grant department; unsupported record types are rejected. |
| Research statistics | Disabled unless individually granted | `module2.research.statistics.read` | Counts are computed from persisted records scoped to grant departments. |
| Data-quality inspection | Disabled unless individually granted | `module2.data_quality.read` | Read-only checks on supported persisted records in exact grant departments; scan is bounded at 5,000 records/category and returns unavailable rather than partial findings. |
| Configurable draft reporting | Disabled unless individually granted | `module2.reports.generate` | Five fixed templates over persisted faculty/research sources; preview and DOCX/XLSX/PDF generation use exact grant scope, bounded queries, and explicit draft/not-approved metadata. No report history or approval workflow exists. |
| Faculty profile export | Disabled unless individually granted | `module2.export.faculty_profiles` | Fixed field allowlist, no phone/email, bounded rows, exact grant departments. |
| Publication export | Disabled unless individually granted | `module2.export.publications` | Fixed field allowlist, linked faculty department scope, bounded rows. |
| Student-sensitive thesis supervision | Denied | Not configured/supported | `GET /module2/supervision` returns 403; student identity/visibility policy is missing. |
| Source ingestion or review | No API; controlled CLI only | No API permission configured | No browser-triggered scripts/jobs. Every CLI connection requires the explicit Module II DB profile. |
| Data-quality review actions | Not available; inspection only | No review/audit permission or persistence model | Findings cannot be marked reviewed, dismissed, corrected, or signed off; the page performs no writes. |
| Faculty chatbot | Denied; not mounted in the main API | `module2.faculty.chat` is intentionally unsupported | The standalone assistant is not bound to the caller's department grant and cannot be used as authorized grounded retrieval. |
| Research/faculty CRUD | Not available | No write permissions configured | Existing ingestion persistence is not a user-facing CRUD service. |
| Module II navigation | Conditional on authenticated capability response | Any supported effective Module II permission | Sidebar entry and internal areas are shown only for permissions returned by `GET /module2/capabilities`; missing grants remain hidden and blocked. |

Supported permission names are checked against the explicit allowlist in
`module2/authorization.py`; unsupported capabilities fail closed. For an
approved deployment, the operator must provision the backend identity first,
then configure its exact account ID, permitted operation names, and department
scope in the protected JSON policy referenced by
`DEPARTMENTAI_MODULE2_PERMISSION_POLICY`. Do not grant the existing roles
globally or infer department membership from a profile URL or user input.

The 2023 UG, Masters, and Doctoral ordinances establish academic committee
bodies DUGC, DMPC, and DDPC for their respective programme areas. They do not
authorize automatic routing of this portal's generic applications. The
Academic Assistant's selector remains informational and never determines
profile identity, eligibility, or application routing. `/auth/me` reports
`NOT_CONFIGURED` for student programme identity until an institutional trusted
source and authorized provisioning process are approved.

## Verification and deployment conclusion

The Prompt 4 local synthetic workflow was exercised end to end in the real frontend against the actual API and loopback-only `departmentai_test` database. Student draft/edit/upload/submit, Official claim and manual assignment, DUGC queue/review/decision, Student-visible status/history/outcome, authorized document download, cross-owner/cross-committee denial, duplicate/invalid-transition rejection, and logout revocation were verified. The API used an exact-origin CORS allowlist for this test; the production defaults were not broadened. Institutional IdP/student-record integration, authorized programme provisioning, automatic routing policy, department-level Official assignment policy, committee membership governance, audit visibility, and institutional database connectivity remain unverified or blocked. Required application categories, eligibility, and required documents remain `NOT SPECIFIED`; formal deficiency request/response remains `MISSING`. Keep real institutional data off this deployment until those controls are approved, independently reviewed, and tested.

The later Prompt 4 retrieval integration adds authenticated `/knowledge/sources`
and `/knowledge/search` routes and requires authentication for `/ask`.
Application-scoped retrieval cannot bypass the access, identity, or policy
checks above. General programme-scoped search and the Assistant's programme
selector provide source scope only; they do not prove a user's programme or
authorize an application decision. The database-backed route test used only
the isolated test profile; no browser Assistant request or production
knowledge search was performed.

# DepartmentAI — API Contract Inventory

This file records the API contract from the current backend implementation. It is intentionally limited to actual route declarations, request models, service responses, and runtime behavior.

## Prompt 4 governance endpoints

All endpoints below are mounted under `/governance` and require a bearer
session. Officials create and schedule proposals only for applications
assigned to their account and an existing committee assignment. DUGC members
submit their own availability and approve/confirm/decline only from a linked
application to which their committee is assigned. The DUGC frontend does not
expose a standalone Meeting Governance page.

| Method and path | Purpose | Important contract / policy |
|---|---|---|
| `GET /governance/configuration` | List committees available for scheduling | Official-only; committees are derived from the caller's assigned applications and active committee memberships. |
| `GET /governance/integrations` | Report provider configuration | Does not send data or claim provider health. Gemini is opt-in and not health-checked; calendar/notifications/timetable are `NOT_CONFIGURED`. |
| `GET /governance/meetings?committee_type=DUGC` | List the caller's proposals | Official-only; returns only proposals organized by the caller and still linked to an application assigned to them. |
| `POST /governance/meetings` | Create a persistent proposal | Official-only; requires at least one linked application assigned to the caller and a matching committee review/membership. Optional `Idempotency-Key` supports safe retries. |
| `POST /governance/availability` | Record the caller's explicit availability | DUGC member-only; requires timezone-aware interval and `AVAILABLE`/`UNAVAILABLE`; does not read a timetable or calendar. |
| `GET /governance/meetings/slots` | Calculate candidate slots | Official-only; requires committee, timezone-aware range, and duration. Results expose missing submissions, conflicts, and source limits; only candidate-flagged slots can be proposed. |
| `GET /governance/meetings/{id}` | Read an owned proposal and its assigned applications | Official-only; organizer and current application assignment are verified. DUGC opens actions through the linked-application endpoint below. |
| `PATCH /governance/meetings/{id}/slot` | Propose a calculated slot | Official organizer only; rejects any slot not marked as a conflict-free candidate at validation time. |
| `PATCH /governance/meetings/{id}/agenda` | Revise a proposal agenda | Official organizer only, before approval; linked application assignment is checked again. |
| `GET /governance/applications/{application_id}/meetings` | Read proposals linked to an assigned application | DUGC-only; linked application, review, and committee membership are checked; returns only actions permitted by current status and configured approver policy. |
| `POST /governance/applications/{application_id}/meetings/{meeting_id}/approve` | Approve a linked meeting proposal | DUGC-only and policy-gated; the application-meeting link and approver identity are checked. |
| `POST /governance/applications/{application_id}/meetings/{meeting_id}/response` | Confirm or decline a linked meeting | DUGC-only; application link and committee membership are checked. Conflicting second responses are rejected. |
| `POST /governance/meetings/{id}/approve` and `/response` | Legacy meeting-level actions | Do not accept DUGC actions without application context; use the application-scoped endpoints above. |
| `GET /governance/meetings/{id}/agenda` and `/notice` | Preview agenda/notice | Persisted data only; notification status remains `NOT_SENT` and provider `NOT_CONFIGURED`. |
| `POST /governance/meetings/{id}/records` | Add note, observation, human decision, or attendance | Record additions are locked after finalized minutes. |
| `GET /governance/meetings/{id}/minutes` | Read records, versions, comments, and human-review issues | Authorized committee membership required. |
| `POST /governance/meetings/{id}/minutes` | Create a manual first draft from persisted meeting inputs | Does not call an AI provider; requires a confirmed meeting, attendance/notes/observations, and a decision or explicit deferral for each agenda item. |
| `POST /governance/meetings/{id}/minutes/generate` | Request AI-assisted draft | Requires confirmed meeting, attendance/notes/observations and a decision or explicit deferral per agenda item; conflict indicators block generation. Gemini is sent data only after explicit approval and user invocation. |
| `PATCH /governance/meetings/{id}/minutes/{version_id}` | Save a human revision as a new version | Finalized versions are immutable; request content is bounded. |
| `POST /governance/minutes/{version_id}/submit`, `/comments`, `/approve` | Review, comment, and sign off | Sign-off requires an approved policy and configured signatory. Only the latest version can be finalized. Indexing reports `INDEXER_NOT_IMPLEMENTED` when requested by policy; it is not represented as successful. |

The `/governance` API was verified with an isolated `departmentai_test`
database-backed meeting/minutes lifecycle test. A real browser at
`http://127.0.0.1:5506/` also created a synthetic meeting proposal, recorded
availability, retrieved candidate slots, proposed a supported slot, and
loaded the notice preview from the API on port 8002. This was partial
synthetic verification, not an institutional workflow. The default
governance registry is empty, so approval/finalization remains blocked. No
reference-project mock calendar, email, or messaging behavior is active.

The current role change was then checked in the live frontend against the
restarted API on loopback with the explicit `test` profile: the DUGC navigation
omits the standalone Meeting Governance item, an assigned application renders
the meeting availability/confirmation section, and the empty meetings response
renders the expected "no proposal linked" state. The live Official proposal,
candidate-slot, DUGC approval, and confirmation sequence remains unverified.

## 1. Backend runtime

- Backend framework: FastAPI
- Application object: `backend.main:app`
- API router: `backend.api.routes.router`
- API prefix: none; routes are mounted directly at the application root
- Default host: not configured in code
- Default port: not configured in code
- Backend startup command: `python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000`
- Backend API base URL: `http://127.0.0.1:8000`
- Frontend API origin: `frontend/config.js` currently sets `http://127.0.0.1:8002`; it is configurable using `globalThis.DEPARTMENTAI_API_BASE_URL`. When config is omitted, the API client defaults to `http://127.0.0.1:8000`. HTTPS frontend pages require an HTTPS API origin.
- OpenAPI endpoint: `GET /openapi.json`
- Docs endpoint: `GET /docs`
- Redirect docs endpoint: `GET /redoc`
- CORS origins: local defaults are `http://127.0.0.1:5500`, `http://localhost:5500`, and `http://127.0.0.1:5501`; optional `CORS_ALLOWED_ORIGINS` replaces the defaults with a comma-separated list of exact HTTP(S) origins.
- CORS methods: `GET`, `POST`, `PATCH`, `OPTIONS`
- CORS headers: `Authorization`, `Content-Type`, `Idempotency-Key`
- CORS credentials: disabled
- Authentication: protected API routes require a bearer session from `POST /auth/login`; local password authentication is restricted to explicitly selected development/test database profiles. Institutional sign-in returns HTTP 503 until an approved identity provider is configured.
- Required headers: content-type is required for JSON request bodies; multipart form-data for document upload
- Error structure: FastAPI returns `{"detail": "..."}` for route-level exceptions; readiness submission conflicts use `{"detail":{"code":"...","message":"..."}}`.
- Application list: `GET /applications?limit=20&offset=0`, filtered by the authenticated account's Student subject, Official assignment, or DUGC committee membership. The DUGC Committee Review page reuses this response; no separate committee queue endpoint was added.
- Document-content download: `GET /applications/{application_id}/documents/{document_id}/download`; application access is checked server-side and stored filesystem paths are not returned.

### Current authentication and role-scoped routes

- `POST /auth/login` accepts `{ "username": "...", "password": "..." }` and returns `access_token`, `token_type`, `expires_in`, and the server-provisioned `user` role/subject. Password login is deliberately unavailable in the institutional profile.
- `GET /auth/me` returns the current server-verified username, role, and subject. `POST /auth/logout` revokes the presented bearer token. The browser persists the access token in `localStorage` and `sessionStorage` so reloads can restore the session after validating the token with `/auth/me`; the password is never persisted. Signing out clears both browser entries and revokes the server-side token, which also expires according to the server session policy.
- Sessions expire after 30 minutes. Only a SHA-256 token digest is stored in PostgreSQL. Password hashes use bcrypt.
- All application/business routes require the `Authorization: Bearer <token>` header. A missing/invalid/expired token returns 401; unavailable auth/database dependencies return a generic 503.
- `GET /applications` returns a bounded page of records visible to that account. Students are filtered by the account subject; Officials by explicit application assignment; DUGC accounts by committee membership and review assignment. The DUGC Committee Review page and Assigned Applications page both use this existing list.
- Student application creation binds the applicant identifier to the authenticated account. Status actors and committee-decision actors are derived from the authenticated username; client-supplied actors are not trusted.
- Official status changes, committee assignment, DUGC decision writes, and document download are server-authorized and scoped. Out-of-scope records return 404; role violations return 403.
- `GET /health/live` checks process liveness. `GET /health/ready` performs a database/schema readiness check; it does not verify AI provider availability.
- Audit reads remain denied with 403 until a visibility policy is approved. Eligibility/deficiency GET routes can write records; eligibility may invoke AI. Do not use them as safe read-only checks.
- This development authentication is not an institutional IdP, and its synthetic seed accounts are not institutional identities. Production remains blocked on IdP, provisioning, policy review, and institutional database access.

### Local integration evidence — 2026-10-25

The browser loaded this checkout from `http://127.0.0.1:5502/` and called a separately started development-profile API on port 8001, explicitly configured for that exact CORS origin. Actual CORS preflights and API requests were observed, not just a preflight-only check. The dev database was `departmentai_dev`; all data was synthetic.

| Method and path | Observed HTTP | Response / effect |
|---|---:|---|
| `GET /health/live` | 200 | `{"status":"ok"}` |
| `GET /health/ready` | 200 | `{"status":"ready"}` with local schema present |
| `GET /openapi.json` | 200 | OpenAPI JSON available |
| `POST /auth/login` | 200 | Browser sign-in succeeded for synthetic Student, Official, and DUGC accounts |
| `GET /applications?limit=5&offset=0` | 200 | Student dashboard displayed the seeded synthetic application |
| `GET /applications?limit=20&offset=0` | 200 | Official and DUGC queues displayed only their assigned synthetic application |
| `GET /applications/2` | 200 | Synthetic application JSON object |
| `GET /applications/2/documents` | 200 | `{"application_id":2,"documents":[]}`; metadata does not expose storage paths |
| `GET /applications/2/status-history` | 200 | `{"application_id":2,"history":[...]}`; Student history omits actor identifier |
| `GET /applications/2/committee-reviews` | 200 | Review JSON; Student response omits decision actor; DUGC view is membership-filtered |
| `GET /applications/2/ordinance-retrieval` | 200 | JSON with empty `results` in the synthetic database |
| `PATCH /applications/2/status` | 200 each | Five legal synthetic transitions through `COMMITTEE_REVIEW`; no AI/process endpoint called |
| `POST /applications/2/committee` | 200 | Synthetic DUGC review assignment |
| `PATCH /committee-reviews/1/decision` | 200 | Synthetic DUGC approval; Student subsequently saw the human decision, not the actor identity |

Automated backend integration tests also cover synthetic upload, metadata, download, upload rejection above 10 MiB, cross-role denial, logout revocation, audit denial, database-unavailable handling, and institutional local-login refusal. These observations do not verify institutional data or production authorization policy.

### Prompt 4 real browser/API verification — 2026-10-27

The checked-in frontend at `http://127.0.0.1:5506/` called the actual API at
`http://127.0.0.1:8002` against the loopback-only `departmentai_test` database.
The API's runtime CORS allowlist contained only the exact frontend origin;
its preflight returned HTTP 200 and an unapproved origin returned HTTP 400.
The synthetic browser journey exercised existing routes for Student draft
creation/editing, document upload/list/download, submission, Official claim,
status changes, committee assignment, committee queue/read/decision, and
Student-visible status/history/outcome. No API endpoint was added in this
verification phase.

Separate authenticated requests confirmed cross-student and cross-committee
application/document/review/download/decision denial (HTTP 404), duplicate
submission conflict (409), invalid status transition (400), unauthorized
Student assignment (403), and authorized document download (200). The
decision's final application status, committee review, status-history entry,
and authenticated committee audit event were verified in the database.
Logout returned 204 and the same token returned 401 from `/auth/me`.
Synthetic records and exact upload files were removed after verification;
unrelated storage contents were preserved. This evidence is limited to local
synthetic accounts and the isolated test database; it is not institutional
integration or production authorization evidence.
This successful submission predates the Prompt 2 readiness gate and does not
demonstrate a currently policy-ready application. With present configuration,
submission is blocked until approved rule provenance is available.

### Earlier runtime verification status (before CORS remediation)

- Source-level route and middleware inspection: verified
- Current API process listening on `127.0.0.1:8000`; `GET /docs` and `GET /openapi.json` returned HTTP 200.
- The configured `.env` database target, `10.219.45.43:5432` (credentials omitted), failed a TCP reachability probe. A local PostgreSQL listener on loopback is a separate endpoint.
- Direct safe `GET /applications/0` timed out after approximately 4.16 seconds with no response body. No database-backed route result was verified.
- No live `/ask`, AI-analysis, document-processing, status-update, or committee-write operation was verified.
- CORS preflight from `http://127.0.0.1:5500` and `http://localhost:5500` returned HTTP 200 with the matching `Access-Control-Allow-Origin` header. Preflight from `http://127.0.0.1:5501` returned HTTP 400.
- Frontend `http://127.0.0.1:5501/` returned HTTP 200; a browser fetch to `/openapi.json` from that origin was blocked by CORS. Port 5500 was already held by a Python listener, but its root returned an empty-response failure. It was left untouched.
- A temporary frontend bound to `[::1]:5500` returned HTTP 200 to direct IPv6 requests, but browser navigation via `localhost:5500` failed loading the role-selector module with `net::ERR_EMPTY_RESPONSE`; the temporary listener was stopped and the existing IPv4 listener remains untouched.
- A loopback-only query found no `STUDENT-TEST` / `Test request` rows on that separate database; this does not establish the configured database state.
- Browser role navigation and responsive-width checks are UI-only and do not verify database-backed integration.

### CORS configuration update — 2026-10-23

- Development origin `http://127.0.0.1:5501` is now explicitly allowed so the current checkout can use its available frontend server when port 5500 is occupied by another checkout.
- `CORS_ALLOWED_ORIGINS`, when set, replaces local defaults. Values are validated as exact HTTP(S) origins; wildcards, credentials, paths, query strings, and fragments are rejected. An empty/invalid configured list fails startup instead of silently broadening access.
- CORS credentials are disabled because the current preview/API has no cookie-based session. Authorization and content-type headers are allowed explicitly.
- Backend CORS tests validate real HTTP responses using FastAPI's test client. This does not add authentication or record-level authorization.
- After restarting the confirmed local Uvicorn process from this checkout, the browser page at `http://127.0.0.1:5501/` successfully completed a preflighted cross-origin `GET /openapi.json` to `http://127.0.0.1:8000`; actual response HTTP 200, JSON, OpenAPI 3.1.0, 18 paths. No application/database endpoint was called.

### Explicit database profiles — 2026-10-24

- `DEPARTMENTAI_DATABASE_ENV` defaults to `institutional`, which reads the existing project `.env`. The application never falls back to local PostgreSQL when that target is unavailable.
- Explicit `development` and `test` values read only `.env.development` and `.env.test`, respectively. Both profiles reject non-loopback hosts and require fixed database names `departmentai_dev` and `departmentai_test`.
- Existing local PostgreSQL databases `departmentai` and `departmentai_m11_test_20261022` were inspected read-only and left untouched. New isolated databases were created and initialized with the core workflow tables plus empty pgvector-backed knowledge tables. No knowledge chunks or application data were copied.
- Core application create/read, status-history, document metadata, empty ordinance retrieval, and committee-review routes are exercised by the isolated backend integration test. This is local test evidence, not institutional database evidence or authenticated role testing. AI analysis and external-provider calls are excluded.

## 2. Shared conventions

All path parameters are integers.

Application IDs are numeric database IDs. Application numbers are generated by the backend as `APP-YYYY-00001`-style values and are not supplied by the client.

Successful JSON responses are objects except for file-download responses and HTTP 204 logout. Errors use FastAPI's `{"detail": "..."}` shape and may return HTTP 400, 401, 403, 404, 413, 422, 500, or 503.

The backend uses PostgreSQL and reads credentials from environment variables. `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, and `DB_PASSWORD` are required by `backend.database.connection.get_connection()`.

## 3. RAG and academic assistance

### GET /knowledge/sources

- Purpose: Return the registered ordinance-source inventory and whether each
  approved source is discovered, fully indexed, or stale/unverified. Index
  completeness is compared with the checked-in processed chunk manifest and
  source ID/version/hash metadata.
- Authentication: required for all roles; use the bearer token from
  `/auth/login`. This endpoint exposes source/index metadata, not applicant
  data or stored document paths.
- Success response:

```json
{
  "status": "AVAILABLE",
  "registry_version": "string",
  "sources": [
    {
      "source_id": "UG_ORDINANCE_2023",
      "source_file": "UG Ordinance.pdf",
      "source_type": "ORDINANCE",
      "programme": "UG",
      "source_version": "BOG-73.13(A)-2023-08-10",
      "approval_status": "APPROVED",
      "status": "INDEXED",
      "chunk_count": 246,
      "verified_chunk_count": 246,
      "expected_chunk_count": 246
    }
  ]
}
```

- Index status values: `DISCOVERED`, `INDEXED`,
  `STALE_OR_UNVERIFIED`, or `PENDING_SOURCE_REVIEW`. `INDEXED` means the
  indexed chunk IDs and provenance match the expected manifest. It does not
  activate application policy.
- Errors: `503` if the policy registry, chunk manifest, or index status cannot
  be checked.

### POST /knowledge/search

- Purpose: Run bounded, provenance-aware ordinance retrieval for an explicit
  programme or an authorized application policy.
- Required headers: `Content-Type: application/json` and authenticated
  `Authorization: ******`.
- Request fields:

```json
{
  "domain": "ORDINANCE",
  "query": "string",
  "programme": "UG",
  "application_id": null,
  "source_ids": null,
  "source_types": ["ORDINANCE"],
  "source_version": null,
  "section_numbers": null,
  "limit": 5
}
```

- `query` is required (1–2,000 characters); `domain` and `source_types`
  support only `ORDINANCE`; `limit` is 1–5. General search requires an
  explicit `programme` (`UG`, `MTECH`, or `PHD`) and returns candidate
  citations only. An application-scoped request must specify
  `application_id`; the caller must have record access, the trusted identity
  provider must verify the programme, and the registry must resolve an
  approved application-type policy. A body-supplied programme/source cannot
  widen that policy.
- Success response contains `status` (`COMPLETED` or `NO_RESULTS`), `domain`,
  `programme`, and `results`. Each result includes `source_id`,
  `source_type`, `source_version`, `source_sha256`, `source_metadata_status`,
  `applicability`, section/page/chunk provenance, and excerpt. If an indexed
  candidate is unverified, `source_*` fields report its indexed values while
  `registered_source_id`, `registered_source_version`,
  `registered_source_sha256`, and `registered_programme` report the registry
  values. Results marked `CANDIDATE` are not application-policy evidence.
  `POLICY_SCOPED` is emitted only for a verified source selected by the
  resolved application policy.
- Errors: `401` when unauthenticated; `404` for inaccessible/missing scoped
  applications; `409` when verified identity or policy is unresolved or the
  requested programme conflicts with the policy; `422` for unsupported or
  invalid filters or absent programme on a general search; `503` when
  registry or retrieval is unavailable. Retrieval errors are not represented
  as `NO_RESULTS`.
- The default registry has no active application-type mappings and the
  default identity provider is `NOT_CONFIGURED`; application-scoped production
  search is therefore intentionally blocked. No production policy is inferred
  from the Assistant selector.

### POST /ask

- Purpose: Answer a question using the ordinance RAG pipeline.
- Request body:

```json
{
  "question": "string",
  "conversation_history": [
    {
      "role": "string",
      "message": "string"
    }
  ],
  "programme": "UG"
}
```

- `conversation_history`: optional; defaults to an empty list.
- `programme`: optional; accepts `UG`, `MTECH`, or `PHD` and defaults to `UG`.
  It selects the ordinance corpus used for this informational assistant request;
  it is not a verified student profile, application category, or committee
  routing instruction. `PGD` is not configured and is rejected with HTTP 422.
- Retrieval is restricted to the selected corpus source file in
  `backend/retrieval/semantic_search.py`; results from other programme corpora
  cannot enter the same answer context.
- The response citations include source ID/type, programme, source version,
  chunk ID, section/page, and relevance where available. These identify
  retrieved source material; the selected programme remains informational.
- Required headers: `Content-Type: application/json`.
- Authentication: required; send the bearer token from `/auth/login` in `Authorization: Bearer <token>`. Local password sign-in is limited to explicit development/test profiles.
- Success response:

```json
{
  "answer": "string",
  "sources": [
    {
      "source": "string",
      "source_id": "string",
      "source_type": "string",
      "programme": "string",
      "source_version": "string",
      "chunk_id": "string",
      "title": "string",
      "page": 6,
      "section": "string",
      "relevance": 0.82,
      "citation": "string"
    }
  ]
}
```

- Error responses: `400` when the question is invalid; `422` for an unsupported
  programme value; `500` for unexpected failures.
- Frontend purpose: Academic Assistant conversation.
- Verification status: Pydantic/TestClient tests verify accepted/rejected
  programme values. Live retrieval against the isolated development database
  returned five results per UG, M.Tech/Masters, and Ph.D. query, each from only
  the selected source. The actual HTTP endpoint and external AI answer
  generation were not exercised live during that source check.

### Local ordinance ingestion

- `python -m backend.ingest_knowledge_base --programme UG|MTECH|PHD` validates
  source PDF/chunks/structure/vector assets and inserts one corpus into the
  explicitly selected `departmentai_dev` database only.
- The command defaults to UG, validates matching chunk/vector IDs, source
  filenames, model name, and 384-dimensional vectors, and refuses duplicate
  chunk ingestion. It does not ingest synthetic cases, minutes, or circulars.
- This ingestion supports the Assistant's read-only ordinance scope only. It
  does not classify applications or change application routing or eligibility.

## 4. Application creation and retrieval

### POST /applications

- Purpose: Create an application in `DRAFT` status.
- `application_type` is free text. An approved category allowlist is not configured.
- The server trims supported text fields and rejects a blank application type. Limits are 100 characters for type, 200 for title, and 10,000 for description.
- Request body:

```json
{
  "application_type": "string",
  "title": "string or null",
  "description": "string or null"
}
```

- The authenticated Student subject identifier is used as `applicant_identifier`; clients cannot choose the applicant identity.
- Undeclared body fields are rejected (`422`), including `programme`, `applicant_identifier`, and committee identifiers. Unrecognized query values do not set profile identity or affect server-derived ownership.
- Required headers: `Content-Type: application/json`.
- Authentication: required; send the bearer token from `/auth/login` in `Authorization: Bearer <token>`. Local password sign-in is limited to explicit development/test profiles.
- Success response:

```json
{
  "id": 1,
  "application_number": "APP-2026-00001",
  "status": "DRAFT",
  "created_at": "timestamp"
}
```

- Error responses: `400` for invalid input, `403` for a non-Student role, `503` when authentication/database dependencies are unavailable, or `500` for an unexpected failure.
- Frontend purpose: Create Application.
- Verification status: synthetic local database integration test passed; no institutional write was made.

### GET /applications

- Purpose: Return the authenticated user's visible application page.
- Query parameters: `limit` (default 20, range 1–100), `offset` (default 0, nonnegative).
- Visibility: Students by exact subject identifier; Officials by explicit application assignment; DUGC by matching committee membership and review.
- Success response:

```json
{
  "items": [
    {
      "id": 1,
      "application_number": "APP-2026-00001",
      "application_type": "string",
      "title": "string or null",
      "description": "string or null",
      "status": "string",
      "submitted_at": "timestamp or null",
      "created_at": "timestamp",
      "updated_at": "timestamp"
    }
  ],
  "limit": 20,
  "offset": 0
}
```

- Verification status: browser-verified HTTP 200 for synthetic Student, Official, and DUGC accounts in the explicitly selected local development profile. No institutional records were queried.

### PATCH /applications/{application_id}

- Purpose: Save edits to an existing Student-owned `DRAFT`.
- Authentication/authorization: requires an authenticated Student and exact ownership of the application. Non-Student roles are denied; records outside the Student's ownership scope return 404.
- The request contains the complete editable draft form. `application_type` is required; `title` and `description` are nullable, and `null` clears those optional values.

```json
{
  "application_type": "Free-text request type",
  "title": null,
  "description": "Revised request details"
}
```

- The backend rejects blank or oversized supported fields and rejects edits once the application leaves `DRAFT`.
- Undeclared body fields are rejected (`422`); a draft update cannot assign or change a programme or committee.
- Side effects: updates the draft, adds a same-status `DRAFT` history entry, and writes an `APPLICATION_UPDATED` audit event in the same database transaction. The actor is derived from the authenticated account.
- Errors: `400` for invalid field content, `403` for a non-Student role, `404` for an application outside the Student's ownership scope, and `409` if the application is no longer a draft.
- Verification status: isolated local database integration test covers successful save, clearing an optional field, role/ownership denial, and non-draft rejection.

### GET /applications/{application_id}/readiness

- Purpose: Return the latest saved readiness analysis and whether it matches the current draft and uploaded file contents. This endpoint is read-only.
- Authentication/authorization: requires application access; Students can read only their own application, and reviewer access follows the existing application scope.
- States: `ANALYSIS_PENDING`, `ANALYSIS_UNAVAILABLE`, `RULES_UNRESOLVED`, `DEFICIENCIES_FOUND`, or `READY`. A missing analysis and any fingerprint mismatch are returned as pending/stale and block submission.
- The version fingerprint covers application fields, document metadata/content SHA-256, the configured policy-registry fingerprint, and trusted programme-identity provenance. A policy or identity change therefore makes a saved result stale.
- Verification status: isolated database integration tests cover no-analysis, unresolved rules, idempotent reads, and stale inputs after an application edit or upload.

### GET /applications/{application_id}/analysis

- Purpose: Return one read-only analysis bundle for Student and authorized reviewer workspaces.
- Authentication/authorization: requires the existing application access check; out-of-scope applications return 404.
- Response includes `schema_version: 1`, `application_id`, `analysis_status`, `freshness_status`, `readiness`, previously stored `eligibility`, `eligibility_freshness: "NOT_TRACKED"`, `advisory: true`, and `formal_decision: false`.
- This route does not run analysis, call an AI provider, or mutate records. Eligibility results are legacy saved advisory output; their freshness is not tracked.
- Verification status: isolated integration tests cover current readiness, owner access, cross-owner denial, and the no-reprocessing path.

### POST /applications/{application_id}/yogesh-advisory

- Purpose: Manually request a source-scoped M.Tech or PhD ordinance advisory for an owned draft.
- Authentication/authorization: Student role and application ownership are required. The application must remain `DRAFT`, its trusted programme identity must be `VERIFIED` as `MTECH` or `PHD`, and its application policy must resolve with `TEST_ONLY` activation scope.
- The request sends only application type, title, and description to the selected loopback reference service. It does not send the applicant identifier or uploaded document contents. The returned programme and source filenames are checked against the configured programme corpus before the advisory is persisted as `YOGESH_RAG_ADVISORY`.
- Results are advisory, not eligibility determinations or formal decisions. A fingerprint over the application type, title, and description marks saved output stale when those fields change; persistence is rejected if the draft changes or leaves `DRAFT` during generation.
- The adapter is disabled by default. It requires the explicit test profile, `DEPARTMENTAI_LOCAL_DEMO=1`, `DEPARTMENTAI_YOGESH_INTEGRATION_ENABLED=true`, a runtime-only shared integration token, and loopback service URLs. Application text may be forwarded by the reference service to a configured model provider; use only approved synthetic text.
- Verification status: adapter and route tests cover access, test-only policy, token handling, programme/source validation, persistence, and fail-closed behavior. In the 2026-10-30 local check, no reference service responded on loopback ports 8003 or 8004; no live RAG call or authenticated browser acceptance was completed.

### POST /applications/{application_id}/readiness/analyze

- Purpose: Validate/classify uploaded draft documents and persist a readiness result for the current inputs. Repeated analysis for an unchanged, non-unavailable result is idempotent.
- Authentication/authorization: Student role and application ownership are required; analysis is permitted only while the application is `DRAFT`.
- The default policy registry catalogs the actual approved UG, Masters, and Doctoral ordinance files and their SHA-256 hashes, but intentionally has no active application-type mappings. No trusted institutional identity provider is configured. Therefore the default deployment does not guess an UG/MTECH/PHD RAG scope, does not interpret empty retrieval as zero requirements, and returns `RULES_UNRESOLVED` with `required_documents`, `document_matches`, `deficiencies`, and `deficiency_count` unset. Document processing failures and unsupported text extraction return `ANALYSIS_UNAVAILABLE`.
- If an exact approved category mapping and verified identity are configured, existing semantic search is invoked for the mapped programme and retrieved source metadata is checked against the configured source files and the cited section numbers declared for each rule. Missing cited sections leave rule retrieval unresolved. The actual document checklist is the explicitly approved mapping, not rules inferred from arbitrary retrieved chunks. The current policy format activates only `ALWAYS` document conditions; eligibility rules remain blocking until an approved evaluator exists.
- Results persist in `ai_analyses` with analysis type `APPLICATION_READINESS`, the input fingerprint, processing results, diagnostics, blockers, and creation time. No AI provider or existing side-effecting eligibility/deficiency GET route is used by this operation.
- Success response includes `readiness_status`, `application_version`, `document_versions`, `document_processing`, `rules` diagnostics/provenance, `blocking_conditions`, `analysis_id`, and `created_at`.
- Errors: `404` for an application outside the Student's ownership scope; `409` if the application is not a draft.
- Verification status: isolated integration tests assert unresolved rules fail closed, empty requirement results are not treated as complete, unreadable synthetic PDFs remain unavailable, and repeated unchanged analysis does not duplicate results.

### POST /applications/{application_id}/submit

- Purpose: Submit a Student-owned draft to the shared Official queue.
- Authentication/authorization: required; Student role and application ownership are verified by the backend.
- Before submission the backend validates supported fields and, inside the same row-locked transaction, requires a current `READY` readiness result with verified rule provenance, a complete document-processing result, zero deficiencies, and no blockers. Missing, stale, unavailable, unresolved, deficient, or structurally incomplete analyses are rejected with HTTP 409 and a structured `detail.code` readiness state.
- No production pathway can currently produce `READY`: the trusted programme and approved required-document policy are not configured. This is intentionally fail-closed; do not seed or manufacture a production readiness result.
- Side effects: atomically changes `DRAFT` to `SUBMITTED`, sets `submitted_at`, creates a status-history record, and writes an audit event.
- Success response includes `application_id`, `old_status`, `new_status`, `submitted_at`, and `history_id`.
- Errors: `400` for invalid application fields, `404` if the application is not owned by the signed-in Student, and `409` for an invalid lifecycle state or any readiness gate failure. Duplicate submissions are rejected.

### GET /official/applications/unassigned

- Purpose: List submitted applications not yet assigned to an Official.
- Authentication/authorization: Official role required. This shared queue is visible to all authenticated Official accounts under the approved shared-queue policy.
- Query parameters: `limit` (default 20, range 1–100), `offset` (default 0, nonnegative).
- Response shape: `{ "items": [application summary...], "limit": 20, "offset": 0 }`.

### POST /applications/{application_id}/claim

- Purpose: Claim one item from the shared Official queue and assign it to the authenticated Official.
- Authentication/authorization: Official role required.
- Side effects: creates the assignment and audit event in one transaction. The application row is locked so only one concurrent claim can succeed.
- Success response includes `application_id`, `official_user_id`, and `assigned_at`.
- Errors: `403` for other roles; `404` if the application does not exist; `409` if it is not `SUBMITTED` or has already been claimed.

### GET /applications/{application_id}

- Purpose: Retrieve one application.
- Path parameters:
  - `application_id`: integer application ID
- Query parameters: none.
- Required headers: `Authorization: Bearer <token>`.
- Authentication: required; send the bearer token from `/auth/login` in `Authorization: Bearer <token>`. Local password sign-in is limited to explicit development/test profiles.
- Success response:

```json
{
  "id": 1,
  "application_number": "APP-2026-00001",
  "applicant_identifier": "string",
  "application_type": "string",
  "title": "string or null",
  "description": "string or null",
  "status": "string",
  "submitted_at": "timestamp or null",
  "created_at": "timestamp",
  "updated_at": "timestamp"
}
```

- Official responses also include `allowed_transitions`; other roles do not receive this field.
- Error responses: `401` for absent/invalid session, `404` for unknown or out-of-scope records, `503` for unavailable authentication/database, or `500` for unexpected failures.
- Frontend purpose: Application Details.
- Verification status: browser-verified HTTP 200 for a synthetic assigned record; role-scope and cross-user denials are covered by integration tests.

### GET /applications/{application_id}/status-history

- Purpose: Retrieve the complete application status history.
- Path parameters:
  - `application_id`: integer application ID
- Student responses omit `changed_by`; authorized staff responses include it.
- Success response:

```json
{
  "application_id": 1,
  "history": [
    {
      "id": 1,
      "old_status": "string or null",
      "new_status": "string",
      "changed_by": "string",
      "reason": "string or null",
      "created_at": "timestamp"
    }
  ]
}
```

- Error responses: `401` for absent/invalid session, `404` for unknown/out-of-scope records, or `503` for unavailable auth/database.
- Frontend purpose: status lifecycle/history presentation.
- Verification status: source verified; no live request performed.

### PATCH /applications/{application_id}/status

- Purpose: Update application status using the backend workflow rules.
- Path parameters:
  - `application_id`: integer application ID
- Request body:

```json
{
  "new_status": "string",
  "reason": "string or null"
}
```

- Only an assigned Official may update status. The server derives `changed_by` from the authenticated username.
- Required headers: `Content-Type: application/json`.
- Authentication: required; send the bearer token from `/auth/login` in `Authorization: Bearer <token>`. Local password sign-in is limited to explicit development/test profiles.
- Success response:

```json
{
  "application_id": 1,
  "old_status": "string",
  "new_status": "string",
  "changed_by": "string",
  "reason": "string or null",
  "history_id": 1
}
```

- Error responses: `400` for invalid status transitions or invalid input; `500` for unexpected failures.
- Frontend purpose: backend-controlled lifecycle actions.
- Verification status: five allowed transitions returned HTTP 200 through the local Official browser workflow; no institutional write was made.

### Supported status transitions

- `DRAFT` → `SUBMITTED`, `ON_HOLD`
- `SUBMITTED` → `DOCUMENT_VALIDATION`, `ON_HOLD`
- `DOCUMENT_VALIDATION` → `PROCESSING`, `DEFICIENCY_FOUND`, `ON_HOLD`
- `PROCESSING` → `UNDER_REVIEW`, `DEFICIENCY_FOUND`, `ON_HOLD`
- `UNDER_REVIEW` → `COMMITTEE_REVIEW`, `DEFICIENCY_FOUND`, `ON_HOLD`
- `DEFICIENCY_FOUND` → `CORRECTION_REQUIRED`, `ON_HOLD`
- `CORRECTION_REQUIRED` → `RESUBMITTED`, `ON_HOLD`
- `RESUBMITTED` → `PROCESSING`, `ON_HOLD`
- `COMMITTEE_REVIEW` → `APPROVED`, `REJECTED`, `ON_HOLD`
- `APPROVED` → `CLOSED`
- `REJECTED` → `CLOSED`
- `CLOSED` → none
- `ON_HOLD` → `DRAFT`, `SUBMITTED`, `DOCUMENT_VALIDATION`, `PROCESSING`, `UNDER_REVIEW`, `COMMITTEE_REVIEW`

## 5. Document management

### POST /applications/{application_id}/documents

- Purpose: Upload an application document.
- Path parameters:
  - `application_id`: integer application ID
- Form fields:
  - `file`: required multipart file
  - `document_type`: optional string
- Required headers: `Content-Type: multipart/form-data`.
- Authentication: required; send the bearer token from `/auth/login` in `Authorization: Bearer <token>`. Local password sign-in is limited to explicit development/test profiles.
- Success response:

```json
{
  "id": 1,
  "application_id": 1,
  "file_name": "document.pdf",
  "document_type": "string or null",
  "file_size": 12345,
  "mime_type": "string or null",
  "upload_status": "UPLOADED",
  "uploaded_at": "timestamp"
}
```

- Supported upload extensions: `.pdf`, `.jpg`, `.jpeg`, `.png`.
- Uploads are Student-only, limited to 10 MiB, and accepted only while the application is `DRAFT`. The service locks the application row while checking its state so a concurrent submission cannot race an upload. Error responses include `400` for empty/invalid file, `403` for a role violation, `404` for unknown/out-of-scope application, `409` when the application is no longer a draft, `413` above the size limit, and `422` for missing multipart fields.
- Frontend purpose: document upload and document listing.
- Verification status: synthetic upload/metadata/download and size/role validation are covered by the isolated integration test.

### GET /applications/{application_id}/documents

- Purpose: List documents for an application.
- Path parameters:
  - `application_id`: integer application ID
- Success response:

```json
{
  "application_id": 1,
  "documents": [
    {
      "id": 1,
      "application_id": 1,
      "file_name": "document.pdf",
      "document_type": "string or null",
      "file_size": 12345,
      "mime_type": "string or null",
      "upload_status": "string",
      "uploaded_at": "timestamp"
    }
  ]
}
```

- Error responses: `404` if the application does not exist; `500` for unexpected failures.
- Frontend purpose: document management list.
- Stored filesystem paths are deliberately omitted from API metadata.
- Verification status: browser-verified HTTP 200 (empty list) and synthetic upload/list metadata verified by automated local integration tests.

### GET /applications/{application_id}/documents/{document_id}/download

- Purpose: Return the uploaded document bytes for an authorized application participant.
- Path parameters: numeric application and document IDs.
- Authentication and scope: bearer session required; the caller must have application access, and the document must belong to that application.
- Success: file response with the stored file MIME type and attachment filename.
- Error responses: `401` for invalid session, `404` for missing/out-of-scope application or document, `503` for unavailable authentication/database, or `500` for unexpected storage failures.
- Verification status: synthetic PDF bytes round-tripped successfully in the isolated automated integration test; browser download was not exercised in this run.

### GET /applications/{application_id}/documents/{document_id}/validate

- Purpose: Validate an uploaded document.
- Path parameters:
  - `application_id`: integer application ID
  - `document_id`: integer document ID
- Required headers: none.
- Authentication: required; send the bearer token from `/auth/login` in `Authorization: Bearer <token>`. Local password sign-in is limited to explicit development/test profiles.
- Success response:

```json
{
  "valid": true,
  "document_id": 1,
  "application_id": 1,
  "file_name": "document.pdf",
  "file_size": 12345,
  "mime_type": "application/pdf",
  "reason": "Document passed basic validation."
}
```

- Failure response:

```json
{
  "valid": false,
  "document_id": 1,
  "reason": "string"
}
```

- Error responses: `400` when the file is invalid; `404` when the document is missing or does not belong to the application; `500` for unexpected failures.
- Frontend purpose: document validation status.
- Verification status: source verified; no live request performed.

### POST /applications/{application_id}/documents/{document_id}/extract

- Purpose: Extract PDF text and store it in the `document_extractions` table.
- Path parameters:
  - `application_id`: integer application ID
  - `document_id`: integer document ID
- Required headers: none.
- Authentication: required; send the bearer token from `/auth/login` in `Authorization: Bearer <token>`. Local password sign-in is limited to explicit development/test profiles.
- Success response:

```json
{
  "extraction_id": 1,
  "document_id": 1,
  "extraction_status": "COMPLETED" or "NO_TEXT",
  "confidence": 0.0,
  "text_length": 0,
  "extracted_text": "string"
}
```

- Supported input: PDF only; non-PDF input returns `400`.
- Extraction first queries by both document and application ID, so a
  cross-application ID is rejected before the PDF is opened. Limits are
  10 MiB, 100 pages, and 1,000,000 extracted text characters. PDF image OCR
  is not performed; scanned/image-only files can return `NO_TEXT`.
- Error responses: `400` for invalid file, size/page/text limits, or
  unsupported MIME type; `404` when the document is missing or belongs to
  another application; `500` for unexpected failures.
- Frontend purpose: extracted document text.
- Verification status: source verified; no live request performed.

### POST /applications/{application_id}/documents/{document_id}/classify

- Purpose: Validate the stored file and infer a supported document category from readable PDF text. The classifier does not use a client-supplied document type as evidence.
- Path parameters:
  - `application_id`: integer application ID
  - `document_id`: integer document ID
- Required headers: `Authorization: Bearer <access_token>`.
- Authentication: required; send the bearer token from `/auth/login` in `Authorization: Bearer <token>`. Local password sign-in is limited to explicit development/test profiles.
- Success response:

```json
{
  "document_id": 1,
  "application_id": 1,
  "file_name": "document.pdf",
  "document_type": "MARKSHEET",
  "valid": true,
  "classification_status": "CLASSIFIED",
  "confidence": 0.9,
  "matched_categories": ["MARKSHEET"],
  "classification_method": "pdf_text",
  "reason": "Category inferred from readable PDF text. This is a heuristic classification, not an eligibility decision."
}
```

- Allowed backend values: `MARKSHEET`, `IDENTITY_PROOF`, `APPLICATION_FORM`, `CERTIFICATE`, `OTHER`.
- Multiple category matches or no readable category yield `OTHER` and `NEEDS_REVIEW`; they are not treated as verified documents.
- PDF files are checked for a readable structure and their embedded text is matched against deterministic category indicators. JPEG/PNG files are checked for a valid image structure, but remain `NEEDS_REVIEW` because OCR is not configured. Scanned PDFs with no embedded text also require review. The confidence value is a heuristic indicator, not a statistically calibrated probability.
- `400` for unsupported, corrupt, empty, encrypted, or extension/MIME-mismatched files; `404` when the document is missing or belongs to another application; `500` for unexpected failures.
- Frontend purpose: document-type classification state.
- The result is a document-type hint only. It does not establish that the document satisfies a policy, eligibility, or application requirement; those requirements remain `NOT SPECIFIED` unless authoritative rules are configured.

## 6. Ordinance retrieval, eligibility, and deficiencies

### GET /applications/{application_id}/ordinance-retrieval

- Purpose: Search official ordinance content using an approved application-type mapping and verified programme identity.
- Path parameters:
  - `application_id`: integer application ID
- Required headers: none.
- Authentication: required; send the bearer token from `/auth/login` in `Authorization: Bearer <token>`. Local password sign-in is limited to explicit development/test profiles.
- Success response:

```json
{
  "application_id": 1,
  "query": "string",
  "results": [
    {
      "id": 1,
      "chunk_text": "string",
      "score": 0.0,
      "metadata": {}
    }
  ]
}
```

- Error responses: `403` for a role violation; `404` for a missing/out-of-scope application; `409` when trusted programme identity or an approved application-type mapping is unresolved; `500` for unexpected failures.
- Frontend purpose: learned ordinance context and citations.
- Verification status: source verified; no live request performed.

### GET /applications/{application_id}/eligibility

- Purpose: Evaluate application requirements using document evidence and Gemini.
- Path parameters:
  - `application_id`: integer application ID
- Required headers: none.
- Authentication: required; send the bearer token from `/auth/login` in `Authorization: Bearer <token>`. Local password sign-in is limited to explicit development/test profiles.
- Success response:

```json
{
  "application_id": 1,
  "requirements_analyzed": 0,
  "results": []
}
```

- Each result object contains:

```json
{
  "eligibility_result_id": 1,
  "requirement_id": 1,
  "result": "MET" or "NOT_MET" or "UNCLEAR",
  "evidence": "string",
  "confidence": 0.0,
  "source_chunk_id": 1
}
```

- Error responses: `400` when the application is invalid; `404` if the application does not exist; `500` for unexpected failures.
- Frontend purpose: requirements and eligibility analysis.
- Side effects: this GET deletes existing eligibility results, may invoke Gemini, inserts replacement results, and commits. It is not a safe read-only endpoint.
- Verification status: source verified; no live request performed. The staff lookup UI intentionally does not invoke it automatically.

### GET /applications/{application_id}/eligibility/results

- Purpose: Read previously stored advisory eligibility results without running analysis, calling an AI provider, or writing to the database.
- Path parameters:
  - `application_id`: integer application ID
- Authentication and scope: bearer session required; the caller must have authorized access to the application as its Student owner or assigned Official/committee reviewer.
- Success response:

```json
{
  "application_id": 1,
  "analysis_status": "NOT_GENERATED" or "PARTIAL" or "AVAILABLE",
  "requirements_analyzed": 0,
  "results_count": 0,
  "results": [],
  "advisory": true
}
```

- Each result contains the requirement ID/description, stored result, evidence, optional confidence, and creation timestamp. Requirements without a stored result are not fabricated.
- Error responses: `401` for an invalid session, `403` for a role violation, `404` for a missing/out-of-scope application, and `500` for unexpected failures.
- Frontend purpose: display saved reviewer results without invoking the side-effecting eligibility-analysis GET route.
- Side effects: none.

### GET /applications/{application_id}/deficiencies

- Purpose: Convert `NOT_MET` and `UNCLEAR` eligibility results into deficiency records.
- Path parameters:
  - `application_id`: integer application ID
- Required headers: none.
- Authentication: required; send the bearer token from `/auth/login` in `Authorization: Bearer <token>`. Local password sign-in is limited to explicit development/test profiles.
- Success response:

```json
{
  "application_id": 1,
  "deficiencies_detected": 0,
  "deficiencies": []
}
```

- Each deficiency object contains:

```json
{
  "deficiency_id": 1,
  "requirement_id": 1,
  "eligibility_result_id": 1,
  "status": "NOT_MET" or "UNCLEAR",
  "severity": "HIGH" or "MEDIUM",
  "description": "string",
  "evidence": "string",
  "source_chunk_id": 1
}
```

- Error responses: `400` when the application is invalid; `404` if the application does not exist; `500` for unexpected failures.
- Frontend purpose: AI-identified deficiencies.
- Side effects: this GET deletes and recreates deficiency records, then commits. It is not a safe read-only endpoint.
- Verification status: source verified; no live request performed. The staff lookup UI intentionally does not invoke it automatically.

## 7. AI-assisted application analysis and processing

### POST /applications/{application_id}/ai-analysis

- Purpose: Generate a multi-source AI-assisted application analysis.
- Path parameters:
  - `application_id`: integer application ID
- Required headers: none.
- Authentication: required; send the bearer token from `/auth/login` in `Authorization: Bearer <token>`. Local password sign-in is limited to explicit development/test profiles.
- Success response:

```json
{
  "analysis_id": 1,
  "application_id": 1,
  "analysis_type": "APPLICATION_ANALYSIS",
  "documents_analyzed": 0,
  "requirements_analyzed": 0,
  "eligibility_results": 0,
  "deficiencies": 0,
  "ordinance_results": 0,
  "analysis": "string",
  "model": "gemini-3.5-flash-lite",
  "created_at": "timestamp"
}
```

- Error responses: `404` when the application does not exist; `500` for unexpected failures.
- Frontend purpose: AI-Assisted Analysis and AI Recommendation display.
- Verification status: source verified; no live request performed.

### POST /applications/{application_id}/process

- Purpose: Legacy Official reprocessing route; currently disabled until policy-aware processing is approved.
- Path parameters:
  - `application_id`: integer application ID
- Required headers: none.
- Authorization: Official-only and limited to an application assigned to that Official.
- Authentication: required; send the bearer token from `/auth/login` in `Authorization: Bearer <token>`. Local password sign-in is limited to explicit development/test profiles.
- Authorization: Official role and access to an assigned application are required.
- Current behavior: returns HTTP 409 with a structured error code. It does not invoke the legacy default-programme pipeline or write processing, eligibility, deficiency, or AI-analysis records. Officials must read the saved combined analysis instead.
- Verification status: isolated integration test confirms the structured 409 response for an assigned Official. The previous pipeline is not exposed as the active Official workflow.

## 8. Committee and human decisions

### POST /applications/{application_id}/committee

- Purpose: Assign an application to a committee.
- Path parameters:
  - `application_id`: integer application ID
- Request body:

```json
{
  "committee_type": "DUGC"
}
```

- Allowed values: `DUGC`, `DMPC`, `DDPC`.
- Only an Official authorized for the application may assign a committee. The assignment is rejected if the selected committee has no configured membership. Unknown request fields such as `committee_id` are rejected; the request cannot assign by an arbitrary committee record identifier.
- Assignment remains manual. The supplied UG/Masters/Doctoral ordinances establish DUGC/DMPC/DDPC academic scope but do not authorize automatic routing of this portal's generic application types.
- Required headers: `Content-Type: application/json`.
- Authentication: required; send the bearer token from `/auth/login` in `Authorization: Bearer <token>`. Local password sign-in is limited to explicit development/test profiles.
- Success response:

```json
{
  "id": 1,
  "application_id": 1,
  "committee_type": "DUGC",
  "assigned_at": "timestamp",
  "review_status": "PENDING"
}
```

- Error responses: `400` for invalid committee, no configured committee members, or invalid application status; `404` if the application does not exist; `422` for undeclared request fields; `500` for unexpected failures.
- Frontend purpose: committee assignment workflow when the application reaches `COMMITTEE_REVIEW`.
- Verification status: source verified; no live request performed.

### GET /applications/{application_id}/committee-reviews

- Purpose: Retrieve committee reviews for an application.
- Path parameters:
  - `application_id`: integer application ID
- Required headers: none.
- Authentication: required; send the bearer token from `/auth/login` in `Authorization: Bearer <token>`. Local password sign-in is limited to explicit development/test profiles.
- Success response:

```json
{
  "application_id": 1,
  "reviews": [
    {
      "id": 1,
      "application_id": 1,
      "committee_type": "DUGC",
      "assigned_at": "timestamp",
      "review_status": "PENDING",
      "decision": "string or null",
      "decision_reason": "string or null",
      "decided_by": "string or null (omitted from Student response)",
      "decided_at": "timestamp or null"
    }
  ]
}
```

- Error responses: `404` if the application does not exist; `500` for unexpected failures.
- Frontend purpose: committee review record list and decision history. The queue page calls existing `GET /applications`; selecting an item loads the application and its scoped review records.
- Verification status: source and isolated HTTP/database integration verified; committee page markup verified by frontend tests. The attempted browser journey was incomplete because the temporary browser origin was not CORS-allowed.

### PATCH /committee-reviews/{review_id}/decision

- Purpose: Record an authorized committee member’s final `APPROVED` or `REJECTED` decision.
- Path parameters:
  - `review_id`: integer committee review ID
- Request body:

```json
{
  "decision": "APPROVED",
  "decision_reason": "string"
}
```

- Allowed values: `APPROVED` and `REJECTED`.
- Only a DUGC account with matching committee membership may decide an assigned review. The server derives `decided_by`; the client does not submit it. Student responses omit this actor field. The decision, application status transition, status-history row, and audit event commit atomically.
- Required headers: `Content-Type: application/json`.
- Authentication: required; send the bearer token from `/auth/login` in `Authorization: Bearer <token>`. Local password sign-in is limited to explicit development/test profiles.
- Success response:

```json
{
  "review": {
    "id": 1,
    "application_id": 1,
    "committee_type": "DUGC",
    "assigned_at": "timestamp",
    "review_status": "COMPLETED",
    "decision": "APPROVED",
    "decision_reason": "string",
    "decided_by": "string",
    "decided_at": "timestamp"
  },
  "application_status": "APPROVED",
  "status_history_id": 1
}
```

- Error responses: `400` for invalid decision, missing reason, or invalid review state; `403` for a role violation; `404` for an unassigned review; `503` for unavailable dependencies; `500` for unexpected failures.
- Frontend purpose: human/committee decision display and final decision authority.
- Verification status: isolated HTTP/database integration test verifies an authorized synthetic decision, status history, audit actor/details, and cross-member denial. No live institutional request or completed Prompt 3 browser decision was performed.

## 9. Audit logs

### GET /applications/{application_id}/audit-logs

- Purpose: Retrieve audit records for an application.
- Path parameters:
  - `application_id`: integer application ID
- Required headers: none.
- Authentication: required; send the bearer token from `/auth/login` in `Authorization: Bearer <token>`. Local password sign-in is limited to explicit development/test profiles.
- Response: HTTP 403 with `{"detail":"Audit visibility policy is not configured."}`. No audit-record success schema is currently exposed.
- Frontend purpose: audit history only after student/staff visibility is authorized. Current Student, Official, and DUGC views withhold this route.
- Security note: the route is authenticated but deliberately returns 403 until a reviewed audit visibility/redaction policy is approved.
- Verification status: isolated integration test confirmed 403 for an assigned Official; no raw audit payload is returned.

## 10. Frontend architecture and workflow presentation

- The current checkout contains the plain HTML/CSS/JavaScript app at `frontend/index.html` and `frontend/app.js`.
- API calls are centralized in `frontend/services/api.js`; browser navigation is handled in `frontend/app.js`.
- The backend CORS configuration explicitly allows the three documented local development origins. Other origins require an exact `CORS_ALLOWED_ORIGINS` configuration; this does not provide authentication or authorization.
- `GET /applications` returns a bounded, authenticated list filtered by Student subject, Official application assignment, or DUGC committee membership/review.
- The Student view reads scoped status history and human decisions; actor identities are omitted from Student responses. The activity panel remains unavailable because the audit route returns 403 pending a visibility policy.
- Official status changes and committee assignments, and DUGC decisions, are exposed only when the backend supplies the assigned record and allowed workflow state. Backend tests and the synthetic development browser workflow verified these operations.
- Committee decision fields are presented as human/committee decisions; AI output remains separately labeled advisory content. Reviewer identifiers are not rendered.
- M14 Settings displays only the current page-session profile and an existing sign-out action. It does not claim backend profile, password, or security management.

## 11. M11–M17 current verification summary

| Area | Status |
|---|---|
| Route declarations and request/response contracts | Verified from source and OpenAPI availability |
| Frontend M11–M13 API helper contracts | Automated mock-server tests passed |
| Live local application/status/committee reads | Browser-verified HTTP 200 against synthetic `departmentai_dev` records |
| M14 Settings browser display and sign-out | Settings renders session identity; automated backend tests verify logout revocation |
| M15 responsive/keyboard spot checks | Widths 376/768/1281 had no horizontal overflow; Tab focus outline was visible |
| Full responsive/accessibility matrix | Screen-reader and full assistive-technology verification remain |
| M16 local synthetic role workflows | Browser-verified for Student, Official, and DUGC; institutional database/IdP remain blocked |
| M09/M10 current-session regressions | Frontend API contract and semantic-search tests passed; live Gemini/API paths not rerun |
| Backend files edited for local authenticated workflows | Yes; see `END_TO_END_VERIFICATION_REPORT.md` and `git status` |
| Institutional database | TCP reachability check failed; no institutional query/write was made |

## 12. Authentication and health endpoints

Local password authentication is enabled only when `DEPARTMENTAI_DATABASE_ENV` is explicitly `development` or `test`. In the institutional profile, login fails closed with HTTP 503 until an approved identity provider is configured. All application/business routes require the bearer token; health and OpenAPI/docs routes are public.

### POST /auth/login

- Request:

```json
{
  "username": "string",
  "password": "string"
}
```

- Username length: 1–128 characters; password length: 1–256 characters at the transport layer. Stored local passwords must be 12–72 UTF-8 bytes.
- Success (HTTP 200):

```json
{
  "access_token": "opaque bearer token",
  "token_type": "bearer",
  "expires_in": 1800,
  "user": {
    "username": "synthetic.student",
    "role": "STUDENT",
    "subject_identifier": "synthetic subject",
    "programme_identity_status": "NOT_CONFIGURED",
    "verified_programme": null
  }
}
```

- Role values are `STUDENT`, `OFFICIAL`, or `DUGC`. The API stores a SHA-256 digest of the token and a bcrypt password hash. The raw token is returned only to the client and expires after 30 minutes.
- For Student accounts, `programme_identity_status` is `NOT_CONFIGURED` and `verified_programme` is `null` because no trusted profile source/provisioning integration exists. Non-Student responses return null for these fields. This is not a programme verification claim.
- Errors: 401 for an invalid username/password; 503 when local authentication is disabled or the auth database is unavailable.
- Verification: browser HTTP 200 for synthetic local accounts in all three roles; no institutional login was attempted.

### GET /auth/me

- Requires the bearer token.
- Returns the current server-verified username, role, and subject identifier plus the same programme identity fields as login; Student accounts currently receive `NOT_CONFIGURED` and `null`. The Assistant search scope is not a profile attribute. 401 for invalid/expired/revoked token; 503 if local auth/database is unavailable.

### POST /auth/logout

- Requires the bearer token; revokes the current session.
- Success: HTTP 204 with no response body. Subsequent use of the same token returns 401.
- Verification: token revocation is covered by the local integration test.

### GET /health/live and GET /health/ready

- `/health/live` returns HTTP 200 `{"status":"ok"}` when the API process is responding.
- `/health/ready` checks PostgreSQL connectivity and required application/auth tables; returns HTTP 200 `{"status":"ready"}` or generic HTTP 503 `{"detail":"Database readiness check failed."}`. It does not check AI-provider readiness.
- Verification: local development browser/API check returned HTTP 200 for both; simulated DB-unavailable tests returned HTTP 503 without exposing driver errors.

## 13. Historical M00 findings

- Historical pre-authentication state only: the router previously had no auth or application-list route. This no longer describes the current local development/test implementation.
- Earlier notes about missing frontend files and failed backend startup describe a prior checkout and are superseded by the current runtime evidence above.

## 14. Module II authenticated data API

Module II routes use the existing bearer session from `POST /auth/login` and
an independent per-user Module II permission policy. The authenticated
account's database user ID is the grant key; browser-supplied role, user ID,
faculty ID, or department is never treated as proof of permission. A grant
must contain one or more exact department names, and every faculty/research
query applies that department scope in SQL. With no
`DEPARTMENTAI_MODULE2_PERMISSION_POLICY`, no account has Module II access.
Missing grants return HTTP 403, an invalid configured policy returns HTTP
503, and missing/invalid sessions retain the normal HTTP 401 behavior.

The policy is a host-managed JSON file with this shape; these example values
are placeholders, not approved real permissions:

```json
{
  "users": {
    "123": {
      "permissions": [
        "module2.faculty.read",
        "module2.research.read",
        "module2.research.statistics.read",
        "module2.data_quality.read",
        "module2.reports.generate",
        "module2.export.faculty_profiles",
        "module2.export.publications"
      ],
      "departments": ["Example Department"]
    }
  }
}
```

Only the permission names supported by `module2/authorization.py` are
accepted. There is no role-wide default. Policy approval and mapping of
authenticated account IDs to departments must be provided before deployment;
no current Student/Official/DUGC role alone grants Module II privileges.
Student-supervision access and the standalone faculty-chat permission are not
supported by the grant schema.

### Module II database profile

Module II never inherits the Module I database selector. Set
`DEPARTMENTAI_MODULE2_DATABASE_ENV` to `development`, `test`, or `production`
and provide only the corresponding `.env.module2.<profile>` file:

| Profile | Required target |
|---|---|
| `test` | Loopback host and database `departmentai_module2_test` |
| `development` | Loopback host and database `departmentai_module2_dev` |
| `production` | An explicit production profile file, host, port, database, user, and password |

No profile selection, missing profile file, invalid target, or incomplete
credentials returns a configuration error; no `.env`, Module I, or institutional
fallback is attempted. The committed
[test profile template](../.env.module2.test.example) is intentionally
incomplete. Provision the dedicated database and a private local
`.env.module2.test` separately; no schema migration or database creation is
performed by connection resolution. Module II Python dependencies are pinned
in the root `requirements.txt`; the three export renderers are exercised by
tests only after those dependencies are installed.

#### Acceptance environment check — 2026-10-28 (follow-up)

The private `.env.module2.test` file and runtime permission policy remain
absent. Selecting the Module II test profile fails closed and does not fall
back to Module I. A read-only catalog query through the verified
`departmentai_test` profile confirmed that `departmentai_module2_test` does
not exist; the connected role has neither `CREATEDB` nor superuser privileges.
No authorized Module II database-administrator credential or provisioning
mechanism was available. No database, account, grant, schema, or record was
created, and `departmentai_test` was not modified for Module II.

The frontend and API are currently serving on loopback, and the authenticated
synthetic M.Tech workflow was exercised against the real API and
`departmentai_test`. That workflow is not Module II acceptance. A synthetic
account's `/module2/capabilities` request returned 403 because no Module II
grant exists; no Module II database connection or report was exercised live.

The Module II security/export/report suites use synthetic authenticated
principals, temporary permission-policy files, and mocked database cursors.
They completed with 88 passed, 0 failed, and 0 skipped; the renderer tests
opened synthetic CSV, XLSX, DOCX, and PDF output and checked its sample
content. Those files are unit-test artifacts, not live report downloads.
Frontend Node tests completed with 9 passed, 0 failed, and 0 skipped. The
standalone assistant and editing/approval actions were not enabled or granted;
their denial/unavailability was covered only by contract or unit tests, not
live browser acceptance.

The Module I test connection used by the local demo resolves to
`departmentai_test` on `127.0.0.1/32`. PostgreSQL's effective
`listen_addresses` is `*`, with IPv4 and IPv6 wildcard listeners on port 5432.
Windows Firewall has an enabled Public-profile inbound TCP/5432 allow rule
scoped to remote IPv4 address `10.219.45.224`; the rule's local address,
program, service, and interface filters are `Any`. This establishes a
host-level allow for that address, not successful remote or Internet
reachability. Routing, the remote host's identity, upstream/NAT controls, and
effective network policy were not verified; no firewall or network settings
were changed.

### Available read-only routes

All paths below are mounted on the main FastAPI application and require a
bearer session. Data routes also require the indicated exact permission.
`GET /module2/capabilities` requires an existing Module II grant and returns
only that authenticated account's effective permissions and department scope.
It does not connect to a database; `database_profile_configured` reports only
whether the selected isolated profile is complete, not whether the database
is reachable. Accounts without a grant receive HTTP 403, invalid policy
configuration receives HTTP 503, and missing/invalid sessions receive HTTP
401.

| Method and path | Permission | Scope and response |
|---|---|---|
| `GET /module2/capabilities` | Authenticated account with a Module II grant | `{"permissions":[...],"departments":[...],"database_profile_configured":true\|false}`. The permissions and departments are derived only from the server policy entry for the authenticated account ID. |
| `GET /module2/faculty?department=&query=&limit=50&offset=0` | `module2.faculty.read` | `{"items":[...],"limit":n,"offset":n}`. Active profiles only; `department` can narrow but never widen the grant. Page size is 1–100, offset is bounded. Contact fields (`phone`, `email`) are not returned. |
| `GET /module2/faculty/{faculty_id}` | `module2.faculty.read` | One active in-scope profile; out-of-scope and absent records both return HTTP 404. |
| `GET /module2/research/records/{publications,projects,achievements}?department=&query=&year_from=&year_to=&limit=50&offset=0` | `module2.research.read` | `{"record_type":"...","items":[...],"limit":n,"offset":n}`. Only schema-backed linked records; query values are parameterized, page size is at most 100, years are 1900–2100 and ranges are checked. Sensitive raw metadata and project financial amounts are omitted. |
| `GET /module2/research/statistics?department=` | `module2.research.statistics.read` | Scoped persisted publication, project, and achievement counts; query/database failures return HTTP 503 rather than zero counts. |
| `GET /module2/data-quality/issues?category=&limit=50&offset=0` | `module2.data_quality.read` | Read-only checks on active faculty and in-scope linked publications, projects, and achievements. Department scope comes only from the authenticated grant. The optional category is one of `faculty`, `publications`, `projects`, or `achievements`; page size is at most 100. At most 5,000 persisted records per selected category are scanned; larger categories return HTTP 503 instead of partial findings. |
| `GET /module2/reports/templates` | `module2.reports.generate` | Static allowlist of five versioned configurable draft templates, supported filters, output formats, and renderer availability. |
| `POST /module2/reports/preview` | `module2.reports.generate` | Body: `{"template_id":"publications_summary","year_from":2020,"year_to":2025}` (year filters are optional and only supported where advertised). Returns draft metadata, scoped counts, limitations, and at most 20 allowlisted preview rows. |
| `POST /module2/reports/generate` | `module2.reports.generate` | Same template/filter body plus `"format":"docx|xlsx|pdf"`; returns a direct, no-store attachment only after the server builds it successfully. Output is bounded to 2,000 rows, with query timeout 5 seconds; an oversized result returns HTTP 413 rather than a partial report. Unavailable renderers return HTTP 503. |
| `GET /module2/export/datasets` | At least one `module2.export.*` dataset permission | Static dataset allowlist and columns for only the caller's permitted datasets; no catalog/table discovery. |
| `GET /module2/export/{faculty_profiles,publications}/download?format=csv\|xlsx\|pdf\|docx&limit=1..10000&columns=...` | `module2.export.faculty_profiles` or `module2.export.publications` | Bounded department-scoped attachment; optional columns must be an allowlisted, non-empty subset. Default limit is 1,000. Unknown datasets return 404, missing dataset grants 403, and malformed format/columns/limits 422. |

Faculty export columns are `id`, `full_name`, `designation`, `department`,
`qualification`, `area_of_interest`, `profile_url`, `source_url`,
`source_name`, and `verification_status`. Publication export columns are
`title`, `publication_type`, `journal_or_conference`, `publisher`,
`publication_date`, `publication_year`, `doi`, `authors`, `source_url`,
`department`, and `faculty_name`. Phone, email, student-linked supervision,
and unrestricted `raw_metadata` are not exportable. Export SQL uses only
fixed dataset/column fragments and binds department and limit values.

The separate draft-report catalogue supports a faculty directory, publication
summary, project summary, achievement summary, and department research
overview. Report SQL and output columns are fixed server-side; the authenticated
grant supplies the department scope, and the request cannot supply SQL, column
names, departments, or arbitrary filters. Supported year filters are limited
to templates with a persisted year expression. DOCX, XLSX, and PDF are
advertised only when their renderer is available. Preview returns at most 20
rows, and generation returns a direct attachment without persisting a file or
report history. Each preview and file labels itself `DRAFT_NOT_OFFICIAL` and
discloses its template version, generation timestamp, scope, filters, counts,
and limitations. No official Ministry/accreditation templates, approval
workflow, or institutional sign-off have been implemented.

`GET /module2/data-quality/issues` is read-only and evaluates nonblank values
for schema `NOT NULL` text fields (`m2_faculties.full_name`, `department`,
`profile_url`, `source_name`; `m2_publications.title` and
`publication_type`; `m2_projects.title`; `m2_achievements.category`), reversed
project/achievement date ranges, and publication date/year mismatches.
Potential duplicates are heuristic suggestions only: faculty name plus
department; publication title plus publication year (falling back to the
stored publication date's year); project title plus funding agency; and
achievement title plus category and year (falling back to the event date's
year). Incomplete matching keys are not used. Findings include persisted
record IDs and available evidence; no record is rewritten or deleted. A
separate review/audit persistence model and permission do not exist, so
review, dismissal, correction, and sign-off actions are not offered.
The response contains `summary.record_counts`, `records_scanned`,
`total_issues`, `objective_issues`, and `potential_duplicate_findings`, plus
a paginated `issues` array. Each issue includes category, record ID/label,
field, issue type, objective-versus-heuristic classification, explanation,
persisted evidence, and a source URL when present. Candidate duplicate evidence
includes at most 100 record IDs and 20 persisted-value previews, with explicit
counts/truncation flags, to keep responses bounded.

Other Module II writes, source ingestion, and reconciliation-review APIs are
not available; controlled ingestion/reconciliation remain CLI operations and
are never invoked from a browser. `GET /module2/supervision` deliberately
returns 403 because student-sensitive field-level policy is unconfigured.
The former unauthenticated `/module2/export/ui` was removed.

The administrative assistant remains unavailable. The temporary standalone
chatbot is not mounted in the main app; its `module2.faculty.chat` permission
is intentionally unsupported. Its current retrieval/aggregate paths are not
bound to the authenticated user's department grant and do not provide the
required safe retrieval/audit contract, so the SoStudy frontend does not call
them or send retrieved content to a model.

The SoStudy Module II page uses the authenticated capability, faculty,
research, statistics, and permitted export routes above. Navigation and
features are shown only for effective server-reported permissions. It never
sends a browser-supplied department filter; department scopes shown in the UI
are informational, and the backend remains authoritative. The UI offers only
publications, projects, and achievements as research categories. Statistics
have no reporting-period filters. Data-quality review requires the separate
`module2.data_quality.read` permission; supervision and the faculty chatbot
remain unavailable. A database profile is not reported as
connected merely because its configuration is complete.

### Export dependency and verification boundary

`openpyxl==3.1.5`, `python-docx==1.1.2`, and `reportlab==4.2.5` are declared
alongside `psycopg==3.3.6` in the root Python dependency manifest. CSV, XLSX,
DOCX, and PDF renderer tests exercise generated content/signatures, and
isolated HTTP tests exercise authorized CSV export and denied/error paths.
No live database export, institutional report, or production permission was
verified. The static dataset names are not approved ministry/accreditation
reports.

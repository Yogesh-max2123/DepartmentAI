# DepartmentAI — API Contract Inventory

This file records the API contract from the current backend implementation. It is intentionally limited to actual route declarations, request models, service responses, and runtime behavior.

## 1. Backend runtime

- Backend framework: FastAPI
- Application object: `backend.main:app`
- API router: `backend.api.routes.router`
- API prefix: none; routes are mounted directly at the application root
- Default host: not configured in code
- Default port: not configured in code
- Backend startup command: `python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000`
- Backend API base URL: `http://127.0.0.1:8000`
- Frontend API origin: configurable using `globalThis.DEPARTMENTAI_API_BASE_URL` in `frontend/config.js`; an empty value uses the local development URL. HTTPS frontend pages require an HTTPS API origin.
- OpenAPI endpoint: `GET /openapi.json`
- Docs endpoint: `GET /docs`
- Redirect docs endpoint: `GET /redoc`
- CORS origins: local defaults are `http://127.0.0.1:5500`, `http://localhost:5500`, and `http://127.0.0.1:5501`; optional `CORS_ALLOWED_ORIGINS` replaces the defaults with a comma-separated list of exact HTTP(S) origins.
- CORS methods: `GET`, `POST`, `PATCH`, `OPTIONS`
- CORS headers: `Authorization`, `Content-Type`
- CORS credentials: disabled
- Authentication: protected API routes require a bearer session from `POST /auth/login`; local password authentication is restricted to explicitly selected development/test database profiles. Institutional sign-in returns HTTP 503 until an approved identity provider is configured.
- Required headers: content-type is required for JSON request bodies; multipart form-data for document upload
- Error structure: FastAPI returns `{"detail": "..."}` for route-level exceptions
- Application list: `GET /applications?limit=20&offset=0`, filtered by the authenticated account's Student subject, Official assignment, or DUGC committee membership.
- Document-content download: `GET /applications/{application_id}/documents/{document_id}/download`; application access is checked server-side and stored filesystem paths are not returned.

### Current authentication and role-scoped routes

- `POST /auth/login` accepts `{ "username": "...", "password": "..." }` and returns `access_token`, `token_type`, `expires_in`, and the server-provisioned `user` role/subject. Password login is deliberately unavailable in the institutional profile.
- `GET /auth/me` returns the current server-verified username, role, and subject. `POST /auth/logout` revokes the presented bearer token. The browser stores the access token in tab-scoped `sessionStorage` so reloads in the same tab can restore the session after validating the token with `/auth/me`; the password is never persisted. Closing the tab clears this storage, and the server-side session still expires or can be revoked.
- Sessions expire after 30 minutes. Only a SHA-256 token digest is stored in PostgreSQL. Password hashes use bcrypt.
- All application/business routes require the `Authorization: Bearer <token>` header. A missing/invalid/expired token returns 401; unavailable auth/database dependencies return a generic 503.
- `GET /applications` returns a bounded page of records visible to that account. Students are filtered by the account subject; Officials by explicit application assignment; DUGC accounts by committee membership and review assignment.
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
  ]
}
```

- `conversation_history`: optional; defaults to an empty list.
- Required headers: `Content-Type: application/json`.
- Authentication: required; send the bearer token from `/auth/login` in `Authorization: Bearer <token>`. Local password sign-in is limited to explicit development/test profiles.
- Success response:

```json
{
  "answer": "string",
  "sources": [
    {
      "source": "string",
      "title": "string",
      "page": "number",
      "section": "string",
      "relevance": "number",
      "citation": "string"
    }
  ]
}
```

- Error responses: `400` when the question is invalid; `500` for unexpected failures.
- Frontend purpose: Academic Assistant conversation.
- Verification status: route and request/response models verified from source; no live API request performed.

## 4. Application creation and retrieval

### POST /applications

- Purpose: Create an application in `DRAFT` status.
- Request body:

```json
{
  "application_type": "string",
  "title": "string or null",
  "description": "string or null"
}
```

- The authenticated Student subject identifier is used as `applicant_identifier`; clients cannot choose the applicant identity.
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

### POST /applications/{application_id}/submit

- Purpose: Submit a Student-owned draft to the shared Official queue.
- Authentication/authorization: required; Student role and application ownership are verified by the backend.
- Side effects: atomically changes `DRAFT` to `SUBMITTED`, sets `submitted_at`, creates a status-history record, and writes an audit event.
- Success response includes `application_id`, `old_status`, `new_status`, `submitted_at`, and `history_id`.
- Errors: `404` if the application is not owned by the signed-in Student; `409` if the current state cannot be submitted.

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
- Uploads are Student-only and limited to 10 MiB. Error responses include `400` for empty/invalid file, `403` for a role violation, `404` for unknown/out-of-scope application, `413` above the size limit, and `422` for missing multipart fields.
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
- Error responses: `400` for invalid file or unsupported mime type; `404` when the document is missing or belongs to another application; `500` for unexpected failures.
- Frontend purpose: extracted document text.
- Verification status: source verified; no live request performed.

### POST /applications/{application_id}/documents/{document_id}/classify

- Purpose: Normalize the document type using the server’s allowed type list.
- Path parameters:
  - `application_id`: integer application ID
  - `document_id`: integer document ID
- Required headers: none.
- Authentication: required; send the bearer token from `/auth/login` in `Authorization: Bearer <token>`. Local password sign-in is limited to explicit development/test profiles.
- Success response:

```json
{
  "document_id": 1,
  "application_id": 1,
  "file_name": "document.pdf",
  "document_type": "MARKSHEET"
}
```

- Allowed backend values: `MARKSHEET`, `IDENTITY_PROOF`, `APPLICATION_FORM`, `CERTIFICATE`, `OTHER`.
- Error responses: `404` when the document is missing or belongs to another application; `500` for unexpected failures.
- Frontend purpose: document-type classification state.
- Verification status: source verified; no live request performed.

## 6. Ordinance retrieval, eligibility, and deficiencies

### GET /applications/{application_id}/ordinance-retrieval

- Purpose: Search official ordinance content using the application type, title, and description.
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

- Error responses: `400` when the application lacks enough information; `404` if the application does not exist; `500` for unexpected failures.
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

- Purpose: Run the complete processing pipeline in order: requirements, eligibility, deficiencies, and AI analysis.
- Path parameters:
  - `application_id`: integer application ID
- Required headers: none.
- Authentication: required; send the bearer token from `/auth/login` in `Authorization: Bearer <token>`. Local password sign-in is limited to explicit development/test profiles.
- Success response:

```json
{
  "application_id": 1,
  "requirements": {
    "application_id": 1,
    "requirements": []
  },
  "eligibility": {
    "application_id": 1,
    "requirements_analyzed": 0,
    "results": []
  },
  "deficiencies": {
    "application_id": 1,
    "deficiencies_detected": 0,
    "deficiencies": []
  },
  "ai_analysis": {
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
}
```

- Error responses: `404` when the application does not exist; `500` for unexpected failures.
- Frontend purpose: batch processing entry point.
- Verification status: source verified; no live request performed.

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

- Error responses: `400` for invalid committee or invalid application status; `404` if the application does not exist; `500` for unexpected failures.
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
- Frontend purpose: committee decision history.
- Verification status: source verified; no live request performed.

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
- Only a DUGC account with matching committee membership may decide an assigned review. The server derives `decided_by`; the client does not submit it. Student responses omit this actor field.
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
- Verification status: source verified; no live request performed.

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
    "subject_identifier": "synthetic subject"
  }
}
```

- Role values are `STUDENT`, `OFFICIAL`, or `DUGC`. The API stores a SHA-256 digest of the token and a bcrypt password hash. The raw token is returned only to the client and expires after 30 minutes.
- Errors: 401 for an invalid username/password; 503 when local authentication is disabled or the auth database is unavailable.
- Verification: browser HTTP 200 for synthetic local accounts in all three roles; no institutional login was attempted.

### GET /auth/me

- Requires the bearer token.
- Returns the current server-verified username, role, and subject identifier; 401 for invalid/expired/revoked token; 503 if local auth/database is unavailable.

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

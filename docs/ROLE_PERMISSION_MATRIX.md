# DepartmentAI Role and Permission Matrix

## Evidence boundary

This matrix describes the current backend and frontend. `STUDENT`, `OFFICIAL`, and `DUGC` are authenticated account roles in the API, not powers granted by the frontend selector. The browser sends credentials to `POST /auth/login`; the API checks the provisioned account, issues a short-lived bearer token, and applies record-level checks on protected routes.

Local password authentication and the seeded identities are available only when `DEPARTMENTAI_DATABASE_ENV` explicitly selects `development` or `test`. The institutional profile rejects local password sign-in with HTTP 503 until an approved institutional identity provider and account-provisioning process exist. The development seeder is for synthetic accounts only. Do not use institutional accounts or real student records in the local workflow.

## Current role matrix

| Capability | Student | Official | DUGC | Enforcement / evidence |
|---|---|---|---|---|
| Sign in and sign out | Local provisioned account | Local provisioned account | Local provisioned account | `POST /auth/login`, `/auth/me`, and `/auth/logout`; opaque bearer token, hashed in the database, 30-minute expiry, server-side revocation |
| Dashboard and application list | Lists applications matching the account's `subject_identifier` | Lists applications assigned to this `user_id` | Lists applications assigned to a committee matching the user's membership | `GET /applications` is paginated and role-scoped; no fabricated counts or rows |
| Create an application | Yes; server uses the authenticated Student subject identifier | Not permitted | Not permitted | `POST /applications`; client cannot choose the applicant identity |
| Submit draft to Official queue | Yes; explicitly submits an owned `DRAFT` | Sees unassigned submitted items in the shared queue; first claim assigns the record | Not permitted | `POST /applications/{id}/submit`, `GET /official/applications/unassigned`, and atomic `POST /applications/{id}/claim`; one Official wins a concurrent claim |
| Read an application | Own records only | Explicitly assigned records only | Records with a review for a committee the account belongs to | `GET /applications/{id}` returns 404 for records outside the caller's scope |
| Documents | Upload, list metadata, and download within own application | Read metadata for assigned records | Read metadata for assigned committee records | Upload is Student-only, capped at 10 MiB; stored paths are not exposed; downloads are application-scoped |
| Status and history | Read own current status and history; actor name is omitted | Read assigned history and update only server-allowed transitions | Read assigned committee application's history | Server derives staff actor from the account. Status writes are tested only against synthetic local data |
| Committee assignment | Read committee decisions; reviewer identity is omitted | Assign DUGC/DMPC/DDPC after authorization to assigned application | No assignment permission | `POST /applications/{id}/committee` is Official-only and server-scoped |
| Committee decision | Read human decisions; `decided_by` is omitted | Read assigned review metadata | Record a decision only for a matching committee membership and assigned review | Decision actor comes from the authenticated DUGC account, not the request body |
| Eligibility / deficiency analysis | Explicit user-triggered operations remain available | Not exposed | Not exposed | These GET routes may write/regenerate records and eligibility may invoke AI; never trigger as ordinary review reads |
| AI analysis / Academic Assistant | Advisory analysis and assistant routes are distinct from human decisions | Assistant available; processing action not exposed in the workspace | Assistant available | AI/provider calls are not part of the verified local browser workflow |
| Audit/history | Unavailable | Unavailable | Unavailable | `/applications/{id}/audit-logs` returns 403 until a reviewed visibility policy exists |
| Settings / sign out | View current session and revoke it | Same | Same | No password-management or institutional profile-management feature is claimed |

## Role and committee types

The authenticated application supports three roles: `STUDENT`, `OFFICIAL`, and `DUGC`. `DUGC`, `DMPC`, and `DDPC` are committee types stored in explicit committee memberships and review assignments; they are not separate login roles. The current development seeder creates a synthetic DUGC account with DUGC membership only.

## Verification and deployment conclusion

The local synthetic workflow has automated database-backed tests and was exercised in a browser against a separately started development API/database. This verifies the implemented development path, not institutional identity or production policy. Institutional IdP integration, trusted account provisioning, department-level Official assignment policy, committee membership governance, audit visibility, and institutional database connectivity remain unverified or blocked. Keep real institutional data off this deployment until those controls are approved, independently reviewed, and tested.

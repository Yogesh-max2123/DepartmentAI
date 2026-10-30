# Module 1 Programme Coverage Audit

**Checked:** 2026-10-27  
**Scope:** Existing Module 1 application workflows and the UG, M.Tech/Masters,
and Ph.D. ordinance references available in the local project and review
checkouts.

## Prompt 4 scheduling/minutes coverage

| Programme scope | Committee mapping in the active app | Shared workflow capability | Remaining policy/provider boundary |
|---|---|---|---|
| M.Tech / Masters | DMPC; programme retrieval scope `MTECH` | The authenticated governance API supports committee-scoped persistent meeting proposals, explicit availability, candidate slots, agenda/application links, records, versioned minutes, comments, and policy-gated sign-off. | No identity-derived programme routing or automatic application assignment; approvals and minutes signatory require approved registry policy. |
| Ph.D. | DDPC; programme retrieval scope `PHD` | Same shared workflow and permissions; no separate unauthenticated project server is mounted. | No institutional timetable/calendar, notifications, OCR, approved minutes archive, or finalized-minutes indexer. |
| UG | DUGC; programme retrieval scope `UG` | Same shared workflow can be used by a DUGC membership. | Existing generic application readiness and policy gates remain fail-closed; meeting scheduling does not resolve application readiness. |

Minutes draft retrieval includes ordinance citations only as candidate
references; these do not substitute for committee decisions. Conflict checks
surface unresolved agenda items and possible opposing terms in recorded
decisions but require a human to resolve them. The Gemini adapter is opt-in
and never authors attendance or decisions. No M.Tech/Ph.D. reference
synthetic cases or minutes were imported.

The focused governance database test and a partial browser-to-test-API journey
passed using synthetic accounts and the isolated `departmentai_test`
database. This does not change the separate Module 1 identity/readiness
policy blockers or verify institutional scheduling providers.

## Summary

The Academic Assistant offers source-isolated ordinance retrieval for UG,
M.Tech/Masters, and Ph.D. The authenticated application still has no trusted
student-programme profile or institutional provisioning source. Student
`/auth/login` and `/auth/me` responses explicitly report
`programme_identity_status: NOT_CONFIGURED` with no verified programme.
Client-supplied programme and committee identifiers are not accepted as
profile or routing authority.

The 2023 UG, Masters, and Doctoral ordinances establish DUGC, DMPC, and DDPC
academic committee scopes, respectively. They do not establish that this
portal's generic application types must route automatically to those bodies.
The shared Student → Official → committee workflow remains generic; explicit
committee selection remains an Official action after authorization. Automatic
programme routing and policy-specific application behavior are not enabled.

## Generic application lifecycle status

| Capability | Status | Evidence / boundary |
|---|---|---|
| Student draft create, list, retrieve, and edit | `VERIFIED` for the local synthetic configuration | Authenticated Student subject is server-bound; only owned `DRAFT` records can be edited. Backend integration tests cover create, read/list, save, optional-field clearing, role denial, and cross-student denial. Prompt 4 also created and edited a draft in the real browser against the isolated test API/database. |
| Student document upload/list/download | `VERIFIED` for the local synthetic configuration | Prompt 4 exercised browser upload/list and an authorized HTTP download against the actual API; isolated integration tests also cover application-scoped access, duplicate display names, unsafe filenames, and download integrity. Stored paths are not returned to the frontend. |
| Student submission and duplicate prevention | `FAIL-CLOSED; successful submission requires approved readiness policy` | Prompt 4 exercised submission before the readiness gate was added. Current isolated integration tests verify that missing, unresolved, stale, and unavailable analyses are rejected; only a structurally complete current `READY` result can pass. No production `READY` result can be produced with current configuration. |
| Readiness freshness and atomic submission gate | `VERIFIED FAIL-CLOSED` in isolated integration tests | Readiness persists against a fingerprint of application fields and uploaded file contents; edits/uploads make earlier results stale. Submission rechecks the fingerprint and result while holding the application row lock. Synthetic tests cover pending, `RULES_UNRESOLVED`, `ANALYSIS_UNAVAILABLE`, idempotent retries, and stale inputs. |
| Official verification/assignment stage | `VERIFIED` for the local shared-queue workflow | Submitted applications enter the shared Official queue and one authorized Official claims the record. This local workflow is not an institutional routing policy. |
| Official committee assignment | `VERIFIED` for the local synthetic configuration | Assignment remains Official-only for assigned applications in `COMMITTEE_REVIEW`; target must have configured committee membership. The assigning Official is audited transactionally. |
| Authorized committee review and decision | `VERIFIED` for the local synthetic configuration | Prompt 4 loaded the membership-scoped queue, reviewed the assigned application, recorded a DUGC decision, and confirmed the applicant-visible outcome/history. A DMPC-only reviewer was denied the DUGC record and decision; database integration also verifies the transaction. |
| Committee review queue UI | `VERIFIED` for rendering, browser workflow, and backend access control | The existing paginated, server-filtered application list is displayed on the DUGC Committee Review page. Prompt 4 loaded the queue from the actual API and opened the assigned application in the real browser; cross-committee list and record access were denied. |
| Atomic committee decision audit | `VERIFIED` for isolated test configuration and browser integration | The existing committee decision route commits the human decision, application status transition, status history, and audit event in one database transaction. Prompt 4 confirmed the final `APPROVED` state and authenticated audit actor in the isolated database. |
| Application fields | `VERIFIED` for generic supported-field validation | Free-text type is required (1–100 characters); optional title and description are limited to 200 and 10,000 characters. These limits do not establish an approved category list. |
| Application categories, eligibility, and required documents | `NOT SPECIFIED` | No approved category allowlist, programme eligibility mapping, or mandatory-document checklist is configured. Submissions are not marked policy-verified or document-complete. |
| Formal deficiency request and applicant response | `MISSING` | Existing deficiency analysis is advisory/system-generated; there is no formal reviewer request or applicant response endpoint. |
| Trusted student programme identity | `BLOCKED` | Authentication has server-provisioned role and subject only. There is no programme profile, institutional IdP/student-record source, or authorized provisioning workflow. `/auth/me` states `NOT_CONFIGURED`; no account receives a fabricated programme. |
| Application-programme-to-committee body scope | `VERIFIED` as ordinance body scope only | UG Ordinance §1.6 defines DUGC and responsibilities for UG students; 2023 Masters Ordinance §1.3 defines DMPC for Masters programmes; 2023 Doctoral Ordinance §1.3 defines DDPC for Ph.D. students. These references do not establish portal routing policy. |
| Automatic application routing UG→DUGC, Masters→DMPC, Ph.D.→DDPC | `BLOCKED` | No approved category, trusted programme identity, or explicit policy for automatic routing of this portal's generic applications. The Official-controlled assignment stage remains active. |

## Prompt 2 readiness workflow — fail-closed boundary

The Student details page now presents documents before one consolidated
AI-Assisted Analysis panel and places the only Submit control after readiness.
The panel reports document processing, source-scope diagnostics, freshness,
deficiencies when supported by a rule source, and blockers. The browser enables
Submit only for an explicitly current `READY` result with verified provenance,
a complete required-document/match list, completed processing, zero
deficiencies, and no blockers. The backend independently enforces the same
conditions in the existing submission transaction.

The current application has no trusted programme identity
(`programme_identity_status: NOT_CONFIGURED`) and the application type is free
text. Although ordinance corpora exist for UG, M.Tech/Masters, and Ph.D., no
approved mapping connects these generic application types to a programme
corpus or an authoritative required-document checklist. Readiness therefore
does not call RAG with an assumed UG default, treat an empty retrieval as zero
requirements, or invent deficiencies. It persists `RULES_UNRESOLVED`,
leaves required documents and deficiency count unknown, and blocks submission.
Corrupt or unsupported documents are reported as `ANALYSIS_UNAVAILABLE`.

Automated isolated-database integration tests exercised the pending and
unresolved states, no-false-zero output, same-input idempotency, stale
fingerprints after edits/uploads, unavailable document processing, and direct
submission rejection. Prompt 3 adds a test-only identity and mapping, real
source retrieval, and an actual readiness analysis; this fixture does not
enable production policy. No real institutional browser workflow was run.

## Prompt 3 identity and policy integration — 2026-10-28

The default registry at `backend/config/application_policies.json` records
these source files as approved by Board of Governors Resolution 73.13(A),
2023-08-10. Their configured SHA-256 hashes are verified before registry use:

| Source ID | Programme corpus | Source version | SHA-256 |
|---|---|---|---|
| `UG_ORDINANCE_2023` | `UG Ordinance.pdf` | `BOG-73.13(A)-2023-08-10` | `742f71b5ce832a7b4adf0372b7caf678eef52766fa239c1075ae334079adc90c` |
| `MTECH_ORDINANCE_2023` | `Ordinances for Masters Programme 2023.pdf` | `BOG-73.13(A)-2023-08-10` | `0c2923a9fd59a44e22f40adb2c0be7b7dbad6c2d94ceb06fcbbac7267ce5d561` |
| `PHD_ORDINANCE_2023` | `Ordinances_for_Doctoral_Programm2023.pdf` | `BOG-73.13(A)-2023-08-10` | `0409f185df07e740cb4ae334bee0086d199947093103c08761f71573d7e2a754` |

`application_types` is intentionally empty: no portal application-category
mapping, required-document checklist, or eligibility evaluator is active.
Approved ordinances establish source authority, not this portal's category
mapping. Student programme identity still resolves to `NOT_CONFIGURED`; the
provider interface rejects mismatched subjects, incomplete provenance, and
conflicting/unavailable identities. No institutional identity provider or
profile provisioning process was available or invented.

The policy-aware resolver requires both an exact approved application-type
mapping and a verified programme before using the existing programme-scoped
semantic search. Retrieved source-file metadata is checked against the
registry and every mapped rule's declared section number must appear in
retrieval evidence. Retrieval does not automatically extract/approve policy
rules: each required document, citation, evidence statement, and source
section must be present in the approved mapping. Until those inputs exist,
readiness is unresolved and submission remains blocked. The fingerprint
includes registry and identity provenance so changes stale a saved analysis.

Student and reviewer applications now use read-only
`GET /applications/{id}/analysis` for readiness plus previously saved
eligibility results. The combined response explicitly marks legacy eligibility
freshness as `NOT_TRACKED` and is not a formal decision. Student and Official
workspaces present one analysis panel with compact policy-source evidence.
Official `POST /applications/{id}/process` is disabled and returns structured
HTTP 409 rather than invoking legacy default-UG processing.

Isolated integration tests use a test-database-only synthetic identity and
policy mapping, then exercise the real semantic-search route using an actual
UG ordinance chunk and prepared embedding. They verify the combined analysis
response, cross-owner denial, and disabled Official processing. This fixture
is test-only and does not establish a production mapping or successful
institutional workflow.

## Committee review UI follow-up

The DUGC Committee Review page now reuses the existing membership-filtered
`GET /applications` list rather than requiring users to know an application ID
before opening a review. Selecting a row opens the existing authorized record
view, including documents, status history, and assigned committee reviews. The
existing final-decision form remains limited to pending/in-review assignments
and submits to the established decision route. The decision, status-history
row, and audit event now share one database transaction.

No separate Official verification stage or committee routing endpoint was
introduced. Official claims and manual assignment remain unchanged. Formal
deficiency request/response remains `MISSING`; system-generated analysis does
not constitute a policy-authorized request to an applicant. The Prompt 3
browser attempt was `PARTIAL` because its origin was not allowlisted. Prompt 4
superseded that interim result with real browser-to-test-API workflow
verification using an explicitly restricted exact-origin CORS configuration.

## Prompt 4 real workflow verification — 2026-10-27

The checked-in frontend at port 5506 called the actual API at port 8002 with
`DEPARTMENTAI_DATABASE_ENV=test` and the loopback-only `departmentai_test`
database. The API allowed only `http://127.0.0.1:5506`; a preflight from that
origin returned 200 and an unapproved origin returned 400. The synthetic
journey completed Student draft/edit/upload/submit, Official claim/status
transitions/manual DUGC assignment, DUGC queue/review/decision, and Student
status/history/outcome display. Read-only database verification confirmed the
committee review, final `APPROVED` status, status history, and a single audit
event with the authenticated committee actor.

Authenticated HTTP checks confirmed cross-student and cross-committee
application/document/review/download/decision denial, duplicate submission
409, invalid transition 400, unauthorized Student assignment 403, authorized
document retrieval 200, and logout revocation (`/auth/me` returned 401 after
the 204 logout response). All synthetic accounts/application data and the
exact upload fixtures were removed afterward; an unrelated file in the shared
storage directory was preserved. Backend tests (31), guardrails (13), the
five focused frontend test files, and frontend JavaScript syntax checks
passed. No AI provider or institutional service was used.

## Coverage matrix

| Capability | UG | M.Tech/Masters | Ph.D. | PG Diploma |
|---|---|---|---|---|
| Ordinance source | Available | Available | Available | Not specified / no source |
| Academic Assistant retrieval | Source-filtered; local development retrieval verified | Source-filtered; local development retrieval verified | Source-filtered; local development retrieval verified | Unsupported; API rejects `PGD` |
| Trusted programme on student profile | `BLOCKED` | `BLOCKED` | `BLOCKED` | Unsupported / not established |
| Approved programme-specific application categories/forms | Generic free-text application only; no verified category taxonomy | Missing; reference form IDs do not establish the main app's approved categories | Missing; reference form IDs do not establish the main app's approved categories | Not specified |
| Programme-specific eligibility and required-document rules | Generic workflow only; no verified programme rule mapping | Missing / policy not established | Missing / policy not established | Not specified |
| Ordinance committee scope | `VERIFIED`: UG Ordinance §1.6 identifies DUGC for UG academic matters | `VERIFIED`: Masters Ordinance §1.3 identifies DMPC for Masters academic matters | `VERIFIED`: Doctoral Ordinance §1.3 identifies DDPC for doctoral academic matters | Not specified |
| Automatic application routing to that committee | `BLOCKED`: no profile or portal routing policy; Official assignment remains | `BLOCKED`: no profile or portal routing policy; Official assignment remains | `BLOCKED`: no profile or portal routing policy; Official assignment remains | Not specified |
| Full programme-specific browser/API lifecycle verification | Generic local workflow has prior synthetic verification; not programme-aware | Not implemented / not verified | Not implemented / not verified | Not specified |

## Ordinance evidence and integration

- The M.Tech/Masters corpus is the 2023 Masters ordinance PDF and matching
  processed text, structure, chunk, and embedding assets from the supplied
  reference checkout. Its processed chunk and vector files each contain 105
  matching entries. The reference build history's 139-entry statement does
  not match those supplied assets; the integrated data was validated from the
  actual files.
- The Ph.D. corpus is the 2023 Doctoral ordinance PDF and matching processed
  assets; the supplied chunk and vector files each contain 143 matching
  entries.
- Both processed corpora use
  `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` with
  384-dimensional vectors, matching the local project's configured embedding
  contract. The source PDFs identify Board of Governors approval at its 73rd
  meeting on August 10, 2023, Resolution 73.13(A).
- Source filtering is applied to semantic retrieval, and the `POST /ask`
  request accepts `UG`, `MTECH`, or `PHD` (default `UG`). The UI explicitly
  describes the choice as an informational source scope, not a verified
  programme or application decision. `PGD` is not configured.
- All three corpora were loaded into the loopback-only `departmentai_dev`
  database. Read-only counts at implementation time were UG 246, M.Tech 105,
  and Ph.D. 143 chunks. Live semantic retrieval returned five results per
  selected programme, each exclusively from its selected ordinance source.
- Supplied synthetic committee minutes/cases/circulars were not copied or
  ingested. The review references are knowledge/scheduling prototypes, not
  authoritative application-workflow specifications.
- Committee body evidence: `documents/ug/processed/ug_ordinance_text.txt`
  §1.6 (Department Undergraduate Committee, p. 11); the 2023 Masters ordinance
  processed text §1.3 (Department Masters' Programme Committee, p. 11); and
  the 2023 Doctoral ordinance processed text §1.3 (Department Doctoral
  Programme Committee, p. 10). These ordinance sections establish committee
  composition and broad academic responsibilities. They do not specify
  application categories for this portal or authorize automatic routing of
  its generic application records.

## Validation boundaries

- Focused automated tests validate corpus assets and metadata, exact-source
  retrieval filtering, request validation, and forwarding of the scope through
  the `/ask` route with answer generation stubbed.
- Direct local semantic-search checks exercised retrieval against the
  development database without calling an external AI provider.
- No live external AI answer-generation request or authenticated browser
  Assistant request was performed for this integration.
- No application data, institutional database, reference checkout, or
  programme profile was changed to infer policy. No profile provisioning
  endpoint or admin role was invented.
- The current Student dashboard and application-creation pages were exercised
  in a browser using an in-page synthetic `fetch` mock; the verified visual
  state was "programme identity is not verified." This was not a live-backend
  or identity-integration test.

## Required policy and engineering prerequisites

Before claiming end-to-end PG/M.Tech/Ph.D. application support, obtain
institutional decisions for trusted programme provisioning, allowed
application categories, per-category eligibility and supporting documents,
review committee ownership, and exception/appeal behavior. Then implement
server-side validation and role-scoped routing from those approved rules and
test the entire lifecycle for each programme. A browser-selected Assistant
scope must never be treated as proof of enrollment or application
authorization.

## Prompt 4 shared retrieval integration — 2026-10-28

The active app now uses a shared retrieval facade for the Academic Assistant,
readiness, and application ordinance paths. Authenticated `GET
/knowledge/sources` reports index status only when the indexed chunk IDs and
source ID/version/hash match the registered source and checked-in processed
manifest. Authenticated `POST /knowledge/search` provides explicit-programme
candidate search; application-scoped search additionally checks application
access, trusted identity, and the exact approved policy mapping. The default
mapping remains empty, so this is not a production readiness path.

The source-gated CLI ingests existing UG/M.Tech/Ph.D. chunk/vector assets and
records provenance. It does not generate a generalized PDF-to-index pipeline:
the existing parsing, chunking, and embedding scripts remain UG-oriented.
The Assistant displays expandable source citations. PDF extraction is
application-scoped before file access and capped at 10 MiB, 100 pages, and
1,000,000 characters; it extracts embedded text only, not OCR.

Reference M.Tech/Ph.D. code was inspected but not imported. The reference
retrieval implementations require their own local model/database
configuration; their scheduling prototypes are simulated/in-memory and
minutes/case examples are not an approved institutional archive. The active
app has no meeting-scheduling or minutes-generation module. There is no
browser verification of the new knowledge endpoints; an isolated database
integration test did verify authenticated application-scoped retrieval,
source metadata, policy applicability, and unauthenticated denial.

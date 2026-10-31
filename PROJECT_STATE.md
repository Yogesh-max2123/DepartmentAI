# M.Tech (DMPC) Portal Project State

## End-to-end implementation plan

Target experience: **Student Portal with RAG Chat and a Gemini document-deficiency gatekeeper → Official Portal with claim handling, a five-heading RAG recommendation, and meeting scheduling → DMPC Committee Portal with meeting approval and AI-generated minutes.**

| Step | Scope | Status |
|---|---|---|
| 1. Establish the data foundation | Bootstrap PostgreSQL/pgvector, seed the Masters' Ordinance document and its 16 sections, and generate scheduler data. | Complete; verified against PostgreSQL |
| 2. Build the Student Portal | Add student case/application intake, document upload, Gemini-based document-deficiency checks, and student-facing status tracking. | Backend and frontend implemented |
| 3. Add student RAG support | Connect the Student Portal to the grounded ordinance RAG chat, retain conversational context, and present cited sources. | Backend and frontend implemented |
| 4. Build the Official Portal | Add claim/assignment handling for office staff, produce the five-heading RAG recommendation, and allow staff to propose and schedule DMPC meetings. | Backend and frontend implemented |
| 5. Build the DMPC Committee Portal | Present cases and meeting materials to the committee, record meeting approval/decisions, and generate and retain AI meeting minutes for review. | Backend and frontend implemented |

## Step 1 deliverables and data contract

- `backend/bootstrap_db_and_data.py` creates the required schema if absent, enables `vector`, inserts the ordinance document/sections only when missing, and invokes the scheduler-data generator.
- Seed source: `documents/mtech/processed/mtech_ordinance_structure.json`.
- Seed document filename: `Ordinances for Masters Programme 2023.pdf`; the title and page count come from the structure JSON, and the document type is `Masters' Ordinance`.
- The structure JSON currently contains 16 sections. Each section row uses its `number`, `title`, `start_page`, and `end_page`.
- `knowledge_chunks` uses `vector(384)`, matching the embedding dimension in `backend/ingest_knowledge_base.py`. Run ingestion after bootstrap, for example: `python backend/ingest_knowledge_base.py --replace`.
- The scheduler generator writes its committee and academic-calendar JSON files under `documents/scheduler/processed/`.
- `backend/workflow/db.py` creates `mtech_applications` when the FastAPI application starts; the bootstrap script creates the same table.
- Application statuses are constrained to `SUBMITTED`, `UNDER_REVIEW`, `DEFICIENCY_FOUND`, `RESUBMITTED`, `CLAIMED_BY_OFFICIAL`, `APPROVED_BY_OFFICIAL`, `MEETING_PROPOSED`, `RESCHEDULE_REQUESTED`, `MEETING_SCHEDULED`, `MINUTES_GENERATED`, and `REJECTED`. Applications also track `revision_count`, student `student_remarks`, and `official_history` action entries with timestamps, actors, and remarks.

## Workflow API

The workflow router is mounted at `/workflow`; HTTP Basic credentials are required on all workflow endpoints. Account names map to roles as follows:

| Account | Role | Password environment variable |
|---|---|---|
| `MTECH20233359` | student | `WORKFLOW_STUDENT_PASSWORD` |
| `OFFICIAL01` | official | `WORKFLOW_OFFICIAL_PASSWORD` |
| `DMPC01` | dmpc | `WORKFLOW_DMPC_PASSWORD` |

Set distinct non-placeholder passwords in `.env`. `/workflow/login` verifies credentials and returns the account role; clients send the same HTTP Basic credentials with subsequent requests.

| Method | Route | Role | Purpose |
|---|---|---|---|
| POST | `/workflow/login` | all | Validate HTTP Basic credentials and return role |
| POST | `/workflow/student/chat` | student | Ordinance RAG chat with formatted sources |
| POST | `/workflow/student/analyze-draft` | student | Retrieve ordinance requirements and check uploaded documents with Gemini |
| POST | `/workflow/student/submit` | student | Re-run the document gate and save only if no deficiencies remain |
| POST | `/workflow/student/resubmit/{app_id}` | student | Re-check multiple new uploads for a deficient application, append valid files, and record a revision |
| GET | `/workflow/student/applications/{student_reg_no}` | student | List the authenticated student's applications |
| GET | `/workflow/official/applications` | official | List the incoming official queue |
| POST | `/workflow/official/claim/{app_id}` | official | Claim an application and save the five-heading RAG recommendation |
| POST | `/workflow/official/decision/{app_id}` | official | Mark under review, return for deficiencies, approve directly, or propose/reschedule a DMPC meeting |
| GET | `/workflow/dmpc/applications` | dmpc | List applications awaiting or completing committee work |
| POST | `/workflow/dmpc/approve-meeting/{app_id}` | dmpc | Approve a proposed slot and dispatch the scheduler invite, or request rescheduling with a remark for the official |
| POST | `/workflow/dmpc/generate-minutes/{app_id}` | dmpc | Generate and persist minutes from meeting notes and final decision |

## Frontend architecture

The multi-role portal is a responsive, dependency-free frontend in `frontend/index.html`, `frontend/app.js`, and `frontend/style.css`. It uses hash routes (`#/student`, `#/official`, `#/dmpc`) and a role-specific navigation view. The frontend is served separately (for example on port 5500); API requests default to `http://127.0.0.1:8000` and can be redirected with the `?api=` query parameter.

- Login verifies credentials through `POST /workflow/login`; HTTP Basic credentials are retained in tab-scoped `sessionStorage` and sent on every `/workflow/*` request. Configure all three workflow password environment variables in `.env`.
- Student views provide RAG chat with conversation history and source references, multiple PDF/text uploads encoded for `POST /workflow/student/analyze-draft`, an analysis-invalidating form gate, submission through `POST /workflow/student/submit`, and a 20-second application-status refresh while the tracker is open. The tracker renders a six-stage application timeline, highlights deficiencies and official remarks, and opens an AI-gated multi-file resubmission modal for returned applications.
- Official views emphasize resubmitted and reschedule-requested queue items and expose Mark Under Review and Send Back to Student actions; returning an application requires remarks entered in a modal. DMPC can request rescheduling from the meeting queue through a remarks modal. These actions update status and append actor/timestamp/remark entries to `official_history`.
- Official views list and claim applications, render the five-heading RAG recommendation and saved sources, allow direct approval or application-linked meeting proposal, and expose a standalone scheduling console backed by `/schedule/propose`, `/schedule/proposals`, and `/schedule/approve`.
- DMPC view lists committee applications, approves a selected proposed slot through the workflow API (which dispatches the scheduler's mock email and calendar invite), and generates saved minutes from entered notes and decision.
- Existing backend APIs `/ask` and `/schedule/*` remain mounted. `/ask` remains available to other clients; student chat uses the authenticated workflow equivalent.

## Current backend function signatures

The following signatures are recorded from the inspected backend modules; unannotated parameters and return types are left as currently declared.

### Knowledge-base ingestion — `backend/ingest_knowledge_base.py`

```python
def validate_files():
def load_json_files():
def connect_database():
def build_embedding_lookup(embedding_chunks):
def load_embedding_model():
def vector_to_string(embedding):
def load_synthetic_dataset(spec):
def build_synthetic_embedding_text(record, chunk_type):
def ensure_synthetic_document(cursor, spec):
def replace_or_guard_existing_chunks(cursor, document_id, replace_existing):
def ingest_one_synthetic_dataset(cursor, spec, model, replace_existing):
def ingest_synthetic_datasets(connection, cursor, replace_existing=False):
def ingest_knowledge_base(
    replace_existing: bool = False,
    skip_synthetic: bool = False,
    synthetic_only: bool = False,
):
```

### Student RAG API and pipeline

```python
def ask_question(request: AskRequest):
def answer_question(question, conversation_history=None):
def generate_text(prompt: str) -> str:
def generate_answer(question: str, context: str) -> str:
```

### Scheduling and minutes API — `backend/api/scheduler_routes.py`

```python
def schedule_propose(request: ProposeRequest):
def schedule_approve(request: ApproveRequest):
def schedule_list_proposals():
def schedule_get_proposal(proposal_id: str):
async def generate_minutes(req: MinutesRequest):
```

The current scheduler models include `ProposeRequest(committee_name, date_range, agenda, duration_minutes=60, use_gemini=True)`, `ApproveRequest(proposal_id, approved=True, slot_index=None, hod_comment="", use_gemini=True)`, and `MinutesRequest(proposal_id, context_text)`.

## Database and model configuration currently in `backend/`

`backend/ingest_knowledge_base.py` and `backend/retrieval/semantic_search.py` load `.env` with `python-dotenv` and use `psycopg2`. Their PostgreSQL connection settings are:

| Setting | Environment variable | Default / requirement |
|---|---|---|
| Database | `DEPARTMENTAI_DB_NAME` | `departmentai` |
| User | `DEPARTMENTAI_DB_USER` | `postgres` |
| Host | `DEPARTMENTAI_DB_HOST` | `localhost` |
| Port | `DEPARTMENTAI_DB_PORT` | `5432` |
| Password | `DEPARTMENTAI_DB_PASSWORD` | Required; no default |

`connect_database()` in the ingestion module calls `psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT)`. Retrieval uses the same values (with `database=DB_NAME` as the connection keyword). The repository `.env.example` currently documents only `DEPARTMENTAI_DB_PASSWORD` for PostgreSQL.

The RAG client uses `GEMINI_API_KEY` and model `gemini-3.5-flash-lite`. Separately, the existing `/schedule/minutes/generate` route configures the legacy `google.generativeai` client from `GOOGLE_API_KEY`; that configuration difference is present in the current code and is not changed by Step 1.

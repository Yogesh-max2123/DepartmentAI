# AGENT_HANDOFF_LOG.md

Handoff document for DepartmentAI / MNNIT Department Portal (B.Tech. / M.Tech. / Ph.D.).

**Last updated:** 2026-10-31
**Status:** UNIFIED UG + PG + Ph.D. SYSTEM — three document trees in repo
**Resume from:** sequential ingest `phd` then `mtech` then `ug` (needs pgvector), restart uvicorn. Artifact: `DepartmentAI-Unified.zip`.

---

## 1. Mission

Existing repo is a working FastAPI RAG + Gemini Meeting Scheduling Agent (Module 1: Ph.D./DDPC).

Build a complete end-to-end system:

1. Role-based auth: `STUDENT` | `OFFICIAL` | `COMMITTEE_DDPC`
2. Application state machine in a database
3. Student UI: profile, RAG chatbot (`POST /ask`), application form + PDF upload
4. AI document verification (PyMuPDF extract + LLM match)
5. Official queue + auto 5-heading draft resolution via `qa_pipeline.answer_question`
6. Committee slot approval via existing `POST /schedule/propose` and `POST /schedule/approve`
7. AI minutes + resolve, green tracker on student dashboard

Constraints:

- Keep existing RAG, scheduler, Gemini client, pgvector ingestion intact
- Vanilla HTML/CSS/JS frontend (matches existing stack, stays inside token budget)
- Single-port preview: FastAPI serves API + static frontend
- Continuously update this log
- Final ZIP + detailed local VS Code README

---

## 2. Existing backend (DO NOT BREAK)

| Path | Role |
| ---- | ---- |
| `backend/main.py` | FastAPI app, CORS, routers |
| `backend/api/routes.py` | `POST /ask` |
| `backend/api/scheduler_routes.py` | `POST /schedule/propose`, `POST /schedule/approve`, `GET /schedule/proposals`, `POST /schedule/minutes/generate` |
| `backend/rag/qa_pipeline.py` | `answer_question(question, history) -> (answer, results)` |
| `backend/llm/gemini_client.py` | `generate_text`, `generate_answer` (5 headings). Starts without key; live generate needs `GEMINI_API_KEY` |
| `ai/ingestion/pdf_parser.py` | PyMuPDF page extract |
| `backend/agents/scheduling_agent.py` | `propose_meeting` returns `{ok, proposal: {proposal_id, slots, ...}}`. `approve_meeting(proposal_id, slot_index, ...)` |
| `frontend/` | Legacy chat-only UI — will be replaced by unified app; chat logic reused |

Env (`.env.example`):

```
DEPARTMENTAI_DB_PASSWORD=
GEMINI_API_KEY=
DEPARTMENTAI_DB_NAME=departmentai   # optional, default
DEPARTMENTAI_DB_USER=postgres
DEPARTMENTAI_DB_HOST=localhost
DEPARTMENTAI_DB_PORT=5432
```

Scheduler propose response shape:

- Top-level `proposal.proposal_id`
- `proposal.slots` = list of slot objects
- `packed["slots"]` is the tool result dict (has `.slots`)
- Frontend must read `data.proposal.proposal_id` and `data.proposal.slots`

Approve: `slot_index` is **1-based**.

Default date range used by existing UI: `2026-09-14 to 2026-09-25`, committee `DDPC`.

---

## 3. Architectural decisions

| Decision | Choice | Why |
| -------- | ------ | --- |
| Frontend | Vanilla HTML/CSS/JS SPA in `frontend/` | Existing stack, no build step, token-efficient, easy VS Code Live Server or FastAPI static |
| Serving | FastAPI serves `frontend/` last via `StaticFiles(html=True)` | Single port for preview; no CORS for same-origin fetches |
| Workflow DB | Same PostgreSQL `departmentai` DB; **SQLite fallback** `data/workflow.db` | Preview/dev may lack Postgres; RAG still needs pgvector |
| Auth | PBKDF2-SHA256 password hashes + bearer tokens in memory (`TOKEN_STORE`) | No extra JWT dependency; demo-local is enough |
| Passwords | Not bcrypt (avoid extra wheel issues) | stdlib hashlib |
| File uploads | `python-multipart` + disk `documents/uploads/{application_id}/` | PyMuPDF reads local path |
| Verification | Gemini JSON check + keyword fallback | Works without API key |
| Draft resolution | Call `answer_question(description)` | Reuses RAG 5-heading agent |
| Scheduling | Call `propose_meeting` / `approve_meeting` with `use_gemini=False` by default | Deterministic slots for local testing |
| Minutes | Reuse `_generate_minutes_text` then set `MINUTES_GENERATED` then `RESOLVED` | Student sees green final state |
| Invalid docs | Stay `DRAFT`, set `missing_documents`, `verification_result` | Spec statuses do not include DOCS_INVALID |
| Demo users | Seeded on startup if `users` empty | Instant local test |

### Design system (UI)

Academic enterprise dashboard, light mode (readable for officials):

- Primary navy `#0B1F3A`
- Accent gold `#B45309` (academic seal)
- Success `#15803D`
- Surface `#F7F4EE` paper, cards `#FFFFFF`
- Fonts: IBM Plex Sans (UI) + Source Serif 4 (headings)
- SVG icons only, no emoji
- 7-step status tracker, role-colored shells
- Touch targets >= 44px, visible focus rings

---

## 4. Database schema

Workflow tables live beside existing `documents` / `knowledge_chunks` (RAG). Created by `backend/workflow/store.py` on API startup.

### 4.1 `users`

| Column | Type | Notes |
| ------ | ---- | ----- |
| id | SERIAL PK | |
| email | VARCHAR(255) UNIQUE NOT NULL | login |
| password_hash | VARCHAR(255) NOT NULL | `salt_hex$dk_hex` PBKDF2 |
| full_name | VARCHAR(255) NOT NULL | |
| role | VARCHAR(32) NOT NULL | `STUDENT` / `OFFICIAL` / `COMMITTEE_DDPC` |
| roll_number | VARCHAR(64) | students |
| department | VARCHAR(128) | default CSE |
| programme | VARCHAR(128) | default Ph.D. |
| phone | VARCHAR(32) | |
| created_at | TIMESTAMPTZ | default now |

### 4.2 `applications`

| Column | Type | Notes |
| ------ | ---- | ----- |
| id | SERIAL PK | |
| student_id | INT FK users | |
| title | VARCHAR(512) | |
| description | TEXT | fed to RAG |
| application_type | VARCHAR(128) | see types below |
| status | VARCHAR(32) | state machine |
| verification_result | TEXT/JSONB | JSON |
| missing_documents | TEXT | JSON list |
| draft_resolution | TEXT | 5-heading RAG output, editable |
| proposal_id | VARCHAR(64) | scheduler PROP-... |
| proposed_slots | TEXT/JSONB | cached slots |
| approved_slot | TEXT/JSONB | |
| minutes_text | TEXT | |
| final_summary | TEXT | shown to student |
| official_id | INT FK users | last official actor |
| committee_id | INT FK users | last committee actor |
| created_at / updated_at | TIMESTAMPTZ | |

**Status machine (required):**

```
DRAFT -> DOCS_VERIFIED -> OFFICIAL_REVIEW -> MEETING_PROPOSED
      -> MEETING_SCHEDULED -> MINUTES_GENERATED -> RESOLVED
```

Invalid verification: remain `DRAFT` + flag `missing_documents`.

### 4.3 `application_documents`

| Column | Type |
| ------ | ---- |
| id | SERIAL PK |
| application_id | INT FK CASCADE |
| filename | VARCHAR(512) |
| stored_path | VARCHAR(1024) |
| content_type | VARCHAR(128) |
| extracted_text | TEXT |
| uploaded_at | TIMESTAMPTZ |

### 4.4 `status_history`

| Column | Type |
| ------ | ---- |
| id | SERIAL PK |
| application_id | INT FK CASCADE |
| from_status | VARCHAR(32) |
| to_status | VARCHAR(32) |
| note | TEXT |
| actor_id | INT FK users |
| created_at | TIMESTAMPTZ |

### 4.5 Application types (verification checklist)

- `comprehensive_exam`
- `thesis_extension`
- `supervisor_allocation`
- `supervisor_change`
- `semester_leave`
- `thesis_submission`
- `general`

### 4.6 Seed users (plaintext only in README / this log)

| Email | Password | Role | Name |
| ----- | -------- | ---- | ---- |
| student@mnnit.ac.in | student123 | STUDENT | Ananya Sharma | roll 2023RCS01 |
| official@mnnit.ac.in | official123 | OFFICIAL | Rajesh Kumar | Member Secretary DDPC |
| committee@mnnit.ac.in | committee123 | COMMITTEE_DDPC | Prof. Meera Joshi | HoD / DDPC Chair |

---

## 5. New API surface (`/api`)

All except login require `Authorization: Bearer <token>`.

| Method | Path | Role | Behavior |
| ------ | ---- | ---- | -------- |
| POST | `/api/auth/login` | public | `{email,password}` -> `{token,user}` |
| GET | `/api/auth/me` | any | current user |
| GET | `/api/applications` | any | role-scoped list |
| POST | `/api/applications` | STUDENT | create DRAFT `{title,description,application_type}` |
| GET | `/api/applications/{id}` | owner/staff | detail + docs + history |
| POST | `/api/applications/{id}/documents` | STUDENT | multipart `files` PDFs, extract text |
| POST | `/api/applications/{id}/submit` | STUDENT | verify docs; if valid -> DOCS_VERIFIED then OFFICIAL_REVIEW |
| POST | `/api/applications/{id}/draft-resolution` | OFFICIAL | RAG on description, save draft, status OFFICIAL_REVIEW |
| PUT | `/api/applications/{id}/draft-resolution` | OFFICIAL | save edited text |
| POST | `/api/applications/{id}/schedule/propose` | OFFICIAL | `propose_meeting`, status MEETING_PROPOSED |
| POST | `/api/applications/{id}/schedule/approve` | COMMITTEE_DDPC | `{slot_index}` 1-based, `approve_meeting`, MEETING_SCHEDULED |
| POST | `/api/applications/{id}/minutes` | OFFICIAL | generate minutes, MINUTES_GENERATED then RESOLVED |

Existing endpoints unchanged: `POST /ask`, `/schedule/*`.

---

## 6. Dependencies to add

- `python-multipart` (FastAPI `UploadFile`)

No React/Vue. No JWT library.

---

## 7. File plan

```
AGENT_HANDOFF_LOG.md          (this file)
backend/workflow/__init__.py
backend/workflow/store.py     schema, seed, CRUD, PG+SQLite
backend/workflow/auth.py      hash, tokens
backend/workflow/verify.py    PyMuPDF + LLM/fallback
backend/api/workflow_routes.py
backend/main.py               include router, init_db, StaticFiles
frontend/index.html
frontend/style.css
frontend/app.js
requirements.txt              + python-multipart
README.md                     local VS Code setup rewritten
documents/uploads/            gitignored runtime
data/workflow.db              sqlite fallback, gitignored
```

---

## 8. Implementation checklist

- [x] Explore existing backend
- [x] Schema + decisions in this log
- [x] `backend/workflow/store.py` + auth + verify
- [x] `backend/api/workflow_routes.py`
- [x] `backend/main.py` wire-up + static
- [x] Unified frontend
- [x] README local testing guide
- [x] python-multipart
- [x] Smoke-test / syntax check (TestClient: DRAFT -> RESOLVED)
- [x] deploy-website preview (uvicorn :8000, terminal term_1793349002508_1)
- [x] Programme-tagged ingest (`phd` / `mtech` / `ug`) + `--programme` CLI
- [x] `semantic_search` / `retrieve_for_recommendation` programme filter
- [x] `POST /ask` optional `role` + `programme`; student vs official prompts
- [x] Draft resolution + schedule committee from application programme (DDPC / DMPC / DUGC)
- [x] Login CSS `[hidden] { display: none !important }` + logout `localStorage` clear + reload
- [x] Seed M.Tech. student `mtech.student@mnnit.ac.in` / `student123`
- [x] Seed B.Tech. student `ug.student@mnnit.ac.in` / `student123`
- [x] Student RAG sanitization (ordinance/forms only, empty sources)
- [x] Profile photo upload (`PUT /api/auth/profile`, `POST /api/auth/profile/photo`)
- [x] Scheduler member free-time windows + DUGC convener match
- [ ] Local triple-KB ingest (needs PostgreSQL + pgvector)
- [x] ZIP artifact includes `documents/phd/`, `documents/mtech/`, and `documents/ug/`

Verified flow: login -> create DRAFT -> upload PDF -> submit DOCS_VERIFIED/OFFICIAL_REVIEW -> draft resolution -> propose 3 slots -> approve -> minutes -> RESOLVED.

Demo users:
- ug.student@mnnit.ac.in / student123 (B.Tech.)
- student@mnnit.ac.in / student123 (Ph.D.)
- mtech.student@mnnit.ac.in / student123 (M.Tech.)
- official@mnnit.ac.in / official123
- committee@mnnit.ac.in / committee123

If calendar find_common_free_slots returns 0, workflow_routes injects 3 demo slots for 2026-09-15/17/22 so committee approval still works.

---

## 9. Resume instructions for the next agent

If this session stops:

1. Read this file fully.
2. Check which checklist boxes are still open.
3. Do not re-ingest the ordinance KB unless asked.
4. Do not modify RAG retrieval math.
5. Keep `/ask` and `/schedule/*` signatures additive only (`role`, `programme` optional on `/ask`).
6. Frontend must use relative URLs (`/ask`, `/api/...`) not hardcoded `http://127.0.0.1:8000` so same-origin preview works.
7. After web changes, use `/deploy-website` (not publish-website).

---

## 10. Notes / gotchas

- `propose_meeting` does not put `proposal_id` at top level; it is `result["proposal"]["proposal_id"]`.
- Gemini client is `None` without key; verification and minutes must fallback.
- `sentence-transformers` load is heavy; draft-resolution will be slow first time if model not cached.
- Guardrails may block some application descriptions; wrap `answer_question` and if blocked, still produce a structured stub draft so officials can edit.
- No `rm` / no long-running servers in the foreground Bash tool — use background terminal + deploy-website skill.
- Existing CORS already allows `*.monkeycode-ai.live`.
- Same `knowledge_chunks` table; filter with `metadata->>'programme'` (`phd`/`mtech`/`ug`). Untagged legacy Ph.D. rows default to `phd`.
- Login used to stay visible because `.login-screen { display: grid }` overrode `[hidden]`.
- Official chatbot has a B.Tech. / M.Tech. / Ph.D. knowledge-base selector; students auto-route from profile.
- Students never receive synthetic chunks or `sources`; `_sanitize_student_answer` strips 5-heading leaks.
- Profile photos live under `frontend/uploads/profiles/` and are served as `/uploads/profiles/...`.
- DUGC membership in `synthetic_committee_db.json` uses HoD Prof. Meenakshi Iyer (from UG pipeline).

---

## 11. Session 2026-10-30 — M.Tech. RAG routing

Wired programme routing through ingest, retrieval, `/ask`, draft-resolution, and scheduling. Role-based prompts: students get concise ordinance answers; officials keep the 5-heading draft. Login hide + sign-out reload fixed. README documents dual-KB ingest.

---

## 12. Session 2026-10-31 — UG merge (B.Tech. / DUGC)

Merged standalone `ug_rag_pipeline` into the unified FastAPI / pgvector / vanilla-JS portal.

Architecture:

- One FastAPI app (`backend/main.py` v1.3.0) serves API + `frontend/` at `/`.
- Programme key `ug` / `mtech` / `phd` on ingest, retrieval, chat, applications, and scheduling.
- `backend/rag/programme.py` and `ai/programme_paths.py` (`UG_STRUCTURE`) route B.Tech. / DUGC.
- Ingest: `python backend/ingest_knowledge_base.py --programme {phd|mtech|ug|all} --replace`. Default `all` runs phd then mtech then ug.
- Student chat: ordinance/forms only, empty `sources`, conversational prompt + `_sanitize_student_answer`. Officials keep mixed RAG + 5 headings.
- Scheduler: per-slot `member_availability` and `member_free_windows`; convener match is `"convener" in role.lower()` so `"Convener DUGC"` works.
- Workflow: `photo_url`, `member_availability`, UG application types, seed Priya Nair.
- Frontend branded **MNNIT Department Portal** with `logo.png`, profile modal/avatar, UG chat/application types, free-time UI.

Ingest order for first setup:

```bash
python backend/ingest_knowledge_base.py --programme phd --replace
python backend/ingest_knowledge_base.py --programme mtech --replace
python backend/ingest_knowledge_base.py --programme ug --replace
```

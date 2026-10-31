# MNNIT Department Portal (DepartmentAI)

### Agentic AI-Based Academic Department Automation System — B.Tech., M.Tech. and Ph.D.

## Local VS Code Setup and End-to-End Testing

This section is the practical runbook for cloning the repo in Visual Studio Code and exercising the full scholar-to-committee flow on your machine.

### What you will run

| Piece | How it is served |
| ----- | ---------------- |
| FastAPI backend | `uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000` |
| Unified frontend | Same process: FastAPI mounts `frontend/` at `/` |
| Workflow state (users, applications) | PostgreSQL if `DEPARTMENTAI_DB_PASSWORD` works, otherwise SQLite `data/workflow.db` |
| RAG knowledge base | PostgreSQL + pgvector (required only for live `/ask` and official draft resolution) |

Demo logins (seeded on first API start):

| Role | Email | Password |
| ---- | ----- | -------- |
| STUDENT (B.Tech.) | `ug.student@mnnit.ac.in` | `student123` |
| STUDENT (Ph.D.) | `student@mnnit.ac.in` | `student123` |
| STUDENT (M.Tech.) | `mtech.student@mnnit.ac.in` | `student123` |
| OFFICIAL | `official@mnnit.ac.in` | `official123` |
| COMMITTEE_DDPC | `committee@mnnit.ac.in` | `committee123` |

Application statuses:

```text
DRAFT -> DOCS_VERIFIED -> OFFICIAL_REVIEW -> MEETING_PROPOSED
      -> MEETING_SCHEDULED -> MINUTES_GENERATED -> RESOLVED
```

### A. Python virtual environment

Open the repository root in VS Code. Use the integrated terminal.

```bash
python -m venv venv
```

Linux / macOS:

```bash
source venv/bin/activate
```

Windows (PowerShell):

```powershell
.\venv\Scripts\Activate.ps1
```

Confirm the prompt shows `(venv)`. Select that interpreter in VS Code (`Python: Select Interpreter`).

### B. Install Python packages

```bash
pip install -r requirements.txt
```

That install includes FastAPI, Uvicorn, psycopg2, PyMuPDF, sentence-transformers, google-genai, and `python-multipart` (required for PDF uploads).

### C. Environment file

```bash
cp .env.example .env
```

Edit `.env` in VS Code:

```env
DEPARTMENTAI_DB_PASSWORD=your_database_password_here
GEMINI_API_KEY=your_api_key_here
DEPARTMENTAI_DB_NAME=departmentai
DEPARTMENTAI_DB_USER=postgres
DEPARTMENTAI_DB_HOST=localhost
DEPARTMENTAI_DB_PORT=5432
```

Notes:

- `GEMINI_API_KEY` is required for live RAG answers, live document-verification JSON, and live minutes. Without it the API still starts; verification, minutes, and scheduler use deterministic fallbacks.
- If PostgreSQL is not available, omit a working password and the workflow tables fall back to SQLite. RAG retrieval will not work until pgvector is loaded.

### D. PostgreSQL and pgvector (for RAG)

Install PostgreSQL 16+ with the pgvector extension. Then:

```bash
sudo -u postgres psql
```

```sql
CREATE DATABASE departmentai;
\c departmentai
CREATE EXTENSION IF NOT EXISTS vector;
```

Create the RAG tables expected by `backend/ingest_knowledge_base.py`:

```sql
CREATE TABLE IF NOT EXISTS documents (
    id              SERIAL PRIMARY KEY,
    title           TEXT,
    file_name       TEXT,
    document_type   TEXT,
    version         TEXT,
    total_pages     INTEGER,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sections (
    id              SERIAL PRIMARY KEY,
    document_id     INTEGER REFERENCES documents(id),
    section_number  TEXT,
    title           TEXT,
    start_page      INTEGER,
    end_page        INTEGER,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id              SERIAL PRIMARY KEY,
    document_id     INTEGER REFERENCES documents(id),
    section_id      INTEGER REFERENCES sections(id),
    chunk_index     INTEGER,
    chunk_type      TEXT,
    clause_number   TEXT,
    chunk_text      TEXT,
    page_start      INTEGER,
    page_end        INTEGER,
    form_id         TEXT,
    metadata        JSONB,
    embedding       vector(384),
    created_at      TIMESTAMP DEFAULT NOW()
);
```

Insert the ordinance document row and section rows (or let ingest create them), then load all three knowledge bases. Chunks are tagged with metadata `programme` (`phd`, `mtech`, or `ug`) in the same `knowledge_chunks` table.

Ingest sequentially (recommended on first setup):

```bash
# 1. Ph.D. / DDPC
python backend/ingest_knowledge_base.py --programme phd --replace

# 2. M.Tech. / DMPC (PG)
python backend/ingest_knowledge_base.py --programme mtech --replace

# 3. B.Tech. / DUGC (UG)
python backend/ingest_knowledge_base.py --programme ug --replace
```

Or ingest all three in one run (default `--programme all`):

```bash
python backend/ingest_knowledge_base.py --replace
```

Processed ordinance JSON already exists under `documents/phd/processed/`, `documents/mtech/processed/`, and `documents/ug/processed/`. Source PDFs live beside them:

* `documents/phd/Ordinances_for_Doctoral_Programm2023.pdf`
* `documents/mtech/Ordinances for Masters Programme 2023.pdf`
* `documents/ug/Ordinances_for_Bachelors_Programme.pdf`

Rebuild processed JSON only if you change a PDF. Pass `--programme phd|mtech|ug`:

```bash
python ai/ingestion/pdf_parser.py --programme ug
python ai/ingestion/structure_parser.py --programme ug
python ai/ingestion/intelligent_chunker.py --programme ug
python ai/embeddings/embedding_generator.py --programme ug
python ai/ingestion/synthetic_scheduler_data.py
```

Workflow tables (`users`, `applications`, `application_documents`, `status_history`) are created automatically when Uvicorn starts.

### E. Sample supporting PDF

```bash
python scripts/make_sample_evidence.py
```

This writes `documents/samples/sample_thesis_extension.pdf` for the student upload step.

### F. Start FastAPI (backend + frontend)

From the repository root, with the venv active:

```bash
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Open in a browser:

```text
http://127.0.0.1:8000/
```

API docs: `http://127.0.0.1:8000/docs`

Health: `http://127.0.0.1:8000/health`

You do not need a second static server. If you prefer Live Server on port 5500, CORS already allows it, but same-origin on port 8000 is the intended path.

### G. Step-by-step application flow (manual test)

1. Browser: `http://127.0.0.1:8000/`
2. Click **Student** (or sign in as `student@mnnit.ac.in` / `student123`).
3. Confirm the profile card shows Ananya Sharma, roll `2023RCS01`.
4. Open **Ordinance chatbot**. Ask: `What is the minimum SPI/CPI requirement for continuing in the programme?` You should see a five-heading draft if pgvector + Gemini are configured; otherwise a guardrail or connection error.
5. Open **New application**.
   - Type: Thesis Extension
   - Title: `Request for one-semester thesis extension`
   - Description: `Ph.D. scholar requests a one-semester thesis duration extension. Coursework and comprehensive examination are complete. Supervisor recommends the extension based on remaining experimental work.`
   - Attach `documents/samples/sample_thesis_extension.pdf`
   - Submit.
6. Status should move `DRAFT -> DOCS_VERIFIED -> OFFICIAL_REVIEW` if verification passes. If it stays `DRAFT`, the yellow banner lists missing evidence; upload a better PDF and submit again.
7. Sign out. Sign in as **Official** (`official@mnnit.ac.in` / `official123`).
8. Open the case in the review queue. Opening it auto-runs RAG and fills the five headings: Relevant ordinance clauses, Similar previous cases, Identified deficiencies, Possible course of action, Initial draft resolution.
9. Edit the draft if needed, click **Save edits**, then **Schedule meeting**. Status becomes `MEETING_PROPOSED` with three calendar slots.
10. Sign out. Sign in as **Committee** (`committee@mnnit.ac.in` / `committee123`).
11. Open the case and click **Approve slot** on one of the three slots. This calls `POST /schedule/approve`, writes a mock `.ics` invite, and sets `MEETING_SCHEDULED`.
12. Sign back in as Official. Open the same case. Click **Generate minutes**. Status becomes `MINUTES_GENERATED` then `RESOLVED`.
13. Sign in as Student. The tracker is green at RESOLVED and the minutes / final summary are visible.

### H. API smoke checks (optional)

```bash
curl -s http://127.0.0.1:8000/health

curl -s -X POST http://127.0.0.1:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"student@mnnit.ac.in\",\"password\":\"student123\"}"
```

Existing RAG and scheduler routes are unchanged:

```text
POST /ask
POST /schedule/propose
POST /schedule/approve
POST /schedule/minutes/generate
```

---

DepartmentAI is an **AI-powered academic governance and department automation system** designed to assist academic committees, faculty, and authorized officials in managing academic processes, institutional knowledge, documentation, and administrative workflows.

This repository is the **unified B.Tech., M.Tech. and Ph.D. module** of DepartmentAI (MNNIT Department Portal). It follows one architecture, file layout, pipeline, and RAG stack. Retrieval is routed by student programme:

* B.Tech. / DUGC — `documents/ug/` — Ordinances for Bachelors Programmes, 2023
* M.Tech. / DMPC — `documents/mtech/` — Ordinances for Masters' Programmes, 2023
* Ph.D. / DDPC — `documents/phd/` — Ordinances for Doctoral Programmes, 2023

The system combines **Large Language Models (LLMs), Retrieval-Augmented Generation (RAG), document intelligence, semantic search, vector databases, and workflow automation** to provide reliable, context-aware assistance while keeping final academic decisions under authorized human control.

> **Human-in-the-loop principle:** DepartmentAI assists with information retrieval, analysis, recommendations, drafting, and workflow preparation. It does not autonomously approve or reject official academic applications where human authorization is required.

---

## Project Vision

Academic departments handle a large amount of information including:

* Academic ordinances
* Rules and regulations
* Circulars and notifications
* Committee decisions
* Student applications
* Faculty information
* Academic records
* Institutional reports
* Administrative documents

Finding the correct information from these documents can be time-consuming and error-prone.

DepartmentAI aims to provide a centralized intelligent system where authorized users can interact with institutional knowledge using natural language.

For example:

> **User:** What is the minimum SPI/CPI requirement for continuing in the Ph.D. programme?

> **DepartmentAI:** The minimum SPI/CPI requirement for continuing in the programme is equal to 6.5.

The answer is generated from the **retrieved official ordinance content**, rather than from unrestricted general knowledge.

---

## Objectives

The major objectives of DepartmentAI are:

1. Build an intelligent knowledge base for academic ordinances and institutional documents.
2. Enable natural-language querying over official academic rules.
3. Implement reliable Retrieval-Augmented Generation (RAG).
4. Use semantic search to retrieve relevant institutional information.
5. Generate concise, grounded answers using an LLM.
6. Automate repetitive academic and administrative workflows.
7. Assist academic committees such as DUGC, DMPC, and DDPC (default doctoral committee: DDPC).
8. Provide document and knowledge management capabilities.
9. Support multilingual interaction in future versions.
10. Maintain human authorization for official academic decisions.
11. Provide traceability from generated answers back to source documents.

---

## High-Level Architecture

The current system follows a Recommendation-Agent RAG architecture:

```text
                    ┌─────────────────────┐
                    │       User          │
                    │  Question / Case    │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │     Guardrails      │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │   Query Embedding   │
                    │ Sentence Transformer│
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ PostgreSQL +        │
                    │      pgvector       │
                    │ Mixed Retrieval     │
                    │ ordinance / cases / │
                    │ minutes / circulars │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Semantic + Keyword  │
                    │     Reranking       │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Recommendation Agent│
                    │      Gemini API     │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Draft Resolution    │
                    │  (five headings)    │
                    └─────────────────────┘
```

The Meeting Scheduling Agent is independent of RAG. After a draft resolution is shown, the frontend can call `POST /schedule/propose` and `POST /schedule/approve` for a DDPC meeting.

---

## Core Technologies

| Component                 | Technology                                                    |
| ------------------------- | ------------------------------------------------------------- |
| Programming Language      | Python                                                        |
| Backend Framework         | FastAPI                                                       |
| Database                  | PostgreSQL 18                                                 |
| Vector Database Extension | pgvector                                                      |
| Embedding Model           | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` |
| Embedding Dimension       | 384                                                           |
| LLM                       | Gemini API (`gemini-3.5-flash-lite`) via `google-genai`       |
| ORM / Database Access     | psycopg2                                                      |
| Data Processing           | NumPy / Pandas                                                |
| PDF Processing            | PyMuPDF                                                       |
| Frontend                  | Vanilla HTML / CSS / JavaScript                               |
| API Server                | Uvicorn                                                       |

---

## Current Module: Doctoral Ordinance → DDPC

This implementation focuses on the **Doctoral Programmes Ordinance and DDPC/SDPC-related academic processes**.

The current authoritative knowledge sources are:

**MNNIT Allahabad Ordinances for Doctoral Programmes (2023)**

plus ordinance-grounded **synthetic** DDPC records that stand in for archives that are not available:

* similar previously decided cases (`past_case`)
* previous minutes of DDPC meetings (`meeting_minute`)
* departmental office orders / circulars (`circular`)

The ordinance was approved by the Board of Governors in its Seventy-third (73rd) meeting held on August 10, 2023 vide Resolution No. 73.13 (A).

The ordinance contains academic rules covering areas such as:

* Introduction (DDPC / SDPC / SRC)
* Academic Session
* Admission (IDSC / DDSC)
* Registration
* Leave Rules
* Permission to Attend Other Academic Institutions / Industry as Non-Degree Students
* Programme Requirements and Grading System
* Academic Performance Requirement
* Comprehensive Examination
* State-of-the-Art Seminar
* Open Seminar
* Appointment of Thesis Supervisor(s) and Constitution of Committees / Boards
* Thesis Submission, Evaluation and Examination
* Degree Requirements and Withdrawal
* Stipends / Fellowships, Scholarships, Prizes and Medals
* Conduct and Discipline
* Waiver of Requirements in Special Cases
* Amendments

The system is being developed so users can ask questions about these rules using natural language.

---

## Retrieval-Augmented Generation (RAG)

DepartmentAI uses RAG to reduce hallucination and ensure that answers are based on institutional documents.

The retrieval pipeline is:

```text
Official Ordinance PDF
       │
       ▼
PDF Extraction
       │
       ▼
Structure Detection
       │
       ▼
Intelligent Chunking
       │
       ├──────────────────────────────┐
       ▼                              ▼
Embedding Generation         Gemini synthetic generator
(ordinance chunks)           (cases / minutes / circulars)
       │                              │
       └──────────────┬───────────────┘
                      ▼
            PostgreSQL + pgvector
                      │
                      ▼
         Mixed semantic + keyword retrieval
                      │
                      ▼
            Recommendation Agent (Gemini)
                      │
                      ▼
            Five-heading draft resolution
```

---

## Document Processing Pipeline

### 1. PDF Parsing

The original ordinance PDF is processed using **PyMuPDF**.

```text
Ordinances_for_Doctoral_Programm2023.pdf
       ↓
Text Extraction
       ↓
Page-level structured data
```

### 2. Structure Parsing

The extracted text is analyzed to identify:

* Sections
* Clauses
* Forms
* Form references
* Page ranges

PyMuPDF often splits a heading number onto its own line (`2.` then `ACADEMIC SESSION`). The structure parser joins those logical lines before matching.

The current ordinance processing identified:

```text
18 unique ordinance sections (Sections 1 to 18)
73 unique ordinance clauses
26 physical form records
26 unique form IDs (DP-01 to DP-24, DP-12a / DP-12b, and GL-1)
```

### 3. Intelligent Chunking

The ordinance is divided into retrieval-friendly chunks.

Current dataset:

```text
117 ordinance chunks
+
 26 form chunks
=
143 total chunks
```

Chunking parameters include:

```text
Target size: 2500 characters
Maximum size: 3200 characters
Overlap: 600 characters
```

### 4. Embedding Generation

Each chunk is converted into a numerical vector using:

```text
sentence-transformers/
paraphrase-multilingual-MiniLM-L12-v2
```

Configuration:

```text
Dimensions: 384
Batch size: 16
Normalized embeddings: Yes
```

---

## Database

DepartmentAI currently uses PostgreSQL with pgvector.

```text
Database: departmentai
```

### Database Schema

#### `documents`

```text
id
title
file_name
document_type
version
total_pages
created_at
```

#### `sections`

```text
id
document_id
section_number
title
start_page
end_page
created_at
```

#### `knowledge_chunks`

```text
id
document_id
section_id
chunk_index
chunk_type
clause_number
chunk_text
page_start
page_end
form_id
metadata
embedding
created_at
```

Embeddings are stored using:

```sql
vector(384)
```

---

## Semantic Retrieval

The current retrieval system performs:

```text
Question
   ↓
Generate query embedding
   ↓
pgvector similarity search
   ↓
50 candidate chunks
   ↓
Keyword / lexical scoring
   ↓
Combined ranking
   ↓
Best relevant chunks
```

Current scoring:

```python
combined_score = (
    0.80 * semantic_score
    +
    0.20 * keyword_score
)
```

This combines semantic similarity with keyword relevance.

---

## LLM Answer Generation

The LLM does not receive the entire ordinance.

Instead:

```text
User Question
      ↓
Retrieve relevant chunks
      ↓
Select top 5–8 chunks
      ↓
Send question + context to LLM
      ↓
Generate grounded answer
```

The Recommendation Agent is instructed to:

* Use only retrieved ordinance clauses, similar previous cases, DDPC minutes, and circulars.
* Cite synthetic previous cases by case id, date, clauses, and recorded decision.
* Preserve important numbers, forms, and conditions.
* Avoid hallucination and outside knowledge.
* Identify deficiencies from the question and retrieved context.
* Propose possible courses of action without making a final decision.
* Draft an initial resolution for human review.
* Format every answer with these exact headings:

```text
Relevant ordinance clauses
Similar previous cases (citing the synthetic data)
Identified deficiencies
Possible course of action
Initial draft resolution
```

If `GEMINI_API_KEY` is missing, the API process still starts. Live `/ask` answers and live minutes drafting require a key. Scheduler tools and minutes fallback drafting work without it.

---

## Grounding and Reliability

```text
Official Ordinance
       ↓
Retrieved Context
       ↓
LLM
       ↓
Answer based ONLY on Context
```

If the retrieved content does not contain enough information, the system should not guess.

---

## Human-in-the-Loop Governance

The AI can:

```text
Retrieve
Analyze
Summarize
Classify
Recommend
Draft
Detect relevant rules
Prepare workflow artifacts
```

Authorized officials remain responsible for:

```text
Review
Verification
Approval
Rejection
Final Academic Decision
```

---

## Planned Academic Modules

### Undergraduate

* DUGC processes
* Registration
* Academic performance
* Degree requirements
* Minor programmes
* Honours
* Academic deficiencies

### Postgraduate

* DMPC-related processes
* Academic requirements
* Registration
* Thesis-related workflows

### Ph.D. (this repository)

* DDPC processes
* Comprehensive Examination
* Supervisor allocation
* Thesis extension
* Research-related workflows
* Academic requirements
* Progress-related workflows

---

## Core File Purpose

| Path | Purpose |
| ---- | ------- |
| `ai/ingestion/pdf_parser.py` | Extract page text from the Doctoral ordinance PDF. |
| `ai/ingestion/structure_parser.py` | Detect 18 sections, clauses, DP/GL forms; join split heading lines. |
| `ai/ingestion/intelligent_chunker.py` | Build retrieval chunks from structure + page text. |
| `ai/ingestion/synthetic_data_generator.py` | Gemini-backed synthetic DDPC cases / minutes / circulars. |
| `ai/ingestion/synthetic_scheduler_data.py` | Mock CSE committees (DUGC / DMPC / DDPC) and calendar block-list. |
| `ai/embeddings/embedding_config.py` | Embedding model name, paths, batch size. |
| `ai/embeddings/embedding_generator.py` | Write `phd_ordinance_embeddings.json`. |
| `backend/ingest_knowledge_base.py` | Load ordinance + synthetic JSON into PostgreSQL/pgvector. |
| `backend/main.py` | FastAPI app, CORS, `/ask` + `/schedule/*` routers. |
| `backend/api/routes.py` | `POST /ask` Recommendation Agent endpoint. |
| `backend/api/scheduler_routes.py` | Propose / approve meetings; minutes generate with Gemini fallback. |
| `backend/llm/gemini_client.py` | Gemini client; starts without a key, fails only on live generate. |
| `backend/rag/qa_pipeline.py` | Retrieve mixed evidence and generate the five-heading draft. |
| `backend/rag/guardrails.py` | Scope checks (doctoral / DDPC vocabulary). |
| `backend/rag/conversation_manager.py` | Follow-up rewrite (Ph.D. CPI example). |
| `backend/rag/source_formatter.py` | Source citation labels. |
| `backend/retrieval/semantic_search.py` | Hybrid pgvector + keyword retrieval. |
| `backend/agents/scheduling_tools.py` | Five Python tools; default slots 09:30–16:30. |
| `backend/agents/scheduling_agent.py` | Gemini function-calling wrapper + deterministic fallback. |
| `frontend/index.html` | Chat UI titled Doctoral Programmes Ordinance Assistant. |
| `frontend/app.js` | Posts to `/ask`; default committee `DDPC`, range `2026-09-14 to 2026-09-25`. |
| `frontend/style.css` | Chat and meeting-button styles. |
| `documents/phd/Ordinances_for_Doctoral_Programm2023.pdf` | Authoritative RAG source. |
| `documents/phd/processed/*.json` | Pages, structure, chunks, embeddings, synthetic KB. |
| `documents/scheduler/processed/` | Committee DB, calendar restrictions, mock `.ics` / minutes. |

---

## Project Structure

```text
DepartmentAI-Replace-2026/
│
├── ai/
│   ├── ingestion/
│   │   ├── pdf_parser.py
│   │   ├── structure_parser.py
│   │   ├── intelligent_chunker.py
│   │   ├── synthetic_data_generator.py
│   │   └── synthetic_scheduler_data.py
│   └── embeddings/
│       ├── embedding_generator.py
│       └── embedding_config.py
│
├── documents/
│   ├── phd/
│   │   ├── Ordinances_for_Doctoral_Programm2023.pdf
│   │   └── processed/
│   │       ├── phd_ordinance_pages.json
│   │       ├── phd_ordinance_text.txt
│   │       ├── phd_ordinance_structure.json
│   │       ├── phd_ordinance_chunks.json
│   │       ├── phd_ordinance_embeddings.json
│   │       ├── synthetic_past_cases.json
│   │       ├── synthetic_ddpc_minutes.json
│   │       └── synthetic_circulars.json
│   ├── calendar/
│   │   └── academic_calendar_rotated_compressed.pdf
│   └── scheduler/processed/
│       ├── academic_calendar.txt
│       ├── academic_calendar_restrictions.json
│       ├── synthetic_committee_db.json
│       └── PROP-*_minutes.md
│
├── backend/
│   ├── ingest_knowledge_base.py
│   ├── main.py
│   ├── api/
│   │   ├── routes.py
│   │   └── scheduler_routes.py
│   ├── agents/
│   │   ├── scheduling_agent.py
│   │   └── scheduling_tools.py
│   ├── llm/
│   │   └── gemini_client.py
│   ├── rag/
│   │   ├── qa_pipeline.py
│   │   ├── guardrails.py
│   │   ├── conversation_manager.py
│   │   └── source_formatter.py
│   └── retrieval/
│       └── semantic_search.py
│
├── frontend/
│   ├── index.html
│   ├── app.js
│   └── style.css
│
├── .env.example
├── requirements.txt
├── .gitignore
├── BUILD_HISTORY.md
├── SCHEDULING_README.md
├── SCHEDULING_BUILD_HISTORY.md
└── README.md
```

Do not put scheduler JSON under `documents/phd/processed/`. That directory is the RAG knowledge base.

---

## Security

Sensitive credentials must never be committed.

The repository excludes:

```text
.env
API keys
Database passwords
Virtual environments
Local databases
Log files
```

Example placeholders (copy from `.env.example`):

```env
DEPARTMENTAI_DB_PASSWORD=your_database_password_here
GEMINI_API_KEY=your_api_key_here
```

Never commit the actual API key.

---

## Testing Strategy

DepartmentAI will be evaluated using representative doctoral questions.

Initial test questions include:

```text
1. What are the requirements for earning a Ph.D. degree?

2. What is the minimum SPI/CPI requirement for continuing in the programme?

3. What are the eligibility requirements for admission to the Ph.D. programme?

4. What happens if a scholar fails the Comprehensive Examination twice?

5. What is the maximum duration allowed for the Ph.D. programme?

6. What is the process for change or addition of Thesis Supervisor?

7. What are the rules regarding semester leave?

8. What is the procedure for thesis submission after Open Seminar?

9. What are the requirements for the award of the degree?

10. What is the constitution of DDPC / SDPC / SRC?
```

The primary evaluation criterion is:

> **Does the final answer correctly answer the question using only the official Doctoral Ordinance content?**

---

## Current Project Status

| Component                        | Status         |
| -------------------------------- | -------------- |
| Project structure                | Complete       |
| PDF parsing                      | Complete       |
| Structure parsing                | Complete       |
| Clause detection                 | Complete       |
| Intelligent chunking             | Complete       |
| 143 knowledge chunks             | Complete       |
| Embedding generation             | Local model required |
| PostgreSQL + pgvector ingestion  | Local DB required |
| Semantic retrieval               | Code complete  |
| LLM recommendation generation    | Code complete (needs `GEMINI_API_KEY`) |
| Draft-resolution formatting      | Complete       |
| Synthetic past cases / minutes / circulars | Complete |
| Mixed retrieval (4 chunk types)  | Complete       |
| FastAPI integration              | Complete       |
| DDPC scheduling defaults         | Complete       |
| Minutes generate fallback        | Complete       |
| Multilingual chatbot             | Planned        |

---

## Design Principles

1. **Accuracy First** — Correct academic information over unnecessary complexity.
2. **Grounded AI** — LLMs answer using authoritative institutional sources.
3. **Human Oversight** — AI assists officials but does not replace institutional decision-making.
4. **Incremental Development** — Complex infrastructure only when required.
5. **Privacy and Security** — Credentials stay in `.env`.
6. **Traceability** — Answers should trace to document / section / clause / page / chunk.
7. **Maintainability** — Same layout as the UG and M.Tech. modules.

---

## Getting Started (from scratch)

Run every command from the repository root.

### 1. Create a virtual environment

```bash
python -m venv venv
```

Linux / macOS:

```bash
source venv/bin/activate
```

Windows:

```powershell
.\venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

`requirements.txt` lists `google-genai` (not `google-generativeai`).

### 3. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill:

```env
DEPARTMENTAI_DB_PASSWORD=your_database_password_here
GEMINI_API_KEY=your_api_key_here
```

`GEMINI_API_KEY` is required for live `/ask` answers and for `synthetic_data_generator.py`. The scheduler and minutes fallback work without it. The API process starts even if the key is missing.

### 4. Build the ordinance knowledge files (offline)

```bash
python ai/ingestion/pdf_parser.py
python ai/ingestion/structure_parser.py
python ai/ingestion/intelligent_chunker.py
```

Expected console (structure parser):

```text
PDF pages          : 75
Sections detected  : 18
Clauses detected   : 73
Form records       : 26
Unique form IDs    : 26
Validation         : PASS
```

Expected console (chunker):

```text
Total chunks       : 143
Ordinance chunks   : 117
Form chunks        : 26
Unique clauses     : 73
Unique forms       : 26
Validation         : PASS
```

Generate embeddings (downloads the sentence-transformer model on first run):

```bash
python ai/embeddings/embedding_generator.py
```

Optional — regenerate synthetic DDPC cases / minutes / circulars (needs `GEMINI_API_KEY`). Pre-written JSON already exists under `documents/phd/processed/`:

```bash
python ai/ingestion/synthetic_data_generator.py
```

Generate scheduler data:

```bash
python ai/ingestion/synthetic_scheduler_data.py
```

Expected:

```text
Committees           : {'DUGC': 7, 'DMPC': 6, 'DDPC': 7}
```

### 5. Start PostgreSQL and enable pgvector

Ensure PostgreSQL is running and the `departmentai` database exists.

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

Schema expected by `backend/ingest_knowledge_base.py`:

```sql
CREATE TABLE documents (
    id              SERIAL PRIMARY KEY,
    title           TEXT,
    file_name       TEXT,
    document_type   TEXT,
    version         TEXT,
    total_pages     INTEGER,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE sections (
    id              SERIAL PRIMARY KEY,
    document_id     INTEGER REFERENCES documents(id),
    section_number  TEXT,
    title           TEXT,
    start_page      INTEGER,
    end_page        INTEGER,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE knowledge_chunks (
    id              SERIAL PRIMARY KEY,
    document_id     INTEGER REFERENCES documents(id),
    section_id      INTEGER REFERENCES sections(id),
    chunk_index     INTEGER,
    chunk_type      TEXT,
    clause_number   TEXT,
    chunk_text      TEXT,
    page_start      INTEGER,
    page_end        INTEGER,
    form_id         TEXT,
    metadata        JSONB,
    embedding       vector(384),
    created_at      TIMESTAMP DEFAULT NOW()
);
```

Insert a `documents` row for:

```text
file_name     = Ordinances_for_Doctoral_Programm2023.pdf
document_type = Doctoral Ordinance
total_pages   = 75
```

Insert the 18 section rows for that document.

### 6. Load the knowledge base

```bash
python backend/ingest_knowledge_base.py --programme phd --replace
python backend/ingest_knowledge_base.py --programme mtech --replace
python backend/ingest_knowledge_base.py --programme ug --replace
```

Or ingest all three:

```bash
python backend/ingest_knowledge_base.py --replace
```

Other options:

```bash
python backend/ingest_knowledge_base.py --synthetic-only --replace
python backend/ingest_knowledge_base.py --skip-synthetic --replace
python backend/ingest_knowledge_base.py --programme ug --synthetic-only --replace
```

### 7. Run the API

From the repository root (so `backend` is importable):

```bash
uvicorn backend.main:app --reload
```

Default URL: `http://127.0.0.1:8000`.

### 8. Serve the frontend

CORS allows `http://127.0.0.1:5500` and `http://localhost:5500`.

```bash
cd frontend
python -m http.server 5500
```

Open `http://127.0.0.1:5500`.

Try a DDPC-style prompt such as:

```text
A full-time Ph.D. scholar failed the first Comprehensive Examination. Form DP-09 is on record. Prepare a DDPC recommendation.
```

The agent should return the five draft-resolution headings. After a draft resolution, the UI offers **Propose DDPC Meeting** (`committee_name: DDPC`, `date_range: 2026-09-14 to 2026-09-25`).

---

## Recommendation Agent Knowledge Types

| `chunk_type`         | Source                                              | Real / synthetic |
| -------------------- | --------------------------------------------------- | ---------------- |
| `ordinance_clause`   | Doctoral ordinance body                             | Real             |
| `form`               | DP / GL annexure forms                              | Real             |
| `past_case`          | `synthetic_past_cases.json`                         | Synthetic        |
| `meeting_minute`     | `synthetic_ddpc_minutes.json`                       | Synthetic        |
| `circular`           | `synthetic_circulars.json`                          | Synthetic        |

Synthetic records are demonstration stand-ins for previous minutes, office orders, and decided cases. The Recommendation Agent is instructed to cite them as synthetic demonstration records.

Typical synthetic case themes: Comprehensive Examination failures, thesis extensions, supervisor allocation / change.

---

## Meeting Scheduling Agent

Documented in `SCHEDULING_README.md` and `SCHEDULING_BUILD_HISTORY.md`.

Default doctoral committee is **DDPC** (Departmental Doctoral Programme Committee), matching Clause 1.3 of the ordinance. DUGC and DMPC remain valid scheduler committees so the shared architecture is unchanged.

Default candidate slot starts: `09:30`, `10:30`, `11:30`, `14:30`, `15:30`, `16:30`.

Mock CSE DDPC roster (fictitious):

* HoD: Prof. Leela Krishnan
* Convener: Dr. Sameer Qureshi
* Member Secretary: Dr. Tanvi Kapoor
* Members include Nandini Rao, Harish Talwar, Aisha Rahman, Gautam Deshpande, Pooja Bhatia, Rajan Khurana, Yusuf Pathan, Arvind Menon, Ritu Banerjee (roles vary by committee)

---

## Disclaimer

DepartmentAI is an **assistive academic information and automation system**.

Information retrieved or generated by the system should be verified against the latest official institutional documents before being used for formal academic or administrative decisions.

The system does not replace authorized institutional officials or official university procedures.

---

## Project Status

**MNNIT Department Portal (B.Tech. / M.Tech. / Ph.D.) is actively under development.**

Current focus:

> **Building a reliable RAG-based academic knowledge assistant for Bachelors, Masters, and Doctoral ordinances and DUGC / DMPC / DDPC processes.**

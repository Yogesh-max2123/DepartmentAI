# BUILD HISTORY / HANDOFF LOG

This document records **everything that was created and changed** while building the
`DepartmentAI-MTech` repository. It is written so that the work can be continued by
another developer or AI assistant without starting from scratch.

---

## 1. Context

The parent project **DepartmentAI: Agentic Academic Governance and Administrative
Intelligence System** consists of two major modules:

* **Module I** — Automation of UG, PG and Ph.D. academic processes (DUGC / DMPC / DDPC).
* **Module II** — Faculty profile and institutional reporting automation.

A teammate had already built the **UG part (DUGC)** — the OCR/document-ingestion,
chunking, embedding, retrieval and RAG pipeline for the *UG Ordinance*. That work lives
in the original repository:

```
/workspace/DepartmentAI-Agentic-Academic-Governance/
```

The task here was to build the **M.Tech. part (DMPC)** as a **separate, independent
repository** that follows **exactly the same structure, file layout, techniques and
format** as the UG work, but using the **Ordinances for Masters' Programmes 2023** PDF as
its authoritative source.

* The original UG repository was **not modified**.
* The new repository is:

```
/workspace/DepartmentAI-MTech/
```

---

## 2. Source from the UG Repository (Reference Only)

Files studied and mirrored from `DepartmentAI-Agentic-Academic-Governance`:

| UG file                                             | Purpose                                                |
| --------------------------------------------------- | ------------------------------------------------------ |
| `ai/ingestion/pdf_parser.py`                        | PyMuPDF page-by-page text extraction                   |
| `ai/ingestion/structure_parser.py`                  | Section / clause / form detection                      |
| `ai/ingestion/intelligent_chunker.py`               | Structure-aware clause-based chunking                  |
| `ai/embeddings/embedding_config.py`                 | Embedding model + generation settings                  |
| `ai/embeddings/embedding_generator.py`              | Vector generation                                      |
| `backend/ingest_knowledge_base.py`                  | Load chunks + embeddings into PostgreSQL/pgvector      |
| `backend/retrieval/semantic_search.py`              | Hybrid pgvector + keyword reranked retrieval           |
| `backend/rag/qa_pipeline.py`                        | Retrieve → build context → generate answer             |
| `backend/rag/guardrails.py`                         | Scope guardrails + human-in-the-loop decision refusal  |
| `backend/rag/conversation_manager.py`               | Follow-up question resolution                          |
| `backend/rag/source_formatter.py`                   | Source citation formatting                             |
| `backend/llm/gemini_client.py`                      | Gemini API grounded answer generation                  |
| `backend/main.py`, `backend/api/routes.py`          | FastAPI app + `/ask` endpoint                          |
| `frontend/index.html`, `app.js`, `style.css`        | Chat UI                                                |
| `tests/*`                                           | Guardrail / QA / Gemini tests                          |
| `README.md`, `requirements.txt`, `.gitignore`       | Project documentation and configuration                |

The UG pipeline produced:

```
68 clauses, 14 physical form records, 13 unique form IDs
232 ordinance chunks + 14 form chunks = 246 total chunks
246 × 384 embeddings
```

---

## 3. Source PDF Used for the M.Tech. Module

```
/workspace/Ordinances_for_Masters_Programme2023.pdf
```

Copied into the new repo as:

```
documents/mtech/Ordinances for Masters Programme 2023.pdf
```

* 56 physical PDF pages
* Approved by the Board of Governors, 73rd meeting, August 10, 2023, Resolution 73.13 (A)

### Page layout discovered

| Pages   | Content                                                        |
| ------- | -------------------------------------------------------------- |
| 1–8     | Front matter: cover, vision/mission, TOC, preamble, nomenclature |
| 9–38    | Ordinance body: Sections 1 to 16                                |
| 39–50   | Annexure forms: MP-01 to MP-10 (MP-09a + MP-09b) and GL-1        |
| 51–56   | Blank "Notes" pages                                             |

---

## 4. Adaptations Made vs the UG Module

The M.Tech. ordinance has a **different numbering scheme** than the UG ordinance, so the
constants and detection rules were adapted while keeping the identical code structure and
style.

| Aspect             | UG module                                | M.Tech. module                                                  |
| ------------------ | ---------------------------------------- | --------------------------------------------------------------- |
| Page range (body)  | 9–27                                     | 9–38                                                            |
| Page range (forms) | 28–44                                    | 39–50                                                           |
| Notes pages        | 45–50                                    | 51–56                                                           |
| Sections           | 13                                       | 16                                                              |
| Clauses            | 68                                       | 65                                                              |
| Form prefix        | `BP-xx` (zero-padded)                    | `MP-xx` (zero-padded) and `GL-1`                                |
| Form records       | 14 (BP-11 appears twice)                 | 12 (MP-09 appears as MP-09a and MP-09b)                         |
| Unique form IDs    | 13                                       | 12                                                              |
| Total chunks       | 246                                      | 139 (127 clause + 12 form)                                      |
| Output filenames   | `ug_ordinance_*.json`                    | `mtech_ordinance_*.json`                                        |
| Chunk ID prefix    | `ug_` / `form_`                          | `mtech_` / `form_`                                              |

### Key structural fixes applied for the Masters' ordinance

1. **Section heading detection.** The Masters' ordinance uses numbered list items inside
   sections (e.g. `1. Master of Technology (M.Tech.)`) that look exactly like section
   headings. A `SECTION_HEADING_PREFIXES` map was added so only the 16 real section
   headings (`1. INTRODUCTION`, `3. ADMISSION`, …) are detected.
2. **Form ID normalisation.** `GL-1` is not zero-padded (`MP-01` is). `normalize_form_id`
   handles both.
3. **MP-09a / MP-09b.** These are two distinct physical forms on separate pages and are
   treated as two form records (`MP-09a`, `MP-09b`).
4. **Form reference detection.** The body lines are joined before matching so that
   references split across a line break (e.g. `(Form: MP-` / `03)`) are still found, and a
   false `MP-10a` suffix match was eliminated.
5. **Programme penalty in keyword scoring.** The UG penalty for branch-specific terms
   (ECE/CSE/…) was replaced with Masters' programme terms (M.Tech./MBA/MCA/M.Sc./MSW).
6. **Guardrail keywords.** Extended with Masters-specific vocabulary (thesis, supervisor,
   DMPC, SMPC, stipend, fellowship, plagiarism, ACD, etc.).
7. **Form `form_id` on ingestion.** The ingestion script now uses a chunk's own `form_id`
   (for form chunks) and falls back to `forms_referenced[0]` (for clause chunks), so the
   `knowledge_chunks.form_id` column is populated for both.
8. **Conversation resolver example.** Changed from the B.Tech Honours example to an
   M.Tech. degree example.

---

## 5. Files Created in `DepartmentAI-MTech`

```
DepartmentAI-MTech/
├── .gitignore
├── .env.example
├── requirements.txt
├── README.md
├── BUILD_HISTORY.md
├── ai/
│   ├── ingestion/
│   │   ├── pdf_parser.py
│   │   ├── structure_parser.py
│   │   └── intelligent_chunker.py
│   └── embeddings/
│       ├── embedding_config.py
│       └── embedding_generator.py
├── backend/
│   ├── __init__.py
│   ├── main.py
│   ├── ingest_knowledge_base.py
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py
│   ├── llm/
│   │   ├── __init__.py
│   │   └── gemini_client.py
│   ├── rag/
│   │   ├── __init__.py
│   │   ├── qa_pipeline.py
│   │   ├── guardrails.py
│   │   ├── conversation_manager.py
│   │   └── source_formatter.py
│   └── retrieval/
│       └── semantic_search.py
├── documents/
│   └── mtech/
│       ├── Ordinances for Masters Programme 2023.pdf
│       └── processed/
│           ├── mtech_ordinance_pages.json
│           ├── mtech_ordinance_text.txt
│           ├── mtech_ordinance_structure.json
│           ├── mtech_ordinance_chunks.json
│           └── mtech_ordinance_embeddings.json
├── frontend/
│   ├── index.html
│   ├── app.js
│   └── style.css
└── tests/
    ├── __init__.py
    ├── test_gemini_api.py
    ├── test_gemini_client.py
    ├── test_guardrails.py
    ├── test_qa_pipeline.py
    └── diagnose_mtech_chunks.py
```

---

## 6. What Was Actually Run and Verified

All offline (non-database) pipeline stages were executed successfully during the build.

| Step | Command                                             | Result |
| ---- | --------------------------------------------------- | ------ |
| 1    | `python ai/ingestion/pdf_parser.py`                 | 56 pages extracted, ~74,027 characters, JSON + TXT written |
| 2    | `python ai/ingestion/structure_parser.py`           | 16 sections, 65 clauses, 12 form records, 12 unique form IDs, validation **PASS** |
| 3    | `python ai/ingestion/intelligent_chunker.py`        | 127 clause + 12 form = **139 chunks**, validation **PASS** (5 chunks > 2400 chars, same tolerated warning class as UG) |
| 4    | `python ai/embeddings/embedding_generator.py`       | **139 × 384** embeddings generated and validated (count / dimension / NaN / Infinity all PASS) |

> **Note on running tests:** the tests import the `backend` package, so they must be run
> from the repository root as a module, e.g. `python -m tests.test_guardrails`. The
> guardrail tests were executed this way and **all passed**. This is the same invocation
> pattern used by the UG module.

### Structure parser validation output

```
PDF pages          : 56
Sections detected  : 16
Clauses detected   : 65
Form records       : 12
Unique form IDs    : 12
Form references    : 10
Validation         : PASS
```

### Chunker validation output

```
Total chunks       : 139
Ordinance chunks   : 127
Form chunks        : 12
Unique clauses     : 65
Unique forms       : 12
Average characters : 1448.96
Maximum characters : 2511
Validation         : PASS
```

### Embedding validation output

```
Chunks embedded    : 139
Vector dimension   : 384
Model              : sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
Validation         : PASS
```

---

## 7. What Was NOT Run (Environment Limitations)

The build/execution sandbox used for this task had the following constraints, so two
stages could **not** be executed here. They are expected to run unchanged on the
developer's own machine.

1. **PostgreSQL ingestion** (`backend/ingest_knowledge_base.py`) and the interactive
   retrieval / QA pipelines require a running PostgreSQL 18 instance with the `pgvector`
   extension, the `departmentai` database, the `documents` / `sections` /
   `knowledge_chunks` tables, and a `documents` row for the Masters' ordinance PDF. These
   are external to the repository (same as the UG module).
2. **Live Gemini API calls** (`backend/llm/gemini_client.py`, `tests/test_gemini_api.py`,
   `tests/test_gemini_client.py`) require a real `GEMINI_API_KEY`.

No database credentials or API keys were hard-coded anywhere. The `.env.example` file
contains only placeholders.

---

## 8. Environment Variables (Placeholders Only)

`.env.example` contains:

```env
DEPARTMENTAI_DB_PASSWORD=your_database_password_here
GEMINI_API_KEY=your_api_key_here
```

To run locally:

```bash
cp .env.example .env
# then edit .env and put your real values in
```

`app.js` posts to `http://127.0.0.1:8000/ask` (the FastAPI default from
`backend/main.py`), exactly like the UG module.

---

## 9. How to Reproduce End-to-End on a Developer Machine

```bash
# 1. Create + activate the environment
python -m venv venv
.\venv\Scripts\Activate.ps1        # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the offline knowledge-base pipeline
python ai/ingestion/pdf_parser.py
python ai/ingestion/structure_parser.py
python ai/ingestion/intelligent_chunker.py
python ai/embeddings/embedding_generator.py

# 4. Configure .env (copy from .env.example)

# 5. Create the database, enable pgvector, create the schema,
#    and insert a documents row for:
#      file_name = "Ordinances for Masters Programme 2023.pdf"
#      document_type = "Masters' Ordinance"

# 6. Insert the 16 section rows for the document.

# 7. Load the knowledge base
python backend/ingest_knowledge_base.py

# 8. Start the API
uvicorn backend.main:app --reload

# 9. Open frontend/index.html (served on port 5500 for CORS)
```

### Database schema expected by the ingestion script

The ingestion script uses the **same schema as the UG module**:

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

---

## 10. Final Delivered Counts (for reference / consistency checks)

| Metric                     | Value                |
| -------------------------- | -------------------- |
| PDF pages                  | 56                   |
| Ordinance sections         | 16                   |
| Ordinance clauses          | 65                   |
| Form records               | 12                   |
| Unique form IDs            | 12                   |
| Ordinance clause chunks    | 127                  |
| Form chunks                | 12                   |
| Total chunks               | 139                  |
| Embedding dimension        | 384                  |
| Embeddings                 | 139 × 384            |

Masters' forms detected: `MP-01 MP-02 MP-03 MP-04 MP-05 MP-06 MP-07 MP-08 MP-09a MP-09b
MP-10 GL-1`.

Sections detected: `1..16` (INTRODUCTION → WAIVER OF REQUIREMENTS IN SPECIAL CASES).

---

## 11. Remaining Work / Next Steps

* [ ] Create the PostgreSQL schema + `documents` row + 16 `sections` rows on the target machine.
* [ ] Run `backend/ingest_knowledge_base.py` and confirm 139 rows inserted.
* [ ] Run `backend/retrieval/semantic_search.py` interactively on the 10 test questions in the README.
* [ ] Put a real `GEMINI_API_KEY` in `.env` and run `tests/test_qa_pipeline.py` for grounded answers.
* [ ] Tune chunking / retrieval weights if retrieval quality needs improvement.
* [ ] Optional: metadata correction and traceability validation (Phase 9).
* [ ] Optional: add the M.Tech. module to the unified DUGC/DMPC/DDPC frontend.

---

## 12. Notes on Repository Isolation

* The original `DepartmentAI-Agentic-Academic-Governance` repository was **read only**.
* No files were added, edited, or deleted inside it.
* `DepartmentAI-MTech` is a fully self-contained repository with its own PDF copy,
  processed artifacts, source code, frontend, tests and documentation.

---

## 13. Deliverable

The complete, ready-to-use deliverable is the zipped repository:

```
/workspace/DepartmentAI-MTech.zip
```

It contains the whole `DepartmentAI-MTech/` folder (including the `.git` directory, so
the initial commit is preserved). Unzip it anywhere and open the folder in VS Code.

The zipped repository was initialised as a git repository with one commit:

```
feat(mtech): add Masters' Programmes ordinance RAG knowledge base module
```

`.gitignore` already excludes `venv/`, `.env`, `__pycache__/`, logs, local databases and
ML caches, so only source, docs, the source PDF and the generated `processed/` JSON
artifacts are tracked (38 tracked files).

The generated `processed/` JSON artifacts are included in the zip so the knowledge base
can be inspected or ingested immediately without re-running the offline pipeline (though
re-running it reproduces the exact same counts).


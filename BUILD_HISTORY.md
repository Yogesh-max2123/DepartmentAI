# BUILD HISTORY / HANDOFF LOG

This document records **everything that was created and changed** while building the
`DepartmentAI-PhD` repository. It is written so that the work can be continued by
another developer or AI assistant without starting from scratch.

---

## 1. Context

The parent project **DepartmentAI: Agentic Academic Governance and Administrative
Intelligence System** consists of two major modules:

* **Module I** — Automation of UG, PG and Ph.D. academic processes (DUGC / DMPC / DDPC).
* **Module II** — Faculty profile and institutional reporting automation.

A teammate had already built the **UG part (DUGC)** and the **M.Tech. part (DMPC)** —
the OCR/document-ingestion, chunking, embedding, retrieval and RAG pipeline for the
*UG Ordinance* and the *Masters' Ordinance*. The M.Tech. work lives in:

```
/workspace/DepartmentAI-MTech-Copy/
```

The task here was to build the **Ph.D. part (DDPC)** as a **separate, independent
repository** that follows **exactly the same structure, file layout, techniques and
format** as the M.Tech. work, but using the **Ordinances for Doctoral Programmes 2023**
PDF as its authoritative source.

* The original UG and M.Tech. repositories were **not modified**.
* The new repository is:

```
/workspace/DepartmentAI-PhD/
```

---

## 2. Source from the M.Tech. Repository (Reference Only)

Files studied and mirrored from `DepartmentAI-MTech-Copy`:

| M.Tech. file                                        | Purpose                                                |
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

The M.Tech. pipeline produced:

```
65 clauses, 12 physical form records, 12 unique form IDs
127 ordinance chunks + 12 form chunks = 139 total chunks
139 × 384 embeddings
```

---

## 3. Source PDF Used for the Ph.D. Module

```
/workspace/Ordinances_for_Doctoral_Programm2023.pdf
```

Copied into the new repo as:

```
documents/phd/Ordinances for Doctoral Programme 2023.pdf
```

* 75 physical PDF pages
* Approved by the Board of Governors, 73rd meeting, August 10, 2023, Resolution 73.13 (A)

### Page layout discovered

| Pages   | Content                                                                 |
| ------- | ----------------------------------------------------------------------- |
| 1–8     | Front matter: cover, vision/mission, TOC, preamble, nomenclature        |
| 9–41    | Ordinance body: Sections 1 to 18                                        |
| 42–69   | Annexure forms: DP-01 to DP-24 (DP-12a + DP-12b) and GL-1               |
| 70–75   | Blank "Notes" pages                                                     |

---

## 4. Adaptations Made vs the M.Tech. Module

The Ph.D. ordinance has a **different numbering scheme** than the Masters' ordinance, so
the constants and detection rules were adapted while keeping the identical code structure
and style.

| Aspect             | M.Tech. module                                               | Ph.D. module                                                         |
| ------------------ | ------------------------------------------------------------ | -------------------------------------------------------------------- |
| Page range (body)  | 9–38                                                         | 9–41                                                                 |
| Page range (forms) | 39–50                                                        | 42–69                                                                |
| Notes pages        | 51–56                                                        | 70–75                                                                |
| Sections           | 16                                                           | 18                                                                   |
| Clauses            | 65                                                           | 73                                                                   |
| Form prefix        | `MP-xx` (zero-padded) and `GL-1`                             | `DP-xx` (zero-padded) and `GL-1`                                     |
| Form records       | 12 (MP-09 appears as MP-09a and MP-09b)                      | 26 (DP-12 appears as DP-12a and DP-12b; DP-17 and DP-19 span 2 pages) |
| Unique form IDs    | 12                                                           | 26                                                                   |
| Total chunks       | 139 (127 clause + 12 form)                                   | 143 (117 clause + 26 form)                                           |
| Output filenames   | `mtech_ordinance_*.json`                                     | `phd_ordinance_*.json`                                               |
| Chunk ID prefix    | `mtech_` / `form_`                                           | `phd_` / `form_`                                                     |

### Key structural fixes applied for the Doctoral ordinance

1. **Section heading detection.** The Doctoral ordinance uses numbered list items inside
   sections (e.g. `1. Initiate the process of Ph.D. admission.`) that look exactly like
   section headings. A `SECTION_HEADING_PREFIXES` map was added so only the 18 real
   section headings (`1. INTRODUCTION`, `3. ADMISSION`, …) are detected.
2. **Split headings.** Many section and clause identifiers are printed on one line
   (`2.`, `1.1`) with the title on the next line. `merge_split_lines()` joins these
   before matching.
3. **Form ID normalisation.** `GL-1` is not zero-padded (`DP-01` is). `normalize_form_id`
   handles both. The regex looks for `DP-xx` (not `MP-xx`) and also matches
   `DP-12 (a)` / `DP-12 (b)`.
4. **DP-12a / DP-12b.** These are two distinct physical forms on separate pages and are
   treated as two form records (`DP-12a`, `DP-12b`).
5. **Multi-page forms.** DP-17 (pages 59–60) and DP-19 (pages 62–63) each span two
   physical pages and are stored as a single form record with `end_page` after the
   continuation page.
6. **Form reference detection.** The body lines are joined before matching so that
   references split across a line break (e.g. `(Form: DP-` / `08)`) are still found.
7. **Programme penalty in keyword scoring.** The Masters' penalty for programme-specific
   terms (M.Tech./MBA/MCA/M.Sc./MSW) was replaced with Doctoral terms
   (Ph.D./phd/doctoral/doctorate).
8. **Guardrail keywords.** Extended with Ph.D.-specific vocabulary (doctoral, thesis
   defense, DDPC, SDPC, SRC, comprehensive, state-of-the-art, open seminar, examiner,
   etc.).
9. **Form `form_id` on ingestion.** The ingestion script now uses a chunk's own `form_id`
   (for form chunks) and falls back to `forms_referenced[0]` (for clause chunks), so the
   `knowledge_chunks.form_id` column is populated for both.
10. **Conversation resolver example.** Changed from the M.Tech. degree example to a
    Ph.D. degree example.

---

## 5. Files Created in `DepartmentAI-PhD`

```
DepartmentAI-PhD/
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
│   └── phd/
│       ├── Ordinances for Doctoral Programme 2023.pdf
│       └── processed/
│           ├── phd_ordinance_pages.json
│           ├── phd_ordinance_text.txt
│           ├── phd_ordinance_structure.json
│           ├── phd_ordinance_chunks.json
│           └── phd_ordinance_embeddings.json   (generated on developer machine)
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
    └── diagnose_phd_chunks.py
```

---

## 6. What Was Actually Run and Verified

All offline (non-database, non-embedding) pipeline stages were executed successfully
during the build.

| Step | Command                                             | Result |
| ---- | --------------------------------------------------- | ------ |
| 1    | `python ai/ingestion/pdf_parser.py`                 | 75 pages extracted, ~110,554 characters, JSON + TXT written |
| 2    | `python ai/ingestion/structure_parser.py`           | 18 sections, 73 clauses, 26 form records, 26 unique form IDs, validation **PASS** |
| 3    | `python ai/ingestion/intelligent_chunker.py`        | 117 clause + 26 form = **143 chunks**, validation **PASS** (6 chunks > 3200 chars, same tolerated warning class as UG/M.Tech.) |

> **Note on running tests:** the tests import the `backend` package, so they must be run
> from the repository root as a module, e.g. `python -m tests.test_guardrails`. The
> guardrail tests were executed this way and **all passed**. This is the same invocation
> pattern used by the UG and M.Tech. modules.

### Structure parser validation output

```
PDF pages          : 75
Sections detected  : 18
Clauses detected   : 73
Form records       : 26
Unique form IDs    : 26
Form references    : 24
Validation         : PASS
```

### Chunker validation output

```
Total chunks       : 143
Ordinance chunks   : 117
Form chunks        : 26
Unique clauses     : 73
Unique forms       : 26
Average characters : 2058.3
Maximum characters : 3533
Validation         : PASS
```

---

## 7. What Was NOT Run (Environment Limitations)

The build/execution sandbox used for this task had the following constraints, so two
stages could **not** be executed here. They are expected to run unchanged on the
developer's own machine.

1. **Embedding generation** (`ai/embeddings/embedding_generator.py`) requires
   `sentence-transformers` and a download of
   `paraphrase-multilingual-MiniLM-L12-v2`. Run it locally to produce
   `phd_ordinance_embeddings.json` (143 × 384).
2. **PostgreSQL ingestion** (`backend/ingest_knowledge_base.py`) and the interactive
   retrieval / QA pipelines require a running PostgreSQL 18 instance with the `pgvector`
   extension, the `departmentai` database, the `documents` / `sections` /
   `knowledge_chunks` tables, and a `documents` row for the Doctoral ordinance PDF. These
   are external to the repository (same as the UG and M.Tech. modules).
3. **Live Gemini API calls** (`backend/llm/gemini_client.py`, `tests/test_gemini_api.py`,
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
```

Then edit `.env` and put your real values in.

`app.js` posts to `http://127.0.0.1:8000/ask` (the FastAPI default from
`backend/main.py`), exactly like the UG and M.Tech. modules.

---

## 9. How to Reproduce End-to-End on a Developer Machine

```bash
python -m venv venv
```

```powershell
.\venv\Scripts\Activate.ps1
```

```bash
pip install -r requirements.txt
```

```bash
python ai/ingestion/pdf_parser.py
python ai/ingestion/structure_parser.py
python ai/ingestion/intelligent_chunker.py
python ai/embeddings/embedding_generator.py
```

Then:

1. Configure `.env` (copy from `.env.example`).
2. Create the database, enable pgvector, create the schema, and insert a `documents`
   row for:
   * `file_name = "Ordinances for Doctoral Programme 2023.pdf"`
   * `document_type = "Doctoral Ordinance"`
3. Insert the 18 section rows for the document.
4. Load the knowledge base:

```bash
python backend/ingest_knowledge_base.py
```

5. Start the API:

```bash
uvicorn backend.main:app --reload
```

6. Open `frontend/index.html` (served on port 5500 for CORS).

### Database schema expected by the ingestion script

The ingestion script uses the **same schema as the UG and M.Tech. modules**:

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
| PDF pages                  | 75                   |
| Ordinance sections         | 18                   |
| Ordinance clauses          | 73                   |
| Form records               | 26                   |
| Unique form IDs            | 26                   |
| Ordinance clause chunks    | 117                  |
| Form chunks                | 26                   |
| Total chunks               | 143                  |
| Embedding dimension        | 384                  |
| Embeddings                 | 143 × 384 (pending local generation) |

Doctoral forms detected: `DP-01 DP-02 DP-03 DP-04 DP-05 DP-06 DP-07 DP-08 DP-09 DP-10
DP-11 DP-12a DP-12b DP-13 DP-14 DP-15 DP-16 DP-17 DP-18 DP-19 DP-20 DP-21 DP-22 DP-23
DP-24 GL-1`.

Sections detected: `1..18` (INTRODUCTION → AMENDMENTS).

---

## 11. Remaining Work / Next Steps

* [ ] Run `python ai/embeddings/embedding_generator.py` to produce 143 × 384 embeddings.
* [ ] Create the PostgreSQL schema + `documents` row + 18 `sections` rows on the target machine.
* [ ] Run `backend/ingest_knowledge_base.py` and confirm 143 rows inserted.
* [ ] Run `backend/retrieval/semantic_search.py` interactively on the 10 test questions in the README.
* [ ] Put a real `GEMINI_API_KEY` in `.env` and run `tests/test_qa_pipeline.py` for grounded answers.
* [ ] Tune chunking / retrieval weights if retrieval quality needs improvement.
* [ ] Optional: metadata correction and traceability validation (Phase 9).
* [ ] Optional: add the Ph.D. module to the unified DUGC/DMPC/DDPC frontend.

---

## 12. Notes on Repository Isolation

* The original `DepartmentAI-MTech-Copy` repository was **read only**.
* No files were added, edited, or deleted inside it.
* `DepartmentAI-PhD` is a fully self-contained repository with its own PDF copy,
  processed artifacts, source code, frontend, tests and documentation.

---

## 13. Deliverable

The complete, ready-to-use deliverable is the zipped repository:

```
/workspace/DepartmentAI-PhD.zip
```

It contains the whole `DepartmentAI-PhD/` folder. Unzip it anywhere and open the folder
in VS Code.

`.gitignore` already excludes `venv/`, `.env`, `__pycache__/`, logs, local databases and
ML caches, so only source, docs, the source PDF and the generated `processed/` JSON
artifacts are tracked.

The generated `processed/` JSON artifacts (`pages`, `text`, `structure`, `chunks`) are
included in the zip so the knowledge base can be inspected immediately without re-running
the offline pipeline (though re-running it reproduces the exact same counts). Embeddings
must be generated on the developer machine because the embedding model was not available
in the build sandbox.

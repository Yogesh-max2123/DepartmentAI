# BUILD HISTORY / HANDOFF LOG

This document records **everything that was created and changed** while building the
Ph.D. (DDPC) module in `DepartmentAI-Replace-2026`. It is written so that the work
can be continued by another developer or AI assistant without starting from scratch.

---

## 1. Context

The parent project **DepartmentAI: Agentic Academic Governance and Administrative
Intelligence System** consists of two major modules:

* **Module I** — Automation of UG, PG and Ph.D. academic processes (DUGC / DMPC / DDPC).
* **Module II** — Faculty profile and institutional reporting automation.

A teammate had already built the **UG part (DUGC)** and the **M.Tech. part (DMPC)**
as separate repositories with the same architecture.

The task here was to **replicate the existing M.Tech. DepartmentAI system for the
Ph.D. domain** with the same architecture, stack, UI, FastAPI routing, and vanilla JS.

Constraints:

* Keep exact project architecture, file layout, UI, FastAPI routing, and vanilla JS.
* Replace all M.Tech. references with Ph.D.
* RAG must use `Ordinances_for_Doctoral_Programm2023.pdf`.
* Committee DMPC → DDPC (Departmental Doctoral Programme Committee). DPGC was
  allowed as an example; the ordinance Clause 1.3 uses DDPC, so DDPC is the default.
* New mock JSON for Ph.D. cases (comprehensive exam failures, thesis extensions,
  supervisor allocation).
* New mock professors, roles (Convener, HoD, Member Secretary), emails, and
  distinct default meeting slots.
* Thoroughly update `README.md` and `BUILD_HISTORY.md`, including a from-scratch
  local run guide.

The original UG / M.Tech. repositories were not modified. Work is in:

```
/workspace/DepartmentAI-Replace-2026/
```

---

## 2. Source from the M.Tech. Repository (Reference Only)

The extracted M.Tech. tree at `/workspace/DepartmentAI-Replace-2026` was the
starting point. Files studied and domain-adapted:

| File                                                | Purpose                                                |
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
| `backend/api/scheduler_routes.py`                   | `/schedule/*` + minutes generate                       |
| `frontend/index.html`, `app.js`, `style.css`        | Chat UI                                                |
| `README.md`, `requirements.txt`, `.env.example`     | Project documentation and configuration                |

The original M.Tech. KB under `documents/mtech/` was missing from the extracted
tree, so Ph.D. files were rebuilt under `documents/phd/`.

---

## 3. Source PDF Used for the Ph.D. Module

```
/workspace/Ordinances_for_Doctoral_Programm2023.pdf
```

Copied into the repo as:

```
documents/phd/Ordinances_for_Doctoral_Programm2023.pdf
```

* 75 physical PDF pages
* Title: Ordinances for Doctoral Programmes
* Institute: Motilal Nehru National Institute of Technology Allahabad
* Approved by the Board of Governors, 73rd meeting, August 10, 2023, Resolution 73.13 (A)

### Page layout discovered

| Pages   | Content                                                        |
| ------- | -------------------------------------------------------------- |
| 1–8     | Front matter: cover, vision/mission, TOC, preamble, nomenclature |
| 9–41    | Ordinance body: Sections 1 to 18                               |
| 42–69   | Annexure forms: DP-01 to DP-24 (DP-12a + DP-12b) and GL-1      |
| 70–75   | Blank "Notes" pages                                            |

---

## 4. Adaptations Made vs the M.Tech. Module

The Doctoral ordinance has a **different numbering scheme** than the Masters'
ordinance, so the constants and detection rules were adapted while keeping the
identical code structure and style.

| Aspect             | M.Tech. module                                               | Ph.D. module                                                       |
| ------------------ | ------------------------------------------------------------ | ------------------------------------------------------------------ |
| Page range (body)  | 9–38                                                         | 9–41                                                               |
| Page range (forms) | 39–50                                                        | 42–69                                                              |
| Notes pages        | 51–56                                                        | 70–75                                                              |
| Sections           | 16                                                           | 18                                                                 |
| Clauses            | 65                                                           | 73                                                                 |
| Form prefix        | `MP-xx` and `GL-1`                                           | `DP-xx` (zero-padded) and `GL-1`                                   |
| Form records       | 12 (MP-09a / MP-09b)                                         | 26 (DP-12a / DP-12b; DP-17 spans two pages, only start page stored)|
| Unique form IDs    | 12                                                           | 26                                                                 |
| Total chunks       | 139 (127 clause + 12 form)                                   | 143 (117 clause + 26 form)                                         |
| Output filenames   | `mtech_ordinance_*.json`                                     | `phd_ordinance_*.json`                                             |
| Chunk ID prefix    | `mtech_` / `form_`                                           | `phd_` / `form_`                                                   |
| Default committee  | DMPC                                                         | DDPC                                                               |
| Default date range | `2026-09-07 to 2026-09-18`                                   | `2026-09-14 to 2026-09-25`                                         |
| Slot starts        | 09:00 / 10:00 / 11:00 / 12:00 / 14:00 / 15:00 / 16:00        | 09:30 / 10:30 / 11:30 / 14:30 / 15:30 / 16:30                      |

### Key structural fixes applied for the Doctoral ordinance

1. **Split heading lines.** PyMuPDF often emits `2.` on one line and
   `ACADEMIC SESSION (AS)` on the next. `logical_lines()` in
   `structure_parser.py` joins a lone section/clause number with the following
   title line. Without this, only sections 1, 8 and 9 were detected.
2. **Section heading detection.** `SECTION_HEADING_PREFIXES` maps the 18 real
   headings (`1. INTRODUCTION`, `9. COMPREHENSIVE EXAMINATION`, …) so numbered
   list items inside a section are rejected.
3. **Form ID normalisation.** `GL-1` is not zero-padded (`DP-01` is).
   `normalize_form_id` handles both. `DP-12(a)` / `DP-12(b)` become `DP-12a` /
   `DP-12b`.
4. **Form page map.** Physical annexure pages 42–69 are mapped in
   `FORM_PAGE_IDS`. Pages 60 and 63 are continuations (DP-17 / DP-19) and are
   not given a second form id.
5. **Guardrail keywords.** Extended with doctoral vocabulary (thesis,
   supervisor, comprehensive, SRC, DDPC, SDPC, IDSC, DDSC, fellowship,
   plagiarism, ACD, open seminar, state-of-the-art).
6. **Conversation resolver example.** Changed from the M.Tech. degree example
   to a Ph.D. CPI / Comprehensive Examination example.
7. **Gemini client start-up.** `gemini_client.py` no longer raises at import
   if `GEMINI_API_KEY` is missing. Live `generate_text` still requires a key.
8. **Minutes generate fallback.** `POST /minutes/generate` no longer imports
   `google.generativeai`. It uses `backend.llm.gemini_client.generate_text`,
   then `google.genai`, then a deterministic DDPC minutes body.

---

## 5. Files in `DepartmentAI-Replace-2026`

```
DepartmentAI-Replace-2026/
├── .gitignore
├── .env.example
├── requirements.txt
├── README.md
├── BUILD_HISTORY.md
├── SCHEDULING_README.md
├── SCHEDULING_BUILD_HISTORY.md
├── ai/
│   ├── ingestion/
│   │   ├── pdf_parser.py
│   │   ├── structure_parser.py
│   │   ├── intelligent_chunker.py
│   │   ├── synthetic_data_generator.py
│   │   └── synthetic_scheduler_data.py
│   └── embeddings/
│       ├── embedding_config.py
│       └── embedding_generator.py
├── backend/
│   ├── __init__.py
│   ├── main.py
│   ├── ingest_knowledge_base.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py
│   │   └── scheduler_routes.py
│   ├── llm/
│   │   ├── __init__.py
│   │   └── gemini_client.py
│   ├── rag/
│   │   ├── __init__.py
│   │   ├── qa_pipeline.py
│   │   ├── guardrails.py
│   │   ├── conversation_manager.py
│   │   └── source_formatter.py
│   ├── retrieval/
│   │   └── semantic_search.py
│   └── agents/
│       ├── __init__.py
│       ├── scheduling_agent.py
│       └── scheduling_tools.py
├── documents/
│   ├── phd/
│   │   ├── Ordinances_for_Doctoral_Programm2023.pdf
│   │   └── processed/
│   │       ├── phd_ordinance_pages.json
│   │       ├── phd_ordinance_text.txt
│   │       ├── phd_ordinance_structure.json
│   │       ├── phd_ordinance_chunks.json
│   │       ├── phd_ordinance_embeddings.json   (local model required)
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
└── frontend/
    ├── index.html
    ├── app.js
    └── style.css
```

---

## 6. What Was Actually Run and Verified

All offline (non-database, non-embedding-model) pipeline stages were executed
successfully during the build.

| Step | Command                                             | Result |
| ---- | --------------------------------------------------- | ------ |
| 1    | `python ai/ingestion/pdf_parser.py`                 | 75 pages extracted, 110,554 characters, JSON + TXT written |
| 2    | `python ai/ingestion/structure_parser.py`           | 18 sections, 73 clauses, 26 form records, 26 unique form IDs, validation **PASS** |
| 3    | `python ai/ingestion/intelligent_chunker.py`        | 117 clause + 26 form = **143 chunks**, validation **PASS** (6 chunks > 3200 chars, tolerated warning) |
| 4    | `python ai/ingestion/synthetic_scheduler_data.py`   | DUGC 7, DMPC 6, DDPC 7 |

> Tests that import the `backend` package must be run from the repository root
> as a module, e.g. `python -m tests.test_guardrails`.

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
Average characters : 2039.47
Maximum characters : 3533
Validation         : PASS
```

---

## 7. What Was NOT Run (Environment Limitations)

1. **Embedding generation** (`ai/embeddings/embedding_generator.py`) needs the
   local `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` model
   download. Run it on the developer machine.
2. **PostgreSQL ingestion** (`backend/ingest_knowledge_base.py`) and the
   interactive retrieval / QA pipelines require a running PostgreSQL instance
   with the `pgvector` extension, the `departmentai` database, the
   `documents` / `sections` / `knowledge_chunks` tables, and a `documents` row
   for the Doctoral ordinance PDF.
3. **Live Gemini API calls** (`backend/llm/gemini_client.py`,
   `ai/ingestion/synthetic_data_generator.py`) require a real `GEMINI_API_KEY`.
   Pre-written synthetic JSON (12 past cases, 10 minutes, 10 circulars) is
   already in `documents/phd/processed/`.

No database credentials or API keys were hard-coded anywhere. The
`.env.example` file contains only placeholders.

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
`backend/main.py`).

---

## 9. How to Reproduce End-to-End on a Developer Machine

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

python ai/ingestion/pdf_parser.py
python ai/ingestion/structure_parser.py
python ai/ingestion/intelligent_chunker.py
python ai/embeddings/embedding_generator.py
python ai/ingestion/synthetic_scheduler_data.py

python backend/ingest_knowledge_base.py --replace
uvicorn backend.main:app --reload
```

In another terminal:

```bash
cd frontend
python -m http.server 5500
```

Open `http://127.0.0.1:5500`.

Full commentary for each step is in `README.md` (Getting Started).

### Database schema expected by the ingestion script

Same schema as the UG / M.Tech. modules. See `README.md` section 5.

Insert a `documents` row for:

```text
file_name     = Ordinances_for_Doctoral_Programm2023.pdf
document_type = Doctoral Ordinance
```

Insert the 18 section rows for the document.

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
| Synthetic past cases       | 12                   |
| Synthetic DDPC minutes     | 10                   |
| Synthetic circulars        | 10                   |

Doctoral forms detected: `DP-01 DP-02 DP-03 DP-04 DP-05 DP-06 DP-07 DP-08
DP-09 DP-10 DP-11 DP-12a DP-12b DP-13 DP-14 DP-15 DP-16 DP-17 DP-18 DP-19
DP-20 DP-21 DP-22 DP-23 DP-24 GL-1`.

Sections detected: `1..18` (INTRODUCTION → AMENDMENTS).

---

## 11. Recommendation Agent Upgrade (Synthetic Knowledge + Draft Resolution)

The Ph.D. RAG module uses the same Recommendation Agent contract as M.Tech.:
five fixed headings, mixed retrieval of ordinance / past_case / meeting_minute
/ circular.

Real previous minutes, office orders, and decided cases are not available.
Synthetic JSON datasets were written from the official Doctoral ordinance
(comprehensive exam, thesis extension, supervisor allocation) and stored as:

* `documents/phd/processed/synthetic_past_cases.json`
* `documents/phd/processed/synthetic_ddpc_minutes.json`
* `documents/phd/processed/synthetic_circulars.json`

### Run order after this upgrade

```bash
python ai/ingestion/synthetic_data_generator.py
python backend/ingest_knowledge_base.py --replace
uvicorn backend.main:app --reload
```

Required output headings:

```text
Relevant ordinance clauses
Similar previous cases (citing the synthetic data)
Identified deficiencies
Possible course of action
Initial draft resolution
```

---

## 12. Scheduling Agent Domain Swap

* `VALID_COMMITTEES` remains `DUGC`, `DMPC`, `DDPC` (shared architecture).
* Default doctoral committee in the frontend and minutes prompts is **DDPC**.
* Default slot starts moved to 09:30 / 10:30 / 11:30 / 14:30 / 15:30 / 16:30.
* New CSE faculty roster: HoD Prof. Leela Krishnan; DDPC Convener
  Dr. Sameer Qureshi; Member Secretary Dr. Tanvi Kapoor; plus Nandini Rao,
  Harish Talwar, Aisha Rahman, Gautam Deshpande, Pooja Bhatia, Rajan Khurana,
  Yusuf Pathan, Arvind Menon, Ritu Banerjee.
* DMPC is still present as the Masters' committee, with M.Tech. lecture busy
  slots **by design** (shared three-committee scheduler).
* Remaining PROP minutes under `documents/scheduler/processed/` were rewritten
  as Ph.D. / DDPC drafts (comprehensive exam, SPI/CPI deficiency, supervisor
  change, Open Seminar eligibility, thesis extension / similarity).

---

## 13. Remaining Work / Next Steps

* [ ] Run `python ai/embeddings/embedding_generator.py` on a machine with the
      sentence-transformer model.
* [ ] Create the PostgreSQL schema + `documents` row + 18 `sections` rows.
* [ ] Run `backend/ingest_knowledge_base.py --replace` and confirm 143 ordinance
      rows plus synthetic records.
* [ ] Put a real `GEMINI_API_KEY` in `.env` and exercise `/ask`.
* [ ] Tune chunking / retrieval weights if retrieval quality needs improvement.
* [ ] Optional: metadata correction and traceability validation.

---

## 14. Notes on Repository Isolation

* The original UG and M.Tech. repositories were **read only**.
* `DepartmentAI-Replace-2026` is a self-contained Ph.D. module with its own
  PDF copy, processed artifacts, source code, frontend and documentation.

---

## 15. Key Decisions

* Use **DDPC** (not DPGC) as the doctoral committee, matching ordinance
  Clause 1.3.
* Keep DUGC / DMPC / DDPC as valid scheduler committees; default doctoral
  committee is DDPC.
* Knowledge-base paths:
  `documents/phd/processed/{phd_ordinance_pages,structure,chunks,embeddings,synthetic_past_cases,synthetic_ddpc_minutes,synthetic_circulars}.json`.
* Gemini model in code: `gemini-3.5-flash-lite`.
* Embeddings: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
  (384-d).
* Frontend talks to `http://127.0.0.1:8000/ask` and `/schedule/*`.
* CORS allows `:5500` and `*.monkeycode-ai.live`.
* `requirements.txt` lists `google-genai` (not `google-generativeai`).

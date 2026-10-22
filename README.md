# DepartmentAI

### Agentic AI-Based Academic Governance and Department Automation System

DepartmentAI is an AI-powered academic governance and department automation system designed to support academic committees, faculty members, and authorized institutional officials in managing academic information, application-processing workflows, research records, documentation, and institutional reporting.

The system combines **Large Language Models (LLMs), Retrieval-Augmented Generation (RAG), semantic search, document intelligence, PostgreSQL, and workflow automation** to make institutional information more accessible and administrative processes more efficient.

> **Human-in-the-loop principle:** DepartmentAI assists with information retrieval, document processing, analysis, and administrative workflows. Final academic and administrative decisions remain with authorized institutional officials.

---

## 🎯 Project Objectives

- Build an intelligent knowledge base for institutional academic documents.
- Enable natural-language querying over academic rules and faculty information.
- Support application-processing and administrative workflows.
- Organize faculty profiles, research publications, and thesis-supervision records.
- Implement reliable retrieval and grounded AI-generated responses.
- Generate structured data exports for institutional use.
- Improve the efficiency and traceability of academic administration.
- Maintain human oversight over official decisions.
- Develop a modular, maintainable architecture that supports future academic automation.

---

## 🏗️ Project Architecture

DepartmentAI is organized into two major modules.

### Module I — Academic Application Processing

Module I provides the existing application-processing backend and related services. It forms the foundation for automating administrative workflows involving academic applications and supporting documents.

Its development focuses on:

- Application-processing workflows.
- Document handling and validation.
- Backend API integration.
- Support for administrative review.
- Human-supervised decision-making.

Module I is maintained as an independent part of the project while additional functionality is integrated into the overall DepartmentAI application.

### Module II — Faculty Information, Research Publications and Institutional Reporting

Module II extends DepartmentAI beyond application processing to faculty information retrieval, research records, thesis-supervision data, and data exports.

Its implemented capabilities include:

- Faculty information collection from official institutional profiles.
- Faculty profile and research-related information retrieval.
- Thesis-supervision record processing and reconciliation.
- Classification of thesis-supervision records into M.Tech. and Ph.D. categories.
- Handling of completed and ongoing Ph.D. supervision records.
- A command-line faculty assistant supporting natural-language questions.
- Database-backed data export functionality.
- CSV, Excel, PDF, and Word export formats.

The faculty data collection process uses the official MNNIT Allahabad Computer Science and Engineering department website as its starting point.

**Authoritative faculty directory:**  
https://mnnit.ac.in/index.php/department/engineering/csed#publications

Faculty profile information should be discovered through the department directory and verified against the corresponding official faculty profiles.

---

## 🧠 Core Technologies

| Component | Technology |
|---|---|
| Programming language | Python |
| Backend framework | FastAPI |
| Database | PostgreSQL |
| Vector search | pgvector |
| Embedding model | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` |
| Embedding dimension | 384 |
| LLM integration | Gemini API |
| Database access | SQLAlchemy / psycopg2, with module-specific database adapters |
| Data processing | NumPy / Pandas |
| PDF extraction | PyMuPDF |
| API server | Uvicorn |
| Development environment | Windows, PowerShell and VS Code |

Exact dependencies and versions should be taken from the project's dependency files and environment configuration.

---

## 🔎 Module I: Academic Knowledge and Application Processing

The original knowledge-assistance architecture uses Retrieval-Augmented Generation to retrieve relevant institutional information before generating an answer.

### RAG pipeline

```text
Official Academic Documents
           |
           v
     PDF Extraction
           |
           v
   Structure Detection
           |
           v
    Intelligent Chunking
           |
           v
   Embedding Generation
           |
           v
    PostgreSQL + pgvector
           |
           v
    Semantic Retrieval
           |
           v
 Keyword / Semantic Ranking
           |
           v
     Relevant Context
           |
           v
     LLM Answer Generation
           |
           v
      Grounded Response
```

The original undergraduate ordinance knowledge base was built around the MNNIT Allahabad Undergraduate Ordinance.

Its processing pipeline included PDF parsing, clause and section detection, chunk generation, embedding creation, database ingestion, and semantic retrieval.

The original documented dataset comprised:

- 68 unique ordinance clauses.
- 14 physical form records.
- 13 unique form identifiers.
- 246 total knowledge chunks, including 232 ordinance chunks and 14 form chunks.
- 384-dimensional embeddings.

These figures describe the original ordinance dataset, not the complete size of the current DepartmentAI system.

The broader application-processing module builds upon this foundation to support administrative workflows and document handling.

---

## 👥 Module II: Faculty Information and Research Data

Module II is designed to make faculty-related institutional information searchable and usable for reporting.

### Faculty information retrieval

The faculty assistant loads searchable records and supports continuous question-answering through a command-line interface.

Start the assistant from the project root:

```powershell
python -m module2.retrieval.faculty_assistant
```

The assistant provides an interactive session and supports contextual commands:

```text
/context
/reset
exit
quit
```

- `/context` displays the current faculty context.
- `/reset` clears the current conversational context.
- `exit` or `quit` ends the session.

The assistant uses available faculty data and its configured retrieval and LLM components to answer relevant questions.

### Thesis-supervision records

The thesis-supervision processing pipeline reconciles records against official faculty profile pages.

The latest completed reconciliation reported:

| Metric | Result |
|---|---:|
| Official faculty profile pages processed | 33 |
| Parsing errors | 0 |
| Records parsed | 1,413 |
| Records updated | 1,413 |
| Records inserted | 0 |
| M.Tech. records | 1,192 |
| Ph.D. records | 221 |

The reconciliation preserved the distinction between completed and ongoing Ph.D. supervision records. M.Tech. records without an explicitly stated completion status are not automatically classified as completed or ongoing.

These figures describe the latest recorded reconciliation run and may change when official profiles are updated.

### Faculty assistant testing

The following focused test suites have previously passed:

```powershell
python -m pytest tests/test_faculty_assistant_thesis_filters.py -q
python -m pytest tests/test_thesis_source_reconciliation.py -q
```

The reported combined result was **15 passed tests**.

---

## 📤 Module II: Data Export

Module II includes a database-backed export feature for supported Module II tables.

### Supported formats

| Format | Intended use |
|---|---|
| CSV | Portable structured data |
| Excel (`.xlsx`) | Spreadsheet analysis and filtering |
| PDF | Shareable document output |
| Word (`.docx`) | Editable document output |

### Export interface

The export module provides a browser-based interface for listing available datasets and downloading supported formats.

When the backend is running locally, the interface is available at:

```text
http://127.0.0.1:8000/module2/export/ui
```

The API exposes endpoints for listing available datasets and downloading individual datasets.

```text
GET /module2/export/ui
GET /module2/export/datasets
GET /module2/export/{dataset}/download?format=csv
GET /module2/export/{dataset}/download?format=xlsx
GET /module2/export/{dataset}/download?format=pdf
GET /module2/export/{dataset}/download?format=docx
```

The export implementation discovers eligible Module II tables through database metadata and restricts exports to supported table names. Export limits are applied to control the amount of data returned in a single request.

The current PDF and Word implementation presents database records in tabular form. **Dataset-aware narrative reports with meaningful headings, paragraphs, and section-specific layouts are a planned enhancement, not yet a completed feature.**

---

## 🗄️ Database

The project uses PostgreSQL for persistent academic and institutional data.

The original knowledge-retrieval module uses PostgreSQL with pgvector for embedding storage and similarity search.

Module II uses its own database and retrieval components for faculty-related information and exports. The exact tables and schemas are maintained in the project's database and module implementation files.

Local database configuration and credentials must be provided through environment variables and must not be committed to version control.

---

## 📁 Project Organization

DepartmentAI is maintained as a modular Python application. Its main areas include:

```text
DepartmentAI/
├── backend/
│   ├── main.py
│   └── api/
│       └── routes.py
├── module2/
│   ├── database/
│   │   └── connection.py
│   ├── ingestion/
│   ├── retrieval/
│   ├── data_export/
│   └── ...
├── tests/
│   ├── test_faculty_assistant_thesis_filters.py
│   ├── test_thesis_source_reconciliation.py
│   └── module2_data_export/
├── documents/
├── requirements.txt
├── .gitignore
└── README.md
```

This is a high-level overview, not a complete recursive listing. The actual repository may contain additional services, scripts, data directories, tests, and configuration files.

---

## 💻 Development Environment

The project is developed primarily on Windows using PowerShell, Python, VS Code, PostgreSQL, and a project-local virtual environment.

### Clone the repository

```powershell
git clone <your-repository-url>
cd DepartmentAI
```

### Create and activate a virtual environment

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### Install dependencies

```powershell
python -m pip install -r requirements.txt
```

### Configure environment variables

Create a local `.env` file containing the environment variables required by the configured modules.

For example:

```env
GEMINI_API_KEY=your_api_key_here
DB_HOST=localhost
DB_PORT=5432
DB_NAME=departmentai
DB_USER=postgres
DB_PASSWORD=your_local_database_password
```

The actual variable names required by a particular component should be verified against its configuration code.

**Never commit real API keys, passwords, or other secrets to GitHub.**

### Start the backend

From the project root, with the virtual environment activated:

```powershell
uvicorn backend.main:app --reload
```

The local API documentation, when enabled by the FastAPI application, is available at:

```text
http://127.0.0.1:8000/docs
```

---

## 🧪 Testing

DepartmentAI uses automated tests for important retrieval, data-processing, and export behaviour.

Run the focused faculty-assistant tests:

```powershell
python -m pytest tests/test_faculty_assistant_thesis_filters.py -q
```

Run the thesis-reconciliation tests:

```powershell
python -m pytest tests/test_thesis_source_reconciliation.py -q
```

Run the Module II export tests:

```powershell
python -m pytest tests/module2_data_export -v
```

Run the available test suite:

```powershell
python -m pytest -q
```

Tests should be run in the project's configured environment. A passing focused test suite does not by itself establish that every integration, database operation, or generated document has been validated.

Export verification should include all four supported formats and checks against the actual configured database.

---

## 📊 Current Project Status

| Component | Status |
|---|---|
| Original undergraduate ordinance ingestion pipeline | Implemented |
| Original ordinance chunking and embeddings | Implemented |
| PostgreSQL and pgvector knowledge storage | Implemented |
| Semantic retrieval and ranking | Implemented |
| Module I application-processing backend | Existing implementation |
| Module II faculty information ingestion | Implemented |
| Faculty assistant | Implemented |
| Thesis-supervision reconciliation | Implemented and reconciled |
| Focused faculty/thesis test suites | Previously passed |
| Module II dataset discovery and export interface | Implemented |
| CSV export | Working |
| Excel export | Working |
| PDF export | Working with tabular presentation |
| Word export | Working with tabular presentation |
| Dataset-aware narrative PDF/Word templates | Planned |
| Expanded institutional reporting | Future enhancement |
| Further frontend integration and refinement | Future enhancement |
| Additional academic workflow automation | Future enhancement |

Status labels describe the latest recorded development state and should be updated when implementation or verification changes.

---

## 🛣️ Development Roadmap

### Phase 1 — Academic knowledge foundation

- Document ingestion and parsing.
- Knowledge extraction and chunking.
- Embedding generation.
- PostgreSQL and vector retrieval.
- Grounded answer generation.

### Phase 2 — Application processing

- Maintain and improve the existing application-processing backend.
- Improve document-processing and validation workflows.
- Strengthen API integration and testing.
- Preserve human authorization for official decisions.

### Phase 3 — Faculty and research information

- Maintain official-source faculty data ingestion.
- Improve faculty information retrieval.
- Reconcile research and thesis-supervision records.
- Expand focused regression testing.

### Phase 4 — Institutional data export and reporting

- Maintain CSV and Excel exports.
- Preserve reliable PDF and Word generation.
- Introduce dataset-aware document templates.
- Support natural-language narrative reports where appropriate.
- Add meaningful report headings, metadata, and section layouts.
- Validate generated documents against actual database records.

### Phase 5 — Expanded academic automation

- Improve institutional analytics.
- Develop additional reporting workflows.
- Expand academic application assistance.
- Introduce additional document intelligence capabilities.
- Explore specialized agents for retrieval, validation, reporting, and workflow preparation.

These phases describe the development direction; they do not imply that every listed feature is already implemented.

---

## 🛡️ Design Principles

### Accuracy first

Institutional information must be retrieved and represented accurately.

### Grounded AI

AI-generated answers should use relevant institutional evidence and acknowledge insufficient information rather than guess.

### Human oversight

AI supports academic and administrative work but does not replace authorized decision-makers.

### Official-source verification

Faculty and institutional records should be checked against authoritative sources.

### Incremental development

Changes should be introduced in small, testable steps while preserving working functionality.

### Privacy and security

Credentials, personal data, and institutional records must be handled responsibly.

### Maintainability

Modules should remain understandable, testable, and independently maintainable.

### Traceability

Where applicable, generated answers and reports should be traceable to their underlying records and source documents.

---

## 🔮 Future Enhancements

Potential enhancements include:

- Dataset-aware narrative PDF and Word reports.
- Expanded institutional analytics and reporting.
- More advanced faculty and research queries.
- Improved frontend experience.
- Additional document classification and validation.
- Multilingual academic assistance.
- Enhanced source citations and traceability.
- Role-based access control and audit logging.
- Notification and workflow-management capabilities.
- Additional academic committee automation.
- Specialized AI agents for approved institutional workflows.

---

## ⚠️ Disclaimer

DepartmentAI is an assistive academic information and automation system. Generated information, extracted records, and reports should be verified against the relevant official sources before being used for formal academic or administrative decisions.

DepartmentAI does not replace official institutional procedures or the authority of authorized officials.

---

## 📜 License

The project is currently intended for academic and research purposes. License information will be added when the project's release and distribution terms are finalized.

---

## 🚀 Current Milestone

**DepartmentAI is actively under development.**

The project has progressed from an undergraduate ordinance knowledge-retrieval foundation to a modular system that also includes application-processing functionality, faculty information retrieval, thesis-supervision reconciliation, and Module II data exports.

The immediate priorities are to preserve the reliability of existing functionality, improve testing and verification, and develop more useful institutional reporting capabilities without disrupting completed work.

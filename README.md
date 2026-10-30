# DepartmentAI: Agentic Academic Governance and Administrative Intelligence System

DepartmentAI is an **Agentic AI-based Department Automation System** designed to automate and assist academic committee processes, faculty information management, and institutional reporting.

The system integrates Large Language Models (LLMs), autonomous AI agents, document intelligence, knowledge retrieval, and workflow automation to improve administrative efficiency, preserve institutional knowledge, and support consistent, evidence-based academic decision-making.

DepartmentAI is designed around two major modules:

- **Module I:** Automation of Undergraduate (UG), Postgraduate (PG), and Ph.D. academic processes.
- **Module II:** Faculty Profile, Research Information, and Institutional Reporting Automation.

Module I currently has a shared local application workflow and source-scoped
UG, M.Tech/Masters, and Ph.D. ordinance retrieval in the Academic Assistant.
Programme identity, programme-specific application categories/forms,
eligibility/document rules, and automatic committee routing are not yet
implemented or institutionally verified. PG Diploma (PGD) is not specified.
See the [Module 1 coverage audit](./docs/MODULE1_PROGRAMME_COVERAGE_AUDIT.md).

## Quick start for local development

The project runs as a Python FastAPI backend plus a static HTML/JavaScript frontend.
Use the commands below from the repository root.

### 1) Prepare the Python environment

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 2) Configure the local development database

The backend expects a local PostgreSQL database named `departmentai_dev` when
`DEPARTMENTAI_DATABASE_ENV=development` is active. Use the example env file as a
starting point and confirm the username, host, and password match your local
PostgreSQL instance.

```powershell
Copy-Item .env.development.example .env.development
$env:DEPARTMENTAI_DATABASE_ENV = "development"
```

### 3) Start the backend

```powershell
$env:DEPARTMENTAI_DATABASE_ENV = "development"
$env:CORS_ALLOWED_ORIGINS = "http://127.0.0.1:5500"
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8002
```

Verify the API is healthy:

```powershell
curl http://127.0.0.1:8002/health/ready
```

### 4) Start the frontend

In a second terminal:

```powershell
python -m http.server 5500 --bind 127.0.0.1 --directory .\frontend
```

Then open this URL in the browser:

```text
http://127.0.0.1:5500/
```

### 5) Optional: load ordinance knowledge

If you want the Academic Assistant to answer UG, M.Tech/Masters, and Ph.D.
questions with the local corpora:

```powershell
$env:DEPARTMENTAI_DATABASE_ENV = "development"
.\.venv\Scripts\python.exe -m backend.ingest_knowledge_base --programme MTECH
.\.venv\Scripts\python.exe -m backend.ingest_knowledge_base --programme PHD
```

### Frontend configuration

The browser-side API URL is configured in `frontend/config.js` and defaults to:

```js
globalThis.DEPARTMENTAI_API_BASE_URL ??= "http://127.0.0.1:8002";
```

If the backend runs elsewhere, update the origin there. Do not use wildcard CORS
values or secret credentials in the frontend file.

For a more detailed frontend-only guide, see [frontend/README.md](./frontend/README.md).

> **Human-in-the-loop principle:** DepartmentAI assists with information retrieval, application classification, document analysis, recommendations, scheduling, minutes preparation, and report generation. All official decisions, recommendations, minutes, and institutional reports remain subject to verification and approval by authorized officials.

---

## 🎯 Project Objectives

The primary objectives of DepartmentAI are to:

1. Automate repetitive academic and administrative workflows.
2. Develop an intelligent chatbot for students, staff, faculty, and authorized officials.
3. Process student applications using document intelligence and AI-assisted classification.
4. Retrieve relevant ordinances, regulations, circulars, and previous committee decisions.
5. Generate evidence-based recommendations and draft resolutions.
6. Assist in committee meeting scheduling, agenda preparation, and minutes generation.
7. Maintain structured faculty profiles and institutional research information.
8. Generate faculty-wise and department-wise statistics for institutional reporting.
9. Prepare reports in prescribed Word, Excel, PDF, and tabular formats.
10. Maintain human oversight, data integrity, traceability, and secure handling of institutional information.

---

# 🏗️ System Architecture

DepartmentAI is organized into two major modules supported by shared AI, database, document-processing, and workflow capabilities.

```text
                         DepartmentAI
                              |
                 +------------+------------+
                 |                         |
                 v                         v
       MODULE I: ACADEMIC          MODULE II: FACULTY
       PROCESS AUTOMATION          & INSTITUTIONAL REPORTING
                 |                         |
       +---------+---------+      +--------+---------+
       |         |         |      |        |         |
       v         v         v      v        v         v
     DUGC      DMPC      DDPC   Faculty  Research  Reporting
     UG        M.Tech.   Ph.D.  Profiles Records   & Exports
       |         |         |      |        |         |
       +---------+---------+      +--------+---------+
                 |                         |
                 v                         v
        Document Intelligence       Data Extraction
        Knowledge Retrieval         Validation
        AI Recommendations          Deduplication
        Workflow Assistance         Statistics
                 |                         |
                 +------------+------------+
                              |
                              v
                   Human Verification
                              |
                              v
                   Authorized Approval
```

The architecture is modular so that existing functionality can be maintained while additional capabilities are introduced incrementally.

---

# 📘 Module I: Automation of UG, PG and Ph.D. Academic Processes

Module I focuses on automating and assisting student application processing and academic committee workflows.

It covers the following departmental committees:

- **DUGC** — Departmental Undergraduate Committee
- **DMPC** — Departmental M.Tech. Programme Committee
- **DDPC** — Departmental Doctoral Programme Committee

The objective is to streamline the processing of academic applications while ensuring that official decisions remain with authorized committee members and institutional officials.

## 1. LLM-Based Student and Staff Chatbot

The proposed multilingual chatbot will guide students and office staff regarding:

- Appropriate application categories.
- Applicable UG, PG, and Ph.D. ordinances.
- Eligibility requirements.
- Required supporting documents.
- Application status.
- Deficiencies and pending actions.

The chatbot will retrieve information from approved ordinances, institutional rules, circulars, and previous committee decisions.

It will provide informational assistance but will not independently approve or reject applications.

## 2. Application Classification Agent

After an application is submitted, the proposed classification agent will:

- Identify the nature of the request.
- Classify it as a DUGC, DMPC, or DDPC matter.
- Extract relevant student information and supporting documents.
- Identify missing information and potential deficiencies.
- Map the request to relevant ordinance provisions.

OCR and intelligent document-processing techniques may be incorporated to process scanned applications and supporting documents.

## 3. Knowledge Retrieval and Recommendation Agent

The knowledge-retrieval system will retrieve relevant information from:

- UG, PG, and Ph.D. ordinances.
- Previous DUGC, DMPC, and DDPC meeting minutes.
- Office orders, circulars, and regulations.
- Similar previously decided cases.

The system will use RAG and suitable semantic, keyword, hybrid, or other retrieval approaches.

The proposed recommendation agent will prepare:

- Relevant ordinance clauses.
- Similar historical cases.
- Identified deficiencies.
- Possible courses of action.
- Initial draft resolutions.

Recommendations and draft resolutions will be reviewed and edited by authorized officials before use.

## 4. Meeting Scheduling Agent

The proposed scheduling agent will consider:

- Faculty timetables.
- Committee membership.
- Existing meetings.
- Member availability.
- Academic calendar restrictions.

It will suggest suitable meeting slots and assist in preparing meeting notices and agendas.

Following the required consent and availability confirmation, the system may integrate with authorized email, calendar, and messaging services to distribute approved meeting information.

Integration with WhatsApp or other institutional communication platforms is a planned capability and will depend on authorized access and supported integrations.

## 5. AI-Assisted Minutes Generation

The proposed minutes-generation dashboard will assist in preparing draft minutes using:

- Approved meeting agendas.
- Notes recorded during meetings.
- Member observations.
- Final committee decisions.
- Relevant ordinance provisions.

The system will support review of draft minutes, identification of inconsistencies, and management of unresolved comments.

Final minutes will be stored and indexed after review and approval by the authorized authority. Secure storage, document version control, and digital-signature integration are intended capabilities.

### Optional local M.Tech/PhD ordinance adapter

The backend contains a manual, source-scoped ordinance-advisory adapter for a
Student-owned draft with a verified M.Tech/PhD identity and a resolved
`TEST_ONLY` application policy. It sends only the draft's application type,
title, and description to a loopback reference service; uploaded document
contents and applicant identifiers are not sent. The adapter is disabled by
default and additionally requires the explicit `test` database profile, the
local synthetic demo, loopback reference-service URLs, and a runtime-only
shared token. The reference services were not available during the latest
local check, so live RAG and authenticated-browser behavior remain unverified.
Do not enable this path with institutional data or credentials.

---

# 📗 Module II: Faculty Profile and Institutional Reporting Automation

Module II focuses on automating faculty information management, research-data processing, institutional statistics, and report preparation.

The module is intended to support reporting requirements from the Ministry, institute administration, accreditation bodies, and other authorized agencies.

## 1. Faculty Information Management

The system collects and organizes faculty information from official faculty profiles and approved institutional databases.

Its scope includes:

- Faculty profile information.
- Research publications.
- Patents filed or granted.
- Sponsored research projects.
- Consultancy activities.
- Conferences.
- Workshops.
- Awards and recognitions.
- Student supervision and thesis-related records.

Official-source verification is important to maintain data accuracy and reduce unsupported assumptions.

The current faculty-data collection process uses the official MNNIT Allahabad Computer Science and Engineering department directory as its starting point:

https://mnnit.ac.in/index.php/department/engineering/csed#publications

Individual faculty information should be discovered through the directory and verified against the corresponding official faculty profiles.

## 2. Research Data Processing

The proposed processing pipeline will:

1. Collect information from approved sources.
2. Extract relevant research and institutional records.
3. Normalize structured data.
4. Remove duplicate records.
5. Identify missing or inconsistent information.
6. Filter records for specified reporting periods.
7. Generate faculty-wise and department-wise statistics.

These capabilities will help reduce manual data compilation and improve the consistency of institutional reporting.

## 3. Faculty Information Assistant

Module II includes a command-line faculty assistant for querying available faculty information.

Run it from the project root:

```powershell
python -m module2.retrieval.faculty_assistant
```

The interactive session supports:

```text
/context
/reset
exit
quit
```

- `/context` displays the current faculty context.
- `/reset` clears the current conversational context.
- `exit` or `quit` terminates the session.

The assistant uses the available faculty records and configured retrieval and LLM components to answer relevant questions.

## 4. Thesis-Supervision Records

The thesis-supervision pipeline processes and reconciles records against official faculty profile pages.

The latest recorded reconciliation reported:

| Metric | Result |
|---|---:|
| Official faculty profile pages processed | 33 |
| Parsing errors | 0 |
| Records parsed | 1,413 |
| Records updated | 1,413 |
| Records inserted | 0 |
| M.Tech. records | 1,192 |
| Ph.D. records | 221 |

Ph.D. records distinguish completed and ongoing supervision where supported by the source information. M.Tech. records without an explicitly stated completion status are not automatically assigned a status.

These figures describe the recorded reconciliation run and may change as official faculty profiles are updated.

## 5. Institutional Data Export

Module II has a secured export API foundation, but it is disabled for all
accounts until an operator configures approved per-user permissions and exact
department scopes. The SoStudy website includes a permission-gated
**Module II — Faculty & Research** page in the authenticated sidebar. It
connects to the capability, faculty, research, statistics, and secured export
APIs using the shared bearer-session client. The former unauthenticated export
UI remains removed.

Currently supported formats include:

| Format | Purpose |
|---|---|
| CSV | Structured, portable data |
| Excel (`.xlsx`) | Spreadsheet analysis and filtering |
| PDF | Shareable document output |
| Word (`.docx`) | Editable document output |

Before using any Module II data route or CLI, select its database profile
independently of Module I. The test profile is restricted to loopback
`departmentai_module2_test`; it never inherits the Module I database selector
or root `.env`. Provision that database and create a private
`.env.module2.test` from [.env.module2.test.example](./.env.module2.test.example).
No database/schema is created or migrated automatically. Development uses
`.env.module2.development` with `departmentai_module2_dev`. Production requires
an explicit `.env.module2.production` file.

```powershell
$env:DEPARTMENTAI_MODULE2_DATABASE_ENV = "test"
```

Profile selection does not provision a database or schema. After an authorized
operator provisions the dedicated database and private profile, verify the
resolved application connection with a read-only `SELECT current_database()`
through `module2.database.connection.get_connection()` and confirm the result
is exactly `departmentai_module2_test` before running acceptance tests. Do not
copy Module I credentials or treat the profile filename alone as proof of the
connected database.

#### Current local acceptance boundary

The dedicated `departmentai_module2_test` database and private
`.env.module2.test` profile are not provisioned in this checkout. The available
Module I test role lacks `CREATEDB` and superuser privileges, and no authorized
Module II database-admin credential is available. Do not point Module II at
`departmentai_test`; wait for an authorized operator to provision the isolated
database and profile, then verify the application's resolved connection before
acceptance. The security/export/report tests currently use mocked database
cursors and do not establish live Module II data or report behavior.

Provide a protected JSON file through `DEPARTMENTAI_MODULE2_PERMISSION_POLICY`
only after approving specific authenticated account IDs, permission names,
and department scopes. No `STUDENT`, `OFFICIAL`, or `DUGC` role receives
Module II access by default.

The mounted read-only routes are documented in
[docs/API_CONTRACT.md](./docs/API_CONTRACT.md). They cover scoped faculty
profiles, linked publication/project/achievement reads, scoped statistics,
and fixed allowlisted exports. Student-sensitive supervision, CRUD,
data-quality review, source-ingestion APIs, and the faculty chatbot remain
unavailable. The existing ingestion/reconciliation tools remain controlled
CLI operations. Statistics do not support reporting-period filters; exports
are scoped data extracts, not approved Ministry, institute, or accreditation
reports. The frontend shows unavailable/configuration states rather than
inventing data when a permission or database profile is missing.

CSV, XLSX, PDF, and DOCX renderers are declared in `requirements.txt`; focused
tests validate each format. These files are raw scoped data extracts, not
approved Ministry, institute, or accreditation reports.

## 6. Ministry and Institutional Report Generation

The intended reporting system will allow authorized users to request information such as:

- How many journal papers were published during a specified period?
- How many patents were filed or granted?
- Which conferences were organized by the department?
- How many sponsored projects are currently active?
- Prepare a response using a supplied institutional reporting template.

The system will retrieve relevant records, calculate appropriate statistics, and prepare reports using approved templates.

The concerned employee will verify the data before formal submission.

---

# 🔎 Knowledge Retrieval and RAG

Retrieval-Augmented Generation is an important component of DepartmentAI's knowledge-assistance architecture.

The original undergraduate ordinance pipeline uses the following general process:

```text
Official Academic Documents
           |
           v
      PDF Extraction
           |
           v
     Structure Parsing
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
        Grounded Answer
```

The original ordinance dataset comprised:

- 68 unique ordinance clauses.
- 14 physical form records.
- 13 unique form identifiers.
- 232 ordinance chunks.
- 14 form chunks.
- 246 total knowledge chunks.
- 384-dimensional embeddings.

These figures refer to the original ordinance dataset, not the total data stored across both modules.

Future retrieval improvements may include hybrid search, improved source traceability, knowledge graphs, and retrieval over approved previous committee decisions.

---

# 🤖 Proposed Agentic Workflow

DepartmentAI is designed to evolve toward specialized agents that cooperate within controlled academic and administrative workflows.

```text
                  DepartmentAI
                       |
             +---------+---------+
             |                   |
             v                   v
      Knowledge Agent      Document Agent
             |                   |
             v                   v
      Retrieval & Rules    Extraction & Validation
             |                   |
             +---------+---------+
                       |
                       v
                Workflow Agent
                       |
                       v
               Draft / Recommendation
                       |
                       v
               Human Verification
                       |
                       v
              Authorized Decision
```

Potential specialized agents include:

- Knowledge Retrieval Agent.
- Application Classification Agent.
- Eligibility Analysis Agent.
- Document Validation Agent.
- Deficiency Detection Agent.
- Meeting Scheduling Agent.
- Agenda Generation Agent.
- Minutes Generation Agent.
- Faculty Information Agent.
- Research Statistics Agent.
- Institutional Report Generation Agent.

The diagram represents the proposed architecture. Individual agents and integrations should be considered implemented only when their corresponding functionality is available and verified.

---

# 🧰 Proposed Technologies

| Component | Technologies or approaches |
|---|---|
| Programming language | Python |
| Backend API | FastAPI |
| Database | PostgreSQL |
| Vector search | pgvector |
| Embeddings | Sentence Transformers |
| LLM integration | Gemini API and compatible LLM services |
| Document processing | PyMuPDF and other suitable document-processing libraries |
| Data analysis | Pandas and NumPy |
| Retrieval | Semantic, keyword, hybrid, or vectorless retrieval |
| OCR | OCR and document-understanding models, as required |
| Agent workflows | Suitable agentic workflow frameworks |
| Frontend | Web-based administrative interface |
| Reporting | CSV, Excel, PDF, and Word |
| Security | Planned role-based access control and audit logging |
| Integrations | Planned API, email, calendar, and approved messaging integrations |

The table includes both currently used technologies and proposed approaches. It does not imply that every listed technology or integration has been deployed.

---

# 🗄️ Database and Data Management

PostgreSQL is used for persistent application and institutional data.

The original knowledge-retrieval module uses PostgreSQL with pgvector for vector-based semantic search.

Module II maintains its own database, ingestion, retrieval, and export components for faculty-related information and supported institutional datasets.

The database schema and table names are defined in the implementation. This README intentionally avoids treating a partial schema as the complete database design.

Database credentials and API keys must be provided through environment variables or the project's supported configuration mechanisms.

---

# 🔐 Security and Governance

DepartmentAI is designed to preserve institutional authority and protect sensitive information.

Planned and applicable security measures include:

- Role-based access control.
- Restricted access to authorized institutional data.
- Audit logs for important administrative operations.
- Document version control.
- Secure document storage.
- Controlled access to external services.
- Human review and approval workflows.
- Protection of credentials and personal information.

Security features should be described as operational only after they have been implemented and verified.

Never commit actual API keys, database passwords, or other secrets to the repository.

Example environment variables:

```env
GEMINI_API_KEY=your_api_key_here
DB_HOST=localhost
DB_PORT=5432
DB_NAME=departmentai
DB_USER=postgres
DB_PASSWORD=your_local_database_password
```

The exact configuration required by each component should be checked against its implementation.

---

# 💻 Development Setup

DepartmentAI is developed primarily using Windows, PowerShell, Python, VS Code, and PostgreSQL.

## 1. Clone the repository

```powershell
git clone <your-repository-url>
cd DepartmentAI
```

## 2. Create and activate the virtual environment

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

## 3. Install dependencies

```powershell
python -m pip install -r requirements.txt
```

## 4. Configure environment variables

Create a local `.env` file with the variables required by the modules you intend to run.

Do not commit `.env` to GitHub.

## 5. Start the backend

```powershell
uvicorn backend.main:app --reload
```

When enabled, interactive API documentation is available at:

http://127.0.0.1:8000/docs

The Module II faculty chatbot is not offered through the shared website. Its
separate prototype endpoint is protected but returns HTTP 403 until
department-scoped retrieval authorization and provider policy are implemented.
Do not mount the standalone chatbot as a production service.

---

# 🧪 Testing and Verification

DepartmentAI uses focused tests to verify important retrieval, data-processing, and export behaviour.

### Faculty assistant tests

```powershell
python -m pytest tests/test_faculty_assistant_thesis_filters.py -q
```

### Thesis-reconciliation tests

```powershell
python -m pytest tests/test_thesis_source_reconciliation.py -q
```

### Module II export tests

```powershell
python -m pytest tests/module2_data_export -v
python -m pytest tests/module2_security -v
```

### Run the available test suite

```powershell
python -m pytest -q
```

The faculty assistant and thesis-reconciliation suites previously reported 15 passing tests combined.

Testing should also cover database integration, supported export formats, malformed or incomplete source records, and regression risks when changing existing functionality.

A passing test suite does not by itself establish that all proposed integrations or agentic workflows are implemented.

---

# 📊 Current Project Status

| Component | Current status |
|---|---|
| Original UG ordinance ingestion and chunking | Implemented |
| Original ordinance embeddings and semantic retrieval | Implemented |
| PostgreSQL and pgvector knowledge storage | Implemented |
| Module I application-processing backend | Existing implementation |
| Module II faculty information ingestion | Implemented |
| Module II Faculty & Research SoStudy page | Implemented; navigation/features require current server permissions |
| Faculty assistant | Standalone prototype; unavailable in SoStudy pending authorized retrieval |
| Thesis-supervision reconciliation | Implemented and reconciled |
| Focused faculty/thesis tests | Previously passed |
| Module II authenticated faculty/research API | Read-only; access requires a configured per-user permission policy |
| Module II dataset discovery and export API | Static allowlist and fixed field/department scope; access requires an export permission |
| CSV, XLSX, PDF, and DOCX renderers | Implemented; format tests run; no live database export verified |
| Narrative PDF and Word reporting templates | Planned |
| Expanded research statistics and reporting workflows | Further development |
| Multilingual student/staff chatbot | Planned |
| Automated application classification agent | Planned |
| Recommendation and draft-resolution agent | Planned |
| Meeting scheduling and communication integrations | Planned |
| AI-assisted minutes dashboard | Planned |
| Module II user/department permission provisioning | Not configured; operations fail closed |
| Digital signatures and secure document repository | Planned |
| Full agentic workflow orchestration | Future development |

Status reflects the currently recorded project state and should be revised when additional features are implemented and verified.

---

# 🛣️ Development Roadmap

## Phase 1 — Academic Knowledge Foundation

- Document parsing and structure extraction.
- Intelligent chunking and embedding generation.
- PostgreSQL and pgvector integration.
- Semantic retrieval and answer generation.

## Phase 2 — Application Processing

- Maintain and extend the existing application-processing backend.
- Improve document validation and workflow support.
- Strengthen API integration and regression testing.

## Phase 3 — Faculty Information Management

- Maintain official-source faculty information collection.
- Improve faculty retrieval and contextual question-answering.
- Reconcile thesis-supervision and research records.

## Phase 4 — Institutional Data Export

- Maintain reliable CSV and Excel exports.
- Preserve working PDF and Word generation.
- Introduce dataset-aware narrative reporting.
- Support approved institutional templates.
- Validate generated reports against source records.

## Phase 5 — Intelligent Academic Assistance

- Develop the multilingual student and staff chatbot.
- Improve application classification.
- Retrieve relevant ordinances and historical decisions.
- Generate evidence-based recommendations and draft resolutions.

## Phase 6 — Committee Workflow Automation

- Assist with meeting scheduling.
- Generate notices and agendas.
- Support draft minutes preparation.
- Introduce controlled review and approval workflows.

## Phase 7 — Institutional Reporting and Agentic Workflows

- Expand research statistics and institutional analytics.
- Develop specialized agents for approved tasks.
- Integrate authorized institutional services.
- Improve auditability, security, and traceability.

The roadmap is an intended development sequence, not a declaration that all phases are complete.

---

# 📈 Expected Deliverables

The overall project aims to deliver:

1. A secure web-based department automation portal.
2. An LLM-based chatbot for students, staff, and authorized faculty.
3. Student application-processing workflows.
4. An ordinance and previous-minutes knowledge base.
5. AI-assisted application classification and deficiency detection.
6. Evidence-based recommendations and draft resolutions.
7. Meeting scheduling, notice, and agenda preparation.
8. An AI-assisted minutes preparation dashboard.
9. Faculty information and research-statistics capabilities.
10. Institutional report generation using approved templates.
11. Role-based access, audit trails, and controlled document storage.
12. Human verification and approval across official workflows.

These are the project's expected deliverables; individual items remain subject to implementation and verification.

---

# 🎯 Design Principles

### 1. Accuracy First
Institutional information and generated reports must faithfully represent their sources.

### 2. Grounded AI
AI-generated responses should rely on relevant institutional evidence and acknowledge insufficient information.

### 3. Human-in-the-Loop Governance
Official decisions remain with authorized institutional officials.

### 4. Official-Source Verification
Faculty records, ordinances, and institutional data should be verified against authoritative sources.

### 5. Incremental Development
Changes should be introduced in controlled steps with appropriate testing.

### 6. Privacy and Security
Sensitive information, credentials, and institutional records must be protected.

### 7. Traceability
Where applicable, records, recommendations, and reports should be traceable to their underlying evidence.

### 8. Maintainability
The architecture should remain modular, testable, and understandable.

---

# 🔮 Future Enhancements

Potential future enhancements include:

- Dataset-aware narrative PDF and Word documents.
- Advanced faculty and research analytics.
- Multilingual conversational assistance.
- OCR for scanned applications.
- Knowledge graphs for mapping ordinances and committee decisions.
- Improved historical-case retrieval.
- Automated agenda and minutes preparation.
- Approved calendar, email, and messaging integrations.
- Role-based access control and audit logs.
- Document version control and digital-signature integration.
- Secure institutional document repositories.
- Further integration with existing departmental systems.

---

# ⚠️ Disclaimer

DepartmentAI is an assistive academic governance and administrative intelligence system.

AI-generated recommendations, extracted records, application analyses, minutes, and institutional reports must be reviewed against official sources and approved by authorized personnel before being used for formal decisions or submissions.

The system does not replace institutional authority, prescribed academic procedures, or authorized human approval.

---

# 📜 License

The project is currently intended for academic and research purposes. Licensing and distribution terms will be specified when finalized.

---

# 🚀 Project Status

**DepartmentAI is actively under development.**

The project has progressed from an academic ordinance knowledge-retrieval foundation to a modular system that includes an existing application-processing backend, faculty information retrieval, thesis-supervision reconciliation, and Module II data exports.

The next development priorities are to strengthen existing functionality, improve institutional reporting, and incrementally introduce additional AI-assisted workflows while preserving data accuracy, security, traceability, and human oversight.

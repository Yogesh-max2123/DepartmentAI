# DepartmentAI

### Agentic AI-Based Academic Department Automation System

DepartmentAI is an **AI-powered academic governance and department automation system** designed to assist academic committees, faculty, and authorized officials in managing academic processes, institutional knowledge, documentation, and administrative workflows.

The system combines **Large Language Models (LLMs), Retrieval-Augmented Generation (RAG), document intelligence, semantic search, vector databases, and workflow automation** to provide reliable, context-aware assistance while keeping final academic decisions under authorized human control.

> **Human-in-the-loop principle:** DepartmentAI assists with information retrieval, analysis, recommendations, drafting, and workflow preparation. It does not autonomously approve or reject official academic applications where human authorization is required.

---

## 🚀 Project Vision

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

> **User:** What are the requirements for a B.Tech Honours degree?

> **DepartmentAI:** To earn a B.Tech. Honours degree, a student must complete the minimum credits required for the Basic B.Tech. degree and earn an additional 16–20 credits through specialized courses in their discipline.

The answer is generated from the **retrieved official ordinance content**, rather than from unrestricted general knowledge.

---

# 🎯 Objectives

The major objectives of DepartmentAI are:

1. Build an intelligent knowledge base for academic ordinances and institutional documents.
2. Enable natural-language querying over official academic rules.
3. Implement reliable Retrieval-Augmented Generation (RAG).
4. Use semantic search to retrieve relevant institutional information.
5. Generate concise, grounded answers using an LLM.
6. Automate repetitive academic and administrative workflows.
7. Assist academic committees such as DUGC, DMPC, and DDPC.
8. Provide document and knowledge management capabilities.
9. Support multilingual interaction in future versions.
10. Maintain human authorization for official academic decisions.
11. Provide traceability from generated answers back to source documents.

---

# 🏗️ High-Level Architecture

The initial system follows a RAG-based architecture:

```text
                    ┌─────────────────────┐
                    │       User          │
                    │  Natural Language   │
                    │      Question       │
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
                    │ Semantic Retrieval  │
                    └──────────┬──────────┘
                               │
                         Top Candidates
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Semantic + Keyword  │
                    │     Reranking       │
                    └──────────┬──────────┘
                               │
                          Top 5–8 Chunks
                               │
                               ▼
                    ┌─────────────────────┐
                    │      LLM API        │
                    │  Grounded Answer    │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Clean Natural       │
                    │ Language Response   │
                    └─────────────────────┘
```

---

# 🧠 Core Technologies

| Component                 | Technology                                                    |
| ------------------------- | ------------------------------------------------------------- |
| Programming Language      | Python                                                        |
| Backend Framework         | FastAPI                                                       |
| Database                  | PostgreSQL 18                                                 |
| Vector Database Extension | pgvector 0.8.6                                                |
| Embedding Model           | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` |
| Embedding Dimension       | 384                                                           |
| LLM                       | Gemini API                                                    |
| ORM / Database Access     | SQLAlchemy / psycopg2                                         |
| Data Processing           | NumPy / Pandas                                                |
| PDF Processing            | PyMuPDF                                                       |
| Environment               | Windows 11 + VS Code                                          |
| API Server                | Uvicorn                                                       |

---

# 📚 Current Module: UG Ordinance → DUGC

The first implementation focuses on the **Undergraduate Ordinance and DUGC-related academic processes**.

The current authoritative knowledge source is the:

**MNNIT Allahabad Undergraduate Ordinance**

The ordinance contains academic rules covering areas such as:

* Introduction
* Academic Session
* Admission
* Curriculum
* Registration
* Teaching and Evaluation
* Academic Performance Requirements
* Holidays and Semester Leave
* Programme Requirements
* Degrees
* Scholarships, Prizes and Medals
* Conduct and Discipline
* Amendments

The system is being developed so users can ask questions about these rules using natural language.

---

# 🔎 Retrieval-Augmented Generation (RAG)

DepartmentAI uses RAG to reduce hallucination and ensure that answers are based on institutional documents.

The retrieval pipeline is:

```text
Official Document
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
       ▼
Embedding Generation
       │
       ▼
PostgreSQL + pgvector
       │
       ▼
Semantic Search
       │
       ▼
Keyword / Semantic Reranking
       │
       ▼
Relevant Context
       │
       ▼
LLM
       │
       ▼
Grounded Answer
```

---

# 📄 Document Processing Pipeline

The document ingestion pipeline consists of several stages.

### 1. PDF Parsing

The original ordinance PDF is processed using **PyMuPDF**.

```text
UG Ordinance.pdf
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

The current ordinance processing identified:

```text
68 unique ordinance clauses
14 physical form records
13 unique form IDs
```

### 3. Intelligent Chunking

The ordinance is divided into retrieval-friendly chunks.

Current dataset:

```text
232 ordinance chunks
+
14 form chunks
=
246 total chunks
```

Chunking parameters include:

```text
Target size: 1800 characters
Maximum size: 2400 characters
Overlap: 250 characters
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

Current embedding dataset:

```text
246 × 384
```

---

# 🗄️ Database

DepartmentAI currently uses PostgreSQL with pgvector.

### Database

```text
departmentai
```

### PostgreSQL Version

```text
PostgreSQL 18
```

### pgvector Version

```text
0.8.6
```

---

## Database Schema

### `documents`

Stores source document information.

```text
id
title
file_name
document_type
version
total_pages
created_at
```

### `sections`

Stores document sections.

```text
id
document_id
section_number
title
start_page
end_page
created_at
```

### `knowledge_chunks`

Stores searchable knowledge chunks and embeddings.

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

# 🔍 Semantic Retrieval

The current retrieval system performs:

```text
Question
   ↓
Generate query embedding
   ↓
pgvector similarity search
   ↓
15 candidate chunks
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

The purpose is to prevent situations where a semantically similar but contextually unrelated chunk is ranked first.

---

# 🤖 LLM Answer Generation

The next stage of the system uses an **LLM API** to convert retrieved ordinance content into a clean natural-language answer.

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

The LLM is instructed to:

* Answer only using retrieved ordinance content.
* Ignore unrelated portions of retrieved chunks.
* Preserve important numbers and conditions.
* Avoid hallucination.
* Avoid adding external/general knowledge.
* Clearly indicate when the retrieved content is insufficient.
* Produce concise and understandable answers.

---

# 🛡️ Grounding and Reliability

A major design goal is preventing the AI from inventing academic rules.

The intended behavior is:

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

For example:

```text
The available ordinance content does not provide
enough information to answer this question.
```

This is particularly important because academic and administrative decisions can have real consequences.

---

# 👥 Human-in-the-Loop Governance

DepartmentAI is designed as an **assistive system**, not an autonomous decision-maker.

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

This architecture ensures that AI assistance does not replace institutional authority.

---

# 🏛️ Planned Academic Modules

The long-term system is intended to support:

### Undergraduate

* DUGC processes
* Registration
* Academic performance
* Degree requirements
* Minor programmes
* Honours
* Research programmes
* Academic deficiencies

### Postgraduate

* DMPC-related processes
* Academic requirements
* Registration
* Thesis-related workflows

### Ph.D.

* DDPC processes
* Research-related workflows
* Academic requirements
* Progress-related workflows

---

# 💬 Planned Multilingual Chatbot

A future chatbot will allow students and faculty to ask questions such as:

```text
What documents are required for this application?

Am I eligible for this programme?

What does the ordinance say about late registration?

What happens if my academic performance becomes deficient?

What is the status of my application?

What deficiency exists in my submission?
```

The chatbot will use approved:

* Ordinances
* Rules
* Regulations
* Circulars
* Notifications
* Previous authorized decisions

The chatbot will provide information and assistance but will **not independently approve or reject applications**.

---

# ⚙️ Planned Agentic Workflow

Future versions will introduce specialized AI agents.

A conceptual architecture is:

```text
                    DepartmentAI
                         │
              ┌──────────┼──────────┐
              │          │          │
              ▼          ▼          ▼
        Knowledge     Document    Workflow
          Agent        Agent        Agent
              │          │          │
              └──────────┼──────────┘
                         │
                         ▼
                 Human Verification
                         │
                         ▼
                 Authorized Decision
```

Potential agents include:

* Knowledge Retrieval Agent
* Document Processing Agent
* Eligibility Analysis Agent
* Application Validation Agent
* Deficiency Detection Agent
* Workflow Agent
* Report Generation Agent
* Minutes Generation Agent

---

# 📁 Project Structure

```text
DepartmentAI/
│
├── venv/
│
├── ai/
│   ├── ingestion/
│   │   ├── pdf_parser.py
│   │   ├── structure_parser.py
│   │   └── intelligent_chunker.py
│   │
│   └── embeddings/
│       ├── embedding_generator.py
│       └── embedding_config.py
│
├── documents/
│   └── ug/
│       ├── UG Ordinance.pdf
│       │
│       └── processed/
│           ├── ug_ordinance_pages.json
│           ├── ug_ordinance_text.txt
│           ├── ug_ordinance_structure.json
│           ├── ug_ordinance_chunks.json
│           └── ug_ordinance_embeddings.json
│
├── backend/
│   ├── ingest_knowledge_base.py
│   │
│   └── retrieval/
│       └── semantic_search.py
│
├── frontend/
│
├── tests/
│
├── requirements.txt
├── .gitignore
└── README.md
```

---

# 💻 Development Environment

The project is currently developed on:

```text
Windows 11
Python 3.14.6
VS Code
PostgreSQL 18
```

The Python environment uses a project-local virtual environment:

```text
venv/
```

The virtual environment is intentionally excluded from version control.

---

# 🔐 Security

Sensitive credentials must never be committed to GitHub.

The repository excludes:

```text
.env
API keys
Database passwords
Proxy credentials
Model caches
Virtual environments
Local databases
Log files
```

API keys should be stored through environment variables.

Example:

```env
GEMINI_API_KEY=your_api_key_here
```

> Never commit the actual API key to GitHub.

---

# 🧪 Testing Strategy

DepartmentAI will be evaluated using representative academic questions.

Initial test questions include:

```text
1. What are the requirements for earning a B.Tech degree?

2. What degrees can be awarded under the undergraduate programme?

3. What are the requirements for a B.Tech Honours degree?

4. What is B.Tech with Research?

5. What are the rules regarding registration in a semester?

6. What happens if a student's academic performance becomes deficient?

7. What are the requirements for academic performance?

8. What is the process for late registration?

9. What are the requirements for registering for a Minor Programme?

10. What happens when a student's programme is terminated?
```

Each test evaluates:

```text
Question
   ↓
Retrieved Context
   ↓
LLM Answer
   ↓
Correctness
   ↓
Grounding
```

The primary evaluation criterion is:

> **Does the final answer correctly answer the question using only the official UG Ordinance content?**

---

# 📊 Current Project Status

| Component                | Status         |
| ------------------------ | -------------- |
| Project structure        | ✅ Complete     |
| Python environment       | ✅ Complete     |
| PDF parsing              | ✅ Complete     |
| Structure parsing        | ✅ Complete     |
| Clause detection         | ✅ Complete     |
| Intelligent chunking     | ✅ Complete     |
| 246 knowledge chunks     | ✅ Complete     |
| Embedding generation     | ✅ Complete     |
| 246 × 384 embeddings     | ✅ Complete     |
| Local embedding model    | ✅ Complete     |
| PostgreSQL 18            | ✅ Complete     |
| pgvector 0.8.6           | ✅ Complete     |
| Database schema          | ✅ Complete     |
| Document ingestion       | ✅ Complete     |
| 246 chunks in PostgreSQL | ✅ Complete     |
| Semantic retrieval       | ✅ Complete     |
| Keyword reranking        | ✅ Complete     |
| LLM answer generation    | 🚧 In Progress |
| Retrieval evaluation     | 🚧 In Progress |
| Metadata correction      | ⏳ Planned      |
| Traceability validation  | ⏳ Planned      |
| FastAPI integration      | ⏳ Planned      |
| Multilingual chatbot     | ⏳ Planned      |
| Agentic workflows        | ⏳ Planned      |
| DUGC automation          | ⏳ Planned      |
| DMPC automation          | ⏳ Planned      |
| DDPC automation          | ⏳ Planned      |

---

# 🛣️ Development Roadmap

```text
Phase 1
Project Foundation
        ↓
Phase 2
Document Intelligence
        ↓
Phase 3
Knowledge Extraction
        ↓
Phase 4
Chunking + Embeddings
        ↓
Phase 5
PostgreSQL + pgvector
        ↓
Phase 6
Semantic Retrieval
        ↓
Phase 7
LLM Answer Generation
        ↓
Phase 8
Retrieval Evaluation
        ↓
Phase 9
Metadata + Traceability
        ↓
Phase 10
FastAPI Backend
        ↓
Phase 11
Chatbot Interface
        ↓
Phase 12
Application Workflows
        ↓
Phase 13
AI Agents
        ↓
Phase 14
DUGC / DMPC / DDPC Automation
        ↓
Phase 15
Institutional Reporting
```

---

# 🎯 Design Principles

DepartmentAI follows these principles:

### 1. Accuracy First

Correct academic information is more important than unnecessary system complexity.

### 2. Grounded AI

LLMs should answer using authoritative institutional sources.

### 3. Human Oversight

AI assists officials but does not replace institutional decision-making.

### 4. Incremental Development

Complex infrastructure is introduced only when required.

### 5. Privacy and Security

Sensitive institutional information and credentials must be protected.

### 6. Traceability

The system should eventually allow answers to be traced back to:

```text
Document
   ↓
Section
   ↓
Clause
   ↓
Page
   ↓
Retrieved Chunk
   ↓
Generated Answer
```

### 7. Maintainability

The architecture should remain understandable and maintainable rather than introducing unnecessary distributed infrastructure prematurely.

---

# 🚀 Getting Started

## 1. Clone the Repository

```bash
git clone <your-private-repository-url>
cd DepartmentAI
```

## 2. Create a Virtual Environment

```bash
python -m venv venv
```

Activate it on Windows:

```powershell
.\venv\Scripts\Activate.ps1
```

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

## 4. Configure Environment Variables

Create a local `.env` file:

```env
DATABASE_URL=your_database_connection_string
GEMINI_API_KEY=your_api_key
```

Never commit `.env`.

## 5. Start PostgreSQL

Ensure PostgreSQL is running and the `departmentai` database is available.

## 6. Verify pgvector

Inside PostgreSQL:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

Verify:

```sql
SELECT extversion
FROM pg_extension
WHERE extname = 'vector';
```

---

# 📌 Current Implementation Notes

The project intentionally avoids unnecessary infrastructure at the current development stage.

The current architecture does **not** require:

* Kubernetes
* Redis
* Microservices
* Distributed databases
* Complex message queues
* Large local LLMs
* Model training
* Fine-tuning

The focus is currently:

```text
Correctness
     ↓
Reliable Retrieval
     ↓
Grounded Answers
     ↓
Testing
     ↓
Traceability
     ↓
Workflow Automation
     ↓
Scalability
```

---

# 🔮 Future Enhancements

Potential future improvements include:

* Multilingual academic chatbot
* OCR for scanned documents
* Advanced document classification
* Application document validation
* Eligibility analysis
* Deficiency detection
* Automated report generation
* AI-assisted meeting minutes
* Committee workflow automation
* Faculty information management
* Institutional analytics
* Advanced citation and traceability
* Role-based access control
* Audit logs
* Notification systems
* Human approval workflows
* Additional academic ordinances
* DUGC / DMPC / DDPC automation

---

# 🤝 Contribution

This project is currently being developed as an academic and research-oriented system.

Future contributions may include:

* New document processors
* Retrieval improvements
* Evaluation datasets
* Workflow modules
* Agent implementations
* UI improvements
* Testing
* Security enhancements
* Institutional integrations

---

# ⚠️ Disclaimer

DepartmentAI is an **assistive academic information and automation system**.

Information retrieved or generated by the system should be verified against the latest official institutional documents before being used for formal academic or administrative decisions.

The system does not replace authorized institutional officials or official university procedures.

---

# 📜 License

This project is currently intended for academic/research purposes.

License information will be added as the project reaches its appropriate release stage.

---

# 👨‍💻 Project Status

**DepartmentAI is actively under development.**

Current focus:

> **Building a reliable RAG-based academic knowledge assistant for undergraduate ordinances and DUGC processes.**

The immediate milestone is:

```text
Reliable Retrieval
        +
Grounded LLM Answer Generation
        +
Evaluation
```

followed by traceability, API integration, and academic workflow automation.

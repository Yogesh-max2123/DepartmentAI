CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS applications (
    id SERIAL PRIMARY KEY,
    application_number TEXT NOT NULL UNIQUE,
    applicant_identifier TEXT NOT NULL,
    application_type TEXT NOT NULL,
    title TEXT,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'DRAFT',
    submitted_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS application_status_history (
    id SERIAL PRIMARY KEY,
    application_id INTEGER REFERENCES applications(id) ON DELETE CASCADE,
    old_status TEXT,
    new_status TEXT NOT NULL,
    changed_by TEXT NOT NULL,
    reason TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS application_documents (
    id SERIAL PRIMARY KEY,
    application_id INTEGER REFERENCES applications(id) ON DELETE CASCADE,
    file_name TEXT NOT NULL,
    document_type TEXT,
    file_path TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    mime_type TEXT,
    upload_status TEXT NOT NULL DEFAULT 'UPLOADED',
    uploaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS document_extractions (
    id SERIAL PRIMARY KEY,
    application_document_id INTEGER NOT NULL
        REFERENCES application_documents(id) ON DELETE CASCADE,
    extracted_text TEXT,
    extraction_status TEXT NOT NULL,
    confidence NUMERIC,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ai_analyses (
    id SERIAL PRIMARY KEY,
    application_id INTEGER NOT NULL
        REFERENCES applications(id) ON DELETE CASCADE,
    analysis_type TEXT NOT NULL,
    input_reference TEXT,
    analysis_result TEXT,
    recommendation TEXT,
    model TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS committee_reviews (
    id SERIAL PRIMARY KEY,
    application_id INTEGER REFERENCES applications(id) ON DELETE CASCADE,
    committee_type TEXT NOT NULL,
    assigned_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    review_status TEXT NOT NULL DEFAULT 'PENDING',
    decision TEXT,
    decision_reason TEXT,
    decided_by TEXT,
    decided_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
    application_id INTEGER REFERENCES applications(id) ON DELETE CASCADE,
    actor_type TEXT NOT NULL,
    actor_id TEXT,
    action TEXT NOT NULL,
    details JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS auth_users (
    id SERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('STUDENT', 'OFFICIAL', 'DUGC')),
    subject_identifier TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS auth_sessions (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES auth_users(id) ON DELETE CASCADE,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS official_application_assignments (
    application_id INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES auth_users(id) ON DELETE CASCADE,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (application_id, user_id)
);

CREATE TABLE IF NOT EXISTS committee_memberships (
    user_id INTEGER NOT NULL REFERENCES auth_users(id) ON DELETE CASCADE,
    committee_type TEXT NOT NULL CHECK (
        committee_type IN ('DUGC', 'DMPC', 'DDPC')
    ),
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, committee_type)
);

CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    file_name TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sections (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    section_number TEXT NOT NULL,
    title TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    section_id INTEGER REFERENCES sections(id) ON DELETE CASCADE,
    chunk_index INTEGER,
    chunk_type TEXT,
    clause_number TEXT,
    chunk_text TEXT,
    page_start INTEGER,
    page_end INTEGER,
    form_id TEXT,
    metadata JSONB,
    embedding vector
);

CREATE TABLE IF NOT EXISTS application_requirements (
    id SERIAL PRIMARY KEY,
    application_id INTEGER NOT NULL
        REFERENCES applications(id) ON DELETE CASCADE,
    requirement_description TEXT NOT NULL,
    requirement_type TEXT,
    source_section_id INTEGER REFERENCES sections(id) ON DELETE SET NULL,
    source_chunk_id INTEGER REFERENCES knowledge_chunks(id) ON DELETE SET NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS eligibility_results (
    id SERIAL PRIMARY KEY,
    application_id INTEGER NOT NULL
        REFERENCES applications(id) ON DELETE CASCADE,
    requirement_id INTEGER NOT NULL
        REFERENCES application_requirements(id) ON DELETE CASCADE,
    result TEXT NOT NULL,
    evidence TEXT,
    confidence NUMERIC,
    analysis_reference TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS deficiencies (
    id SERIAL PRIMARY KEY,
    application_id INTEGER NOT NULL
        REFERENCES applications(id) ON DELETE CASCADE,
    requirement_id INTEGER NOT NULL
        REFERENCES application_requirements(id) ON DELETE CASCADE,
    description TEXT NOT NULL,
    evidence TEXT,
    severity TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'OPEN',
    source_chunk_id INTEGER REFERENCES knowledge_chunks(id) ON DELETE SET NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_document_extractions_document
    ON document_extractions(application_document_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_application_requirements_application
    ON application_requirements(application_id);
CREATE INDEX IF NOT EXISTS idx_eligibility_results_application
    ON eligibility_results(application_id);
CREATE INDEX IF NOT EXISTS idx_deficiencies_application
    ON deficiencies(application_id);
CREATE INDEX IF NOT EXISTS idx_ai_analyses_application
    ON ai_analyses(application_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_application_status_history_application
    ON application_status_history(application_id);
CREATE INDEX IF NOT EXISTS idx_application_documents_application
    ON application_documents(application_id);
CREATE INDEX IF NOT EXISTS idx_committee_reviews_application
    ON committee_reviews(application_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_application
    ON audit_logs(application_id);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_user_expiry
    ON auth_sessions(user_id, expires_at);
CREATE INDEX IF NOT EXISTS idx_official_assignments_user
    ON official_application_assignments(user_id, application_id);
CREATE INDEX IF NOT EXISTS idx_committee_memberships_committee
    ON committee_memberships(committee_type, user_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_section
    ON knowledge_chunks(section_id);

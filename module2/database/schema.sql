-- ============================================================
-- DepartmentAI Module II
-- Faculty Profile & Institutional Reporting
-- ============================================================
-- IMPORTANT:
-- These tables belong exclusively to Module II.
-- Existing Module I tables must not be modified.
-- ============================================================


-- ============================================================
-- 1. FACULTY
-- ============================================================

CREATE TABLE IF NOT EXISTS m2_faculties (
    id BIGSERIAL PRIMARY KEY,

    full_name TEXT NOT NULL,
    designation TEXT,
    department TEXT NOT NULL DEFAULT 'Computer Science and Engineering',
    qualification TEXT,

    area_of_interest TEXT,

    phone TEXT,
    email TEXT,

    profile_url TEXT NOT NULL UNIQUE,

    source_url TEXT,
    source_name TEXT NOT NULL DEFAULT 'MNNIT CSE Website',

    source_last_fetched_at TIMESTAMP,

    verification_status TEXT NOT NULL DEFAULT 'AI_EXTRACTED'
        CHECK (
            verification_status IN (
                'AI_EXTRACTED',
                'DRAFT',
                'PENDING_VERIFICATION',
                'VERIFIED',
                'APPROVED',
                'FINAL'
            )
        ),

    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================
-- 2. EDUCATION
-- ============================================================

CREATE TABLE IF NOT EXISTS m2_education (
    id BIGSERIAL PRIMARY KEY,

    faculty_id BIGINT NOT NULL
        REFERENCES m2_faculties(id)
        ON DELETE CASCADE,

    degree TEXT NOT NULL,
    specialization TEXT,
    institution TEXT,
    year INTEGER,
    details TEXT,

    source_url TEXT,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================
-- 3. COURSES / TEACHING
-- ============================================================

CREATE TABLE IF NOT EXISTS m2_courses (
    id BIGSERIAL PRIMARY KEY,

    faculty_id BIGINT NOT NULL
        REFERENCES m2_faculties(id)
        ON DELETE CASCADE,

    course_name TEXT NOT NULL,

    course_status TEXT NOT NULL
        CHECK (course_status IN ('CURRENT', 'PAST')),

    course_code TEXT,

    academic_year TEXT,
    semester TEXT,

    source_url TEXT,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================
-- 4. RESEARCH AREAS
-- ============================================================

CREATE TABLE IF NOT EXISTS m2_research_areas (
    id BIGSERIAL PRIMARY KEY,

    faculty_id BIGINT NOT NULL
        REFERENCES m2_faculties(id)
        ON DELETE CASCADE,

    research_area TEXT NOT NULL,

    source_url TEXT,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (faculty_id, research_area)
);


-- ============================================================
-- 5. PROFESSIONAL MEMBERSHIPS
-- ============================================================

CREATE TABLE IF NOT EXISTS m2_memberships (
    id BIGSERIAL PRIMARY KEY,

    faculty_id BIGINT NOT NULL
        REFERENCES m2_faculties(id)
        ON DELETE CASCADE,

    organization TEXT NOT NULL,
    membership_type TEXT,
    membership_number TEXT,

    details TEXT,

    source_url TEXT,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================
-- 6. RESEARCH IDENTIFIERS
-- ============================================================

CREATE TABLE IF NOT EXISTS m2_research_ids (
    id BIGSERIAL PRIMARY KEY,

    faculty_id BIGINT NOT NULL
        REFERENCES m2_faculties(id)
        ON DELETE CASCADE,

    identifier_type TEXT NOT NULL,
    identifier_value TEXT NOT NULL,
    identifier_url TEXT,

    source_url TEXT,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (faculty_id, identifier_type)
);


-- ============================================================
-- 7. RESPONSIBILITIES / APPOINTMENTS
-- ============================================================

CREATE TABLE IF NOT EXISTS m2_responsibilities (
    id BIGSERIAL PRIMARY KEY,

    faculty_id BIGINT NOT NULL
        REFERENCES m2_faculties(id)
        ON DELETE CASCADE,

    role_title TEXT NOT NULL,
    organization TEXT,
    department TEXT,

    start_date DATE,
    end_date DATE,

    is_current BOOLEAN,

    details TEXT,

    source_url TEXT,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================
-- 8. PUBLICATIONS
-- ============================================================

CREATE TABLE IF NOT EXISTS m2_publications (
    id BIGSERIAL PRIMARY KEY,

    title TEXT NOT NULL,

    publication_type TEXT NOT NULL,

    journal_or_conference TEXT,
    publisher TEXT,

    publication_date DATE,
    publication_year INTEGER,

    volume TEXT,
    issue TEXT,
    pages TEXT,

    doi TEXT,
    indexing_information TEXT,
    impact_information TEXT,

    authors TEXT,

    source_url TEXT,
    source_document TEXT,

    raw_metadata JSONB,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================
-- 9. FACULTY ↔ PUBLICATION
-- ============================================================

CREATE TABLE IF NOT EXISTS m2_faculty_publications (
    id BIGSERIAL PRIMARY KEY,

    faculty_id BIGINT NOT NULL
        REFERENCES m2_faculties(id)
        ON DELETE CASCADE,

    publication_id BIGINT NOT NULL
        REFERENCES m2_publications(id)
        ON DELETE CASCADE,

    author_position INTEGER,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (faculty_id, publication_id)
);


-- ============================================================
-- 10. PROJECTS
-- ============================================================

CREATE TABLE IF NOT EXISTS m2_projects (
    id BIGSERIAL PRIMARY KEY,

    title TEXT NOT NULL,

    funding_agency TEXT,
    reference_number TEXT,

    start_date DATE,
    end_date DATE,

    amount NUMERIC(15,2),
    currency TEXT DEFAULT 'INR',

    status TEXT,

    description TEXT,

    source_url TEXT,

    raw_metadata JSONB,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================
-- 11. FACULTY ↔ PROJECT
-- ============================================================

CREATE TABLE IF NOT EXISTS m2_faculty_projects (
    id BIGSERIAL PRIMARY KEY,

    faculty_id BIGINT NOT NULL
        REFERENCES m2_faculties(id)
        ON DELETE CASCADE,

    project_id BIGINT NOT NULL
        REFERENCES m2_projects(id)
        ON DELETE CASCADE,

    role TEXT,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (faculty_id, project_id)
);


-- ============================================================
-- 12. ACADEMIC ACHIEVEMENTS
-- ============================================================

CREATE TABLE IF NOT EXISTS m2_achievements (
    id BIGSERIAL PRIMARY KEY,

    faculty_id BIGINT NOT NULL
        REFERENCES m2_faculties(id)
        ON DELETE CASCADE,

    category TEXT NOT NULL,

    title TEXT,
    description TEXT,

    organization TEXT,
    venue TEXT,

    role TEXT,

    event_date DATE,
    start_date DATE,
    end_date DATE,
    year INTEGER,

    amount NUMERIC(15,2),
    reference_number TEXT,

    status TEXT,

    source_url TEXT,

    raw_metadata JSONB,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================
-- 13. THESIS SUPERVISION
-- ============================================================

CREATE TABLE IF NOT EXISTS m2_thesis_supervision (
    id BIGSERIAL PRIMARY KEY,

    faculty_id BIGINT NOT NULL
        REFERENCES m2_faculties(id)
        ON DELETE CASCADE,

    program_level TEXT NOT NULL,

    student_name TEXT NOT NULL,
    research_topic TEXT,

    registration_year INTEGER,
    completion_year INTEGER,

    status TEXT,

    details TEXT,

    source_url TEXT,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================
-- INDEXES
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_m2_education_faculty
    ON m2_education(faculty_id);

CREATE INDEX IF NOT EXISTS idx_m2_courses_faculty
    ON m2_courses(faculty_id);

CREATE INDEX IF NOT EXISTS idx_m2_research_areas_faculty
    ON m2_research_areas(faculty_id);

CREATE INDEX IF NOT EXISTS idx_m2_memberships_faculty
    ON m2_memberships(faculty_id);

CREATE INDEX IF NOT EXISTS idx_m2_research_ids_faculty
    ON m2_research_ids(faculty_id);

CREATE INDEX IF NOT EXISTS idx_m2_responsibilities_faculty
    ON m2_responsibilities(faculty_id);

CREATE INDEX IF NOT EXISTS idx_m2_publications_year
    ON m2_publications(publication_year);

CREATE INDEX IF NOT EXISTS idx_m2_publications_type
    ON m2_publications(publication_type);

CREATE INDEX IF NOT EXISTS idx_m2_faculty_publications_faculty
    ON m2_faculty_publications(faculty_id);

CREATE INDEX IF NOT EXISTS idx_m2_projects_status
    ON m2_projects(status);

CREATE INDEX IF NOT EXISTS idx_m2_faculty_projects_faculty
    ON m2_faculty_projects(faculty_id);

CREATE INDEX IF NOT EXISTS idx_m2_achievements_faculty
    ON m2_achievements(faculty_id);

CREATE INDEX IF NOT EXISTS idx_m2_achievements_category
    ON m2_achievements(category);

CREATE INDEX IF NOT EXISTS idx_m2_thesis_faculty
    ON m2_thesis_supervision(faculty_id);

CREATE INDEX IF NOT EXISTS idx_m2_thesis_program
    ON m2_thesis_supervision(program_level);
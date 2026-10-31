"""Persistence helpers for the M.Tech application workflow."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, TypedDict

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import Json, RealDictCursor


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

DB_NAME = os.getenv("DEPARTMENTAI_DB_NAME", "departmentai")
DB_USER = os.getenv("DEPARTMENTAI_DB_USER", "postgres")
DB_HOST = os.getenv("DEPARTMENTAI_DB_HOST", "localhost")
DB_PORT = int(os.getenv("DEPARTMENTAI_DB_PORT", "5432"))
DB_PASSWORD = os.getenv("DEPARTMENTAI_DB_PASSWORD")

ApplicationStatus = Literal[
    "SUBMITTED",
    "UNDER_REVIEW",
    "DEFICIENCY_FOUND",
    "RESUBMITTED",
    "CLAIMED_BY_OFFICIAL",
    "APPROVED_BY_OFFICIAL",
    "MEETING_PROPOSED",
    "RESCHEDULE_REQUESTED",
    "MEETING_SCHEDULED",
    "MINUTES_GENERATED",
    "REJECTED",
]

APPLICATION_STATUSES = (
    "SUBMITTED",
    "UNDER_REVIEW",
    "DEFICIENCY_FOUND",
    "RESUBMITTED",
    "CLAIMED_BY_OFFICIAL",
    "APPROVED_BY_OFFICIAL",
    "MEETING_PROPOSED",
    "RESCHEDULE_REQUESTED",
    "MEETING_SCHEDULED",
    "MINUTES_GENERATED",
    "REJECTED",
)

APPLICATION_STATUS_CHECK = ", ".join(
    f"'{application_status}'" for application_status in APPLICATION_STATUSES
)


class ApplicationRecord(TypedDict):
    id: int
    student_reg_no: str
    student_name: str | None
    category: str
    subject: str
    description: str
    uploaded_files: list[dict[str, Any]]
    ai_analysis: dict[str, Any]
    status: ApplicationStatus
    claimed_by: str | None
    official_rag_recommendation: str | None
    official_rag_sources: list[dict[str, Any]]
    official_remarks: str | None
    scheduler_proposal_id: str | None
    scheduler_proposal_data: dict[str, Any]
    approved_slot: dict[str, Any]
    meeting_notes: str | None
    final_decision: str | None
    generated_minutes: str | None
    revision_count: int
    official_history: list[dict[str, Any]]
    student_remarks: str | None
    created_at: datetime
    updated_at: datetime


APPLICATION_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS mtech_applications (
    id SERIAL PRIMARY KEY,
    student_reg_no TEXT NOT NULL,
    student_name TEXT,
    category TEXT NOT NULL,
    subject TEXT NOT NULL,
    description TEXT NOT NULL,
    uploaded_files JSONB DEFAULT '[]',
    ai_analysis JSONB DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'SUBMITTED',
    claimed_by TEXT,
    official_rag_recommendation TEXT,
    official_rag_sources JSONB DEFAULT '[]',
    official_remarks TEXT,
    scheduler_proposal_id TEXT,
    scheduler_proposal_data JSONB DEFAULT '{}',
    approved_slot JSONB DEFAULT '{}',
    meeting_notes TEXT,
    final_decision TEXT,
    generated_minutes TEXT,
    revision_count INTEGER DEFAULT 0,
    official_history JSONB DEFAULT '[]',
    student_remarks TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT mtech_applications_status_check CHECK (
        status IN (__APPLICATION_STATUS_CHECK__)
    )
);
""".replace("__APPLICATION_STATUS_CHECK__", APPLICATION_STATUS_CHECK)

APPLICATION_MIGRATION_SQL = (
    "ALTER TABLE mtech_applications "
    "ADD COLUMN IF NOT EXISTS revision_count INTEGER DEFAULT 0;",
    "ALTER TABLE mtech_applications "
    "ADD COLUMN IF NOT EXISTS official_history JSONB DEFAULT '[]';",
    "ALTER TABLE mtech_applications "
    "ADD COLUMN IF NOT EXISTS student_remarks TEXT;",
    "ALTER TABLE mtech_applications "
    "ALTER COLUMN revision_count SET DEFAULT 0;",
    "ALTER TABLE mtech_applications "
    "ALTER COLUMN official_history SET DEFAULT '[]'::jsonb;",
    "ALTER TABLE mtech_applications "
    "DROP CONSTRAINT IF EXISTS mtech_applications_status_check;",
    f"""
    ALTER TABLE mtech_applications
    ADD CONSTRAINT mtech_applications_status_check
    CHECK (status IN ({APPLICATION_STATUS_CHECK}));
    """,
)

HISTORY_APPEND_SQL = """
COALESCE(official_history, '[]'::jsonb) ||
jsonb_build_array(jsonb_build_object(
    'action', %s,
    'timestamp', NOW(),
    'actor', %s,
    'remarks', %s
))
"""


def connect_database():
    if not DB_PASSWORD:
        raise RuntimeError(
            "DEPARTMENTAI_DB_PASSWORD environment variable is not set."
        )
    return psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
    )


def initialize_workflow_db() -> None:
    connection = connect_database()
    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(APPLICATION_TABLE_SQL)
                for statement in APPLICATION_MIGRATION_SQL:
                    cursor.execute(statement)
    finally:
        connection.close()


def _fetch_one(query: str, values: tuple = ()) -> ApplicationRecord | None:
    connection = connect_database()
    try:
        with connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, values)
                row = cursor.fetchone()
                return dict(row) if row is not None else None
    finally:
        connection.close()


def _fetch_all(query: str, values: tuple = ()) -> list[ApplicationRecord]:
    connection = connect_database()
    try:
        with connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, values)
                return [dict(row) for row in cursor.fetchall()]
    finally:
        connection.close()


def get_application(application_id: int) -> ApplicationRecord | None:
    return _fetch_one(
        "SELECT * FROM mtech_applications WHERE id = %s;",
        (application_id,),
    )


def create_application(values: dict[str, Any]) -> ApplicationRecord:
    query = """
    INSERT INTO mtech_applications (
        student_reg_no, student_name, category, subject, description,
        uploaded_files, ai_analysis, student_remarks
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    RETURNING *;
    """
    connection = connect_database()
    try:
        with connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    query,
                    (
                        values["student_reg_no"],
                        values.get("student_name"),
                        values["category"],
                        values["subject"],
                        values["description"],
                        Json(values["uploaded_files"]),
                        Json(values["ai_analysis"]),
                        values.get("student_remarks"),
                    ),
                )
                return dict(cursor.fetchone())
    finally:
        connection.close()


def resubmit_application(
    application_id: int,
    student_reg_no: str,
    uploaded_files: list[dict[str, Any]],
    student_remarks: str,
    ai_analysis: dict[str, Any],
) -> ApplicationRecord | None:
    return _update_application(
        f"""
        UPDATE mtech_applications
        SET status = 'RESUBMITTED',
            revision_count = COALESCE(revision_count, 0) + 1,
            uploaded_files = COALESCE(uploaded_files, '[]'::jsonb) || %s,
            student_remarks = %s,
            ai_analysis = %s,
            claimed_by = NULL,
            official_history = {HISTORY_APPEND_SQL},
            updated_at = NOW()
        WHERE id = %s
          AND student_reg_no = %s
          AND status = 'DEFICIENCY_FOUND'
        RETURNING *;
        """,
        (
            Json(uploaded_files),
            student_remarks,
            Json(ai_analysis),
            "RESUBMITTED",
            student_reg_no,
            student_remarks,
            application_id,
            student_reg_no,
        ),
    )


def list_student_applications(student_reg_no: str) -> list[ApplicationRecord]:
    return _fetch_all(
        """
        SELECT * FROM mtech_applications
        WHERE student_reg_no = %s
        ORDER BY created_at DESC, id DESC;
        """,
        (student_reg_no,),
    )


def list_official_applications() -> list[ApplicationRecord]:
    return _fetch_all(
        """
        SELECT * FROM mtech_applications
        WHERE status IN (
            'SUBMITTED', 'UNDER_REVIEW', 'DEFICIENCY_FOUND',
            'RESUBMITTED', 'CLAIMED_BY_OFFICIAL', 'RESCHEDULE_REQUESTED'
        )
        ORDER BY created_at ASC, id ASC;
        """
    )


def list_dmpc_applications() -> list[ApplicationRecord]:
    return _fetch_all(
        """
        SELECT * FROM mtech_applications
        WHERE status IN (
            'MEETING_PROPOSED', 'RESCHEDULE_REQUESTED',
            'MEETING_SCHEDULED', 'MINUTES_GENERATED'
        )
        ORDER BY updated_at DESC, id DESC;
        """
    )


def claim_application(
    application_id: int, official_id: str
) -> ApplicationRecord | None:
    connection = connect_database()
    try:
        with connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    f"""
                    UPDATE mtech_applications
                    SET status = 'CLAIMED_BY_OFFICIAL',
                        claimed_by = %s,
                        official_history = {HISTORY_APPEND_SQL},
                        updated_at = NOW()
                    WHERE id = %s
                      AND status IN (
                          'SUBMITTED', 'UNDER_REVIEW',
                          'RESUBMITTED', 'RESCHEDULE_REQUESTED'
                      )
                    RETURNING *;
                    """,
                    (
                        official_id,
                        "CLAIMED_BY_OFFICIAL",
                        official_id,
                        "",
                        application_id,
                    ),
                )
                row = cursor.fetchone()
                return dict(row) if row is not None else None
    finally:
        connection.close()


def mark_application_under_review(
    application_id: int,
    official_id: str,
    remarks: str,
) -> ApplicationRecord | None:
    return _update_application(
        f"""
        UPDATE mtech_applications
        SET status = 'UNDER_REVIEW',
            claimed_by = NULL,
            official_remarks = %s,
            official_history = {HISTORY_APPEND_SQL},
            updated_at = NOW()
        WHERE id = %s
          AND status = 'CLAIMED_BY_OFFICIAL'
          AND claimed_by = %s
        RETURNING *;
        """,
        (
            remarks,
            "UNDER_REVIEW",
            official_id,
            remarks,
            application_id,
            official_id,
        ),
    )


def send_application_back_for_deficiency(
    application_id: int,
    official_id: str,
    remarks: str,
) -> ApplicationRecord | None:
    return _update_application(
        f"""
        UPDATE mtech_applications
        SET status = 'DEFICIENCY_FOUND',
            claimed_by = NULL,
            official_remarks = %s,
            official_history = {HISTORY_APPEND_SQL},
            updated_at = NOW()
        WHERE id = %s
          AND status = 'CLAIMED_BY_OFFICIAL'
          AND claimed_by = %s
        RETURNING *;
        """,
        (
            remarks,
            "DEFICIENCY_FOUND",
            official_id,
            remarks,
            application_id,
            official_id,
        ),
    )


def save_recommendation(
    application_id: int,
    recommendation: str,
    sources: list[dict[str, Any]],
    actor_id: str | None = None,
) -> ApplicationRecord | None:
    return _update_application(
        f"""
        UPDATE mtech_applications
        SET official_rag_recommendation = %s,
            official_rag_sources = %s,
            official_history = {HISTORY_APPEND_SQL},
            updated_at = NOW()
        WHERE id = %s AND status = 'CLAIMED_BY_OFFICIAL'
        RETURNING *;
        """,
        (
            recommendation,
            Json(sources),
            "OFFICIAL_RAG_RECOMMENDATION",
            actor_id or "",
            "",
            application_id,
        ),
    )


def save_direct_approval(
    application_id: int, remarks: str, actor_id: str | None = None
) -> ApplicationRecord | None:
    return _update_application(
        f"""
        UPDATE mtech_applications
        SET status = 'APPROVED_BY_OFFICIAL',
            official_remarks = %s,
            official_history = {HISTORY_APPEND_SQL},
            updated_at = NOW()
        WHERE id = %s AND status = 'CLAIMED_BY_OFFICIAL'
        RETURNING *;
        """,
        (remarks, "APPROVED_BY_OFFICIAL", actor_id or "", remarks, application_id),
    )


def save_meeting_proposal(
    application_id: int,
    remarks: str,
    proposal_id: str,
    proposal_data: dict[str, Any],
    actor_id: str | None = None,
) -> ApplicationRecord | None:
    return _update_application(
        f"""
        UPDATE mtech_applications
        SET status = 'MEETING_PROPOSED',
            official_remarks = %s,
            scheduler_proposal_id = %s,
            scheduler_proposal_data = %s,
            official_history = {HISTORY_APPEND_SQL},
            updated_at = NOW()
        WHERE id = %s AND status = 'CLAIMED_BY_OFFICIAL'
        RETURNING *;
        """,
        (
            remarks,
            proposal_id,
            Json(proposal_data),
            "MEETING_PROPOSED",
            actor_id or "",
            remarks,
            application_id,
        ),
    )


def save_meeting_approval(
    application_id: int,
    approved_slot: dict[str, Any],
    actor_id: str | None = None,
    remarks: str = "",
) -> ApplicationRecord | None:
    return _update_application(
        f"""
        UPDATE mtech_applications
        SET status = 'MEETING_SCHEDULED',
            approved_slot = %s,
            official_history = {HISTORY_APPEND_SQL},
            updated_at = NOW()
        WHERE id = %s AND status = 'MEETING_PROPOSED'
        RETURNING *;
        """,
        (
            Json(approved_slot),
            "MEETING_SCHEDULED",
            actor_id or "",
            remarks,
            application_id,
        ),
    )


def request_meeting_reschedule(
    application_id: int,
    dmpc_id: str,
    remarks: str,
) -> ApplicationRecord | None:
    return _update_application(
        f"""
        UPDATE mtech_applications
        SET status = 'RESCHEDULE_REQUESTED',
            official_remarks = %s,
            official_history = {HISTORY_APPEND_SQL},
            updated_at = NOW()
        WHERE id = %s AND status = 'MEETING_PROPOSED'
        RETURNING *;
        """,
        (
            remarks,
            "RESCHEDULE_REQUESTED",
            dmpc_id,
            remarks,
            application_id,
        ),
    )


def save_minutes(
    application_id: int,
    meeting_notes: str,
    final_decision: str,
    generated_minutes: str,
    actor_id: str | None = None,
) -> ApplicationRecord | None:
    return _update_application(
        f"""
        UPDATE mtech_applications
        SET status = 'MINUTES_GENERATED',
            meeting_notes = %s,
            final_decision = %s,
            generated_minutes = %s,
            official_history = {HISTORY_APPEND_SQL},
            updated_at = NOW()
        WHERE id = %s AND status = 'MEETING_SCHEDULED'
        RETURNING *;
        """,
        (
            meeting_notes,
            final_decision,
            generated_minutes,
            "MINUTES_GENERATED",
            actor_id or "",
            final_decision,
            application_id,
        ),
    )


def _update_application(
    query: str, values: tuple
) -> ApplicationRecord | None:
    connection = connect_database()
    try:
        with connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, values)
                row = cursor.fetchone()
                return dict(row) if row is not None else None
    finally:
        connection.close()

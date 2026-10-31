"""Create the knowledge-base schema and seed its required source records."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2 import sql
from psycopg2.extras import Json
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STRUCTURE_FILE = (
    PROJECT_ROOT
    / "documents"
    / "mtech"
    / "processed"
    / "mtech_ordinance_structure.json"
)
SCHEDULER_DATA_SCRIPT = (
    PROJECT_ROOT / "ai" / "ingestion" / "synthetic_scheduler_data.py"
)
SOURCE_FILE_NAME = "Ordinances for Masters Programme 2023.pdf"
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

load_dotenv(PROJECT_ROOT / ".env")

DB_NAME = os.getenv("DEPARTMENTAI_DB_NAME", "departmentai")
DB_USER = os.getenv("DEPARTMENTAI_DB_USER", "postgres")
DB_HOST = os.getenv("DEPARTMENTAI_DB_HOST", "localhost")
DB_PORT = int(os.getenv("DEPARTMENTAI_DB_PORT", "5432"))
DB_PASSWORD = os.getenv("DEPARTMENTAI_DB_PASSWORD")


def load_ordinance_structure() -> dict[str, Any]:
    if not STRUCTURE_FILE.is_file():
        raise FileNotFoundError(f"Ordinance structure file not found: {STRUCTURE_FILE}")

    structure = json.loads(STRUCTURE_FILE.read_text(encoding="utf-8"))
    document = structure.get("document")
    sections = structure.get("sections")
    if not isinstance(document, dict) or not isinstance(sections, list):
        raise ValueError(
            f"Invalid ordinance structure: expected document and sections in {STRUCTURE_FILE}"
        )
    if len(sections) != 16:
        raise ValueError(
            f"Expected 16 ordinance sections in {STRUCTURE_FILE}, found {len(sections)}."
        )
    if document.get("source_file") != SOURCE_FILE_NAME:
        raise ValueError(
            "The ordinance structure's source_file does not match "
            f"{SOURCE_FILE_NAME!r}."
        )

    for index, section in enumerate(sections, start=1):
        required_fields = ("number", "title", "start_page", "end_page")
        if not isinstance(section, dict) or any(
            field not in section for field in required_fields
        ):
            raise ValueError(
                f"Ordinance section {index} is missing one or more required fields: "
                f"{', '.join(required_fields)}."
            )

    return structure


def connect_database():
    if not DB_PASSWORD:
        raise RuntimeError(
            "DEPARTMENTAI_DB_PASSWORD environment variable is not set. "
            "Set it in the project .env file or environment before running."
        )

    return psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
    )


def ensure_schema(cursor) -> None:
    cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS documents (
            id              SERIAL PRIMARY KEY,
            title           TEXT,
            file_name       TEXT,
            document_type   TEXT,
            version         TEXT,
            total_pages     INTEGER,
            created_at      TIMESTAMP DEFAULT NOW()
        );
        """
    )
    cursor.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS id SERIAL;")
    cursor.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS title TEXT;")
    cursor.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS file_name TEXT;")
    cursor.execute(
        "ALTER TABLE documents ADD COLUMN IF NOT EXISTS document_type TEXT;"
    )
    cursor.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS version TEXT;")
    cursor.execute(
        "ALTER TABLE documents ADD COLUMN IF NOT EXISTS total_pages INTEGER;"
    )
    cursor.execute(
        "ALTER TABLE documents ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW();"
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS sections (
            id              SERIAL PRIMARY KEY,
            document_id     INTEGER REFERENCES documents(id),
            section_number  TEXT,
            title           TEXT,
            start_page      INTEGER,
            end_page        INTEGER,
            created_at      TIMESTAMP DEFAULT NOW()
        );
        """
    )
    cursor.execute("ALTER TABLE sections ADD COLUMN IF NOT EXISTS id SERIAL;")
    cursor.execute(
        "ALTER TABLE sections ADD COLUMN IF NOT EXISTS document_id INTEGER REFERENCES documents(id);"
    )
    cursor.execute(
        "ALTER TABLE sections ADD COLUMN IF NOT EXISTS section_number TEXT;"
    )
    cursor.execute("ALTER TABLE sections ADD COLUMN IF NOT EXISTS title TEXT;")
    cursor.execute(
        "ALTER TABLE sections ADD COLUMN IF NOT EXISTS start_page INTEGER;"
    )
    cursor.execute("ALTER TABLE sections ADD COLUMN IF NOT EXISTS end_page INTEGER;")
    cursor.execute(
        "ALTER TABLE sections ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW();"
    )
    cursor.execute(
        """
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
        """
    )
    cursor.execute(
        "ALTER TABLE knowledge_chunks ADD COLUMN IF NOT EXISTS id SERIAL;"
    )
    cursor.execute(
        "ALTER TABLE knowledge_chunks ADD COLUMN IF NOT EXISTS document_id INTEGER REFERENCES documents(id);"
    )
    cursor.execute(
        "ALTER TABLE knowledge_chunks ADD COLUMN IF NOT EXISTS section_id INTEGER REFERENCES sections(id);"
    )
    cursor.execute(
        "ALTER TABLE knowledge_chunks ADD COLUMN IF NOT EXISTS chunk_index INTEGER;"
    )
    cursor.execute(
        "ALTER TABLE knowledge_chunks ADD COLUMN IF NOT EXISTS chunk_type TEXT;"
    )
    cursor.execute(
        "ALTER TABLE knowledge_chunks ADD COLUMN IF NOT EXISTS clause_number TEXT;"
    )
    cursor.execute(
        "ALTER TABLE knowledge_chunks ADD COLUMN IF NOT EXISTS chunk_text TEXT;"
    )
    cursor.execute(
        "ALTER TABLE knowledge_chunks ADD COLUMN IF NOT EXISTS page_start INTEGER;"
    )
    cursor.execute(
        "ALTER TABLE knowledge_chunks ADD COLUMN IF NOT EXISTS page_end INTEGER;"
    )
    cursor.execute(
        "ALTER TABLE knowledge_chunks ADD COLUMN IF NOT EXISTS form_id TEXT;"
    )
    cursor.execute(
        "ALTER TABLE knowledge_chunks ADD COLUMN IF NOT EXISTS metadata JSONB;"
    )
    cursor.execute(
        "ALTER TABLE knowledge_chunks ADD COLUMN IF NOT EXISTS embedding vector(384);"
    )
    cursor.execute(
        """
        ALTER TABLE knowledge_chunks
        ALTER COLUMN embedding TYPE vector(384)
        USING embedding::vector(384);
        """
    )
    cursor.execute(
        "ALTER TABLE knowledge_chunks ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW();"
    )
    allowed_statuses = ", ".join(
        f"'{application_status}'"
        for application_status in APPLICATION_STATUSES
    )
    cursor.execute(
        """
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
                status IN (__ALLOWED_STATUSES__)
            )
        );
        """.replace("__ALLOWED_STATUSES__", allowed_statuses)
    )
    cursor.execute(
        "ALTER TABLE mtech_applications "
        "ADD COLUMN IF NOT EXISTS revision_count INTEGER DEFAULT 0;"
    )
    cursor.execute(
        "ALTER TABLE mtech_applications "
        "ADD COLUMN IF NOT EXISTS official_history JSONB DEFAULT '[]';"
    )
    cursor.execute(
        "ALTER TABLE mtech_applications "
        "ADD COLUMN IF NOT EXISTS student_remarks TEXT;"
    )
    cursor.execute(
        "ALTER TABLE mtech_applications "
        "ALTER COLUMN revision_count SET DEFAULT 0;"
    )
    cursor.execute(
        "ALTER TABLE mtech_applications "
        "ALTER COLUMN official_history SET DEFAULT '[]'::jsonb;"
    )
    cursor.execute(
        "ALTER TABLE mtech_applications "
        "DROP CONSTRAINT IF EXISTS mtech_applications_status_check;"
    )
    cursor.execute(
        f"""
        ALTER TABLE mtech_applications
        ADD CONSTRAINT mtech_applications_status_check
        CHECK (status IN ({allowed_statuses}));
        """
    )


def _column_metadata(cursor, table_name: str) -> list[tuple]:
    cursor.execute(
        """
        SELECT column_name, data_type, udt_name, is_nullable,
               column_default, is_identity
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = %s
        ORDER BY ordinal_position;
        """,
        (table_name,),
    )
    return cursor.fetchall()


def _required_column_placeholder(
    cursor, data_type: str, udt_name: str
) -> Any:
    if data_type in {"character varying", "character", "text"}:
        return ""
    if data_type == "boolean":
        return False
    if data_type in {
        "smallint",
        "integer",
        "bigint",
        "numeric",
        "decimal",
        "real",
        "double precision",
    }:
        return 0
    if data_type == "date":
        return date.today()
    if data_type == "timestamp without time zone":
        return datetime.now()
    if data_type == "timestamp with time zone":
        return datetime.now(timezone.utc)
    if data_type == "json":
        return Json({})
    if data_type == "jsonb":
        return Json({})
    if data_type == "ARRAY":
        return []
    if data_type == "USER-DEFINED":
        cursor.execute(
            """
            SELECT e.enumlabel
            FROM pg_enum e
            JOIN pg_type t ON t.oid = e.enumtypid
            WHERE t.typname = %s
            ORDER BY e.enumsortorder
            LIMIT 1;
            """,
            (udt_name,),
        )
        enum_value = cursor.fetchone()
        if enum_value:
            return enum_value[0]
    raise RuntimeError(
        "Cannot seed a required NOT NULL database column with no default "
        f"(type {data_type!r}, underlying type {udt_name!r})."
    )


def _insert_seed_row(cursor, table_name: str, values: dict[str, Any]) -> int:
    columns = _column_metadata(cursor, table_name)
    if not columns:
        raise RuntimeError(f"Could not inspect columns for table {table_name!r}.")

    insert_values = dict(values)
    for (
        column_name,
        data_type,
        udt_name,
        is_nullable,
        column_default,
        is_identity,
    ) in columns:
        if (
            is_nullable == "NO"
            and column_default is None
            and is_identity != "YES"
            and column_name not in insert_values
        ):
            insert_values[column_name] = _required_column_placeholder(
                cursor, data_type, udt_name
            )

    id_column = next((column for column in columns if column[0] == "id"), None)
    if (
        id_column
        and id_column[3] == "NO"
        and id_column[4] is None
        and id_column[5] != "YES"
        and "id" not in insert_values
    ):
        cursor.execute(
            sql.SQL("SELECT COALESCE(MAX(id), 0) + 1 FROM {}").format(
                sql.Identifier(table_name)
            )
        )
        insert_values["id"] = cursor.fetchone()[0]

    insert_columns = list(insert_values)
    query = sql.SQL(
        "INSERT INTO {table} ({columns}) VALUES ({placeholders}) RETURNING id;"
    ).format(
        table=sql.Identifier(table_name),
        columns=sql.SQL(", ").join(map(sql.Identifier, insert_columns)),
        placeholders=sql.SQL(", ").join(
            sql.Placeholder() for _ in insert_columns
        ),
    )
    cursor.execute(query, tuple(insert_values[name] for name in insert_columns))
    return cursor.fetchone()[0]


def seed_ordinance(cursor, structure: dict[str, Any]) -> tuple[int, int]:
    document = structure["document"]
    cursor.execute(
        """
        SELECT id
        FROM documents
        WHERE file_name = %s
        ORDER BY id
        LIMIT 1;
        """,
        (SOURCE_FILE_NAME,),
    )
    row = cursor.fetchone()

    if row:
        document_id = row[0]
    else:
        document_id = _insert_seed_row(
            cursor,
            "documents",
            {
                "title": document["name"],
                "file_name": SOURCE_FILE_NAME,
                "document_type": "Masters' Ordinance",
                "version": "2023",
                "total_pages": document["total_pages"],
            },
        )

    inserted_sections = 0
    for section in structure["sections"]:
        section_number = str(section["number"])
        cursor.execute(
            """
            SELECT id
            FROM sections
            WHERE document_id = %s AND section_number = %s
            ORDER BY id
            LIMIT 1;
            """,
            (document_id, section_number),
        )
        if cursor.fetchone():
            continue

        _insert_seed_row(
            cursor,
            "sections",
            {
                "document_id": document_id,
                "section_number": section_number,
                "title": section["title"],
                "start_page": section["start_page"],
                "end_page": section["end_page"],
            },
        )
        inserted_sections += 1

    return document_id, inserted_sections


def generate_scheduler_data() -> None:
    if not SCHEDULER_DATA_SCRIPT.is_file():
        raise FileNotFoundError(
            f"Scheduler data generator not found: {SCHEDULER_DATA_SCRIPT}"
        )

    subprocess.run(
        [sys.executable, str(SCHEDULER_DATA_SCRIPT)],
        cwd=PROJECT_ROOT,
        check=True,
    )


def bootstrap() -> None:
    structure = load_ordinance_structure()
    connection = connect_database()
    try:
        with connection:
            with connection.cursor() as cursor:
                ensure_schema(cursor)
                document_id, inserted_sections = seed_ordinance(cursor, structure)
        print(f"PostgreSQL bootstrap complete (ordinance document ID {document_id}).")
        print(f"Ordinance sections inserted: {inserted_sections}")
    finally:
        connection.close()

    generate_scheduler_data()


def main() -> None:
    bootstrap()


if __name__ == "__main__":
    main()

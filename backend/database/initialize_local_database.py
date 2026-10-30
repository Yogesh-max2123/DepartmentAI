from pathlib import Path

from backend.database.connection import LOCAL_DATABASES, get_connection, get_database_settings


SCHEMA_FILE = Path(__file__).with_name("application_schema.sql")
EXPECTED_TABLES = {
    "applications",
    "application_status_history",
    "application_documents",
    "committee_reviews",
    "audit_logs",
    "auth_users",
    "auth_sessions",
    "official_application_assignments",
    "committee_memberships",
    "documents",
    "sections",
    "knowledge_chunks",
    "document_extractions",
    "application_requirements",
    "eligibility_results",
    "deficiencies",
    "ai_analyses",
    "governance_meetings",
    "meeting_member_availability",
    "meeting_confirmations",
    "meeting_application_links",
    "meeting_records",
    "meeting_minutes_versions",
    "meeting_minutes_comments",
}


def initialize_local_database() -> int:
    settings = get_database_settings()
    if settings.environment not in LOCAL_DATABASES:
        raise RuntimeError(
            "Schema initialization is restricted to the explicit "
            "development or test database profile."
        )

    schema_sql = SCHEMA_FILE.read_text(encoding="utf-8")
    connection = get_connection()
    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT tablename
                    FROM pg_tables
                    WHERE schemaname = 'public';
                    """
                )
                existing_tables = {row[0] for row in cursor.fetchall()}
                unexpected_tables = existing_tables - EXPECTED_TABLES
                if unexpected_tables:
                    raise RuntimeError(
                        "Refusing to initialize a local database containing "
                        "unrecognized tables: "
                        + ", ".join(sorted(unexpected_tables))
                    )

                for statement in schema_sql.split(";"):
                    if statement.strip():
                        cursor.execute(statement)
        return len(EXPECTED_TABLES - existing_tables)
    finally:
        connection.close()


if __name__ == "__main__":
    created_count = initialize_local_database()
    settings = get_database_settings()
    print(
        f"Local {settings.environment} schema ready in "
        f"{settings.database}; tables created: {created_count}."
    )

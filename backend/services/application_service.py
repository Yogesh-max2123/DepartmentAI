from backend.database.connection import get_connection


def generate_application_number(conn):
    """
    Generate a unique, human-readable application number.
    Example: APP-2026-00001
    """
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT COALESCE(MAX(id), 0) + 1
            FROM applications;
            """
        )
        next_id = cursor.fetchone()[0]

    from datetime import datetime

    year = datetime.now().year

    return f"APP-{year}-{next_id:05d}"


def create_application(
    applicant_identifier,
    application_type,
    title=None,
    description=None,
):
    """
    Create a new application in the database.

    The system automatically:
    - generates the application number
    - assigns the initial DRAFT status
    - records the creation time
    - creates the initial status-history entry
    """

    conn = get_connection()

    try:
        application_number = generate_application_number(conn)

        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO applications (
                    application_number,
                    applicant_identifier,
                    application_type,
                    title,
                    description,
                    status
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id, application_number, status, created_at;
                """,
                (
                    application_number,
                    applicant_identifier,
                    application_type,
                    title,
                    description,
                    "DRAFT",
                ),
            )

            application = cursor.fetchone()

            application_id = application[0]

            cursor.execute(
                """
                INSERT INTO application_status_history (
                    application_id,
                    old_status,
                    new_status,
                    changed_by,
                    reason
                )
                VALUES (%s, %s, %s, %s, %s);
                """,
                (
                    application_id,
                    None,
                    "DRAFT",
                    "SYSTEM",
                    "Application created",
                ),
            )

        conn.commit()

        return {
            "id": application[0],
            "application_number": application[1],
            "status": application[2],
            "created_at": application[3],
        }

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def get_application(application_id):
    """
    Retrieve an application by its database ID.
    """

    conn = get_connection()

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    application_number,
                    applicant_identifier,
                    application_type,
                    title,
                    description,
                    status,
                    submitted_at,
                    created_at,
                    updated_at
                FROM applications
                WHERE id = %s;
                """,
                (application_id,),
            )

            application = cursor.fetchone()

            if application is None:
                return None

            return {
                "id": application[0],
                "application_number": application[1],
                "applicant_identifier": application[2],
                "application_type": application[3],
                "title": application[4],
                "description": application[5],
                "status": application[6],
                "submitted_at": application[7],
                "created_at": application[8],
                "updated_at": application[9],
            }

    finally:
        conn.close()
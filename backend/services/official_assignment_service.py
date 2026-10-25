from backend.database.connection import get_connection
from backend.services.auth_service import AuthenticatedUser


def list_unassigned_submissions(limit: int, offset: int) -> list[dict]:
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT a.id, a.application_number, a.application_type,
                       a.title, a.description, a.status, a.submitted_at,
                       a.created_at, a.updated_at
                FROM applications a
                WHERE a.status = 'SUBMITTED'
                  AND NOT EXISTS (
                      SELECT 1
                      FROM official_application_assignments assignment
                      WHERE assignment.application_id = a.id
                  )
                ORDER BY a.submitted_at ASC, a.id ASC
                LIMIT %s OFFSET %s;
                """,
                (limit, offset),
            )
            rows = cursor.fetchall()
        return [
            {
                "id": row[0],
                "application_number": row[1],
                "application_type": row[2],
                "title": row[3],
                "description": row[4],
                "status": row[5],
                "submitted_at": row[6],
                "created_at": row[7],
                "updated_at": row[8],
            }
            for row in rows
        ]
    finally:
        connection.close()


def claim_application(application_id: int, official: AuthenticatedUser) -> dict:
    """Atomically assign one submitted application to a single Official."""
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT status
                FROM applications
                WHERE id = %s
                FOR UPDATE;
                """,
                (application_id,),
            )
            application = cursor.fetchone()
            if application is None:
                raise LookupError(
                    f"Application with id {application_id} does not exist."
                )
            if application[0] != "SUBMITTED":
                raise ValueError(
                    "Only submitted applications can be claimed."
                )

            cursor.execute(
                """
                SELECT 1
                FROM official_application_assignments
                WHERE application_id = %s
                LIMIT 1;
                """,
                (application_id,),
            )
            if cursor.fetchone() is not None:
                raise ValueError(
                    "This application has already been claimed by an Official."
                )

            cursor.execute(
                """
                INSERT INTO official_application_assignments
                    (application_id, user_id)
                VALUES (%s, %s)
                RETURNING assigned_at;
                """,
                (application_id, official.id),
            )
            assigned_at = cursor.fetchone()[0]
            cursor.execute(
                """
                INSERT INTO audit_logs (
                    application_id, actor_type, actor_id, action, details
                )
                VALUES (%s, 'OFFICIAL', %s, 'APPLICATION_CLAIMED', %s);
                """,
                (
                    application_id,
                    official.username,
                    '{"queue":"shared_official"}',
                ),
            )
        connection.commit()
        return {
            "application_id": application_id,
            "official_user_id": official.id,
            "assigned_at": assigned_at,
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

import json

from backend.database.connection import get_connection

def log_action(
    application_id: int | None,
    actor_type: str,
    action: str,
    actor_id: str | None = None,
    details: dict | None = None,
):
    """
    Record an action in the audit log.

    actor_type examples:
    SYSTEM, STUDENT, STAFF, COMMITTEE, ADMIN, AI
    """

    if not actor_type or not actor_type.strip():
        raise ValueError("actor_type is required.")

    if not action or not action.strip():
        raise ValueError("action is required.")

    conn = get_connection()

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO audit_logs (
                    application_id,
                    actor_type,
                    actor_id,
                    action,
                    details
                )
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, application_id, actor_type,
                          actor_id, action, details, created_at;
                """,
                (
                    application_id,
                    actor_type.strip().upper(),
                    actor_id,
                    action.strip().upper(),
                    json.dumps(details) if details is not None else None,
                ),
            )

            row = cursor.fetchone()

        conn.commit()

        return {
            "id": row[0],
            "application_id": row[1],
            "actor_type": row[2],
            "actor_id": row[3],
            "action": row[4],
            "details": row[5],
            "created_at": row[6],
        }

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def get_application_audit_logs(application_id: int):
    """
    Retrieve all audit records for an application.
    """

    conn = get_connection()

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    application_id,
                    actor_type,
                    actor_id,
                    action,
                    details,
                    created_at
                FROM audit_logs
                WHERE application_id = %s
                ORDER BY created_at ASC, id ASC;
                """,
                (application_id,),
            )

            rows = cursor.fetchall()

        return [
            {
                "id": row[0],
                "application_id": row[1],
                "actor_type": row[2],
                "actor_id": row[3],
                "action": row[4],
                "details": row[5],
                "created_at": row[6],
            }
            for row in rows
        ]

    finally:
        conn.close()

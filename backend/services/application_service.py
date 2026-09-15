from datetime import datetime

from backend.database.connection import get_connection
from backend.services.audit_service import log_action


# Allowed application status transitions.
# This prevents invalid workflow jumps.
ALLOWED_TRANSITIONS = {
    "DRAFT": {"SUBMITTED", "ON_HOLD"},
    "SUBMITTED": {"DOCUMENT_VALIDATION", "ON_HOLD"},
    "DOCUMENT_VALIDATION": {"PROCESSING", "DEFICIENCY_FOUND", "ON_HOLD"},
    "PROCESSING": {"UNDER_REVIEW", "DEFICIENCY_FOUND", "ON_HOLD"},
    "UNDER_REVIEW": {"COMMITTEE_REVIEW", "DEFICIENCY_FOUND", "ON_HOLD"},
    "DEFICIENCY_FOUND": {"CORRECTION_REQUIRED", "ON_HOLD"},
    "CORRECTION_REQUIRED": {"RESUBMITTED", "ON_HOLD"},
    "RESUBMITTED": {"PROCESSING", "ON_HOLD"},
    "COMMITTEE_REVIEW": {"APPROVED", "REJECTED", "ON_HOLD"},
    "APPROVED": {"CLOSED"},
    "REJECTED": {"CLOSED"},
    "CLOSED": set(),
    "ON_HOLD": {
        "DRAFT",
        "SUBMITTED",
        "DOCUMENT_VALIDATION",
        "PROCESSING",
        "UNDER_REVIEW",
        "COMMITTEE_REVIEW",
    },
}


def generate_application_number(conn):
    """
    Generate the next human-readable application number.
    Format: APP-YYYY-00001
    """

    year = datetime.now().year

    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT COALESCE(MAX(id), 0) + 1
            FROM applications;
            """
        )

        next_id = cursor.fetchone()[0]

    return f"APP-{year}-{next_id:05d}"


def create_application(
    applicant_identifier,
    application_type,
    title=None,
    description=None,
):
    """
    Create a new application in DRAFT status.
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
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                RETURNING
                    id,
                    application_number,
                    status,
                    created_at;
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

            # Record initial application status
            cursor.execute(
                """
                INSERT INTO application_status_history (
                    application_id,
                    old_status,
                    new_status,
                    changed_by,
                    reason
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                );
                """,
                (
                    application[0],
                    None,
                    "DRAFT",
                    "SYSTEM",
                    "Application created.",
                ),
            )

        conn.commit()

        # Record application creation in the audit trail.
        log_action(
            application_id=application[0],
            actor_type="SYSTEM",
            actor_id="SYSTEM",
            action="APPLICATION_CREATED",
            details={
                "application_number": application[1],
                "application_type": application_type,
            },
        )

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
    Retrieve an application by ID.
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


def update_application_status(
    application_id,
    new_status,
    changed_by="SYSTEM",
    reason=None,
):
    """
    Change an application's status using the allowed workflow.

    Every status change is recorded in application_status_history.
    """

    conn = get_connection()

    try:
        with conn.cursor() as cursor:

            # Get current status
            cursor.execute(
                """
                SELECT status
                FROM applications
                WHERE id = %s;
                """,
                (application_id,),
            )

            application = cursor.fetchone()

            if application is None:
                raise ValueError(
                    f"Application with id {application_id} does not exist."
                )

            current_status = application[0]

            # Same-status update is not considered a transition.
            if current_status == new_status:
                raise ValueError(
                    f"Application is already in status '{new_status}'."
                )

            # Validate transition
            allowed_statuses = ALLOWED_TRANSITIONS.get(
                current_status,
                set(),
            )

            if new_status not in allowed_statuses:
                raise ValueError(
                    f"Invalid status transition: "
                    f"{current_status} -> {new_status}"
                )

            # Update application status
            if new_status == "SUBMITTED":
                cursor.execute(
                    """
                    UPDATE applications
                    SET
                        status = %s,
                        submitted_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s;
                    """,
                    (
                        new_status,
                        application_id,
                    ),
                )
            else:
                cursor.execute(
                    """
                    UPDATE applications
                    SET
                        status = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s;
                    """,
                    (
                        new_status,
                        application_id,
                    ),
                )

            # Record status history
            cursor.execute(
                """
                INSERT INTO application_status_history (
                    application_id,
                    old_status,
                    new_status,
                    changed_by,
                    reason
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                RETURNING id;
                """,
                (
                    application_id,
                    current_status,
                    new_status,
                    changed_by,
                    reason,
                ),
            )

            history_id = cursor.fetchone()[0]

        conn.commit()
        log_action(
            application_id=application_id,
            actor_type="SYSTEM",
            actor_id=changed_by,
            action="STATUS_CHANGED",
            details={
                "old_status": current_status,
                "new_status": new_status,
                "reason": reason,
                "history_id": history_id,
            },
        )

        return {
            "application_id": application_id,
            "old_status": current_status,
            "new_status": new_status,
            "changed_by": changed_by,
            "reason": reason,
            "history_id": history_id,
        }

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def get_application_status_history(application_id):
    """
    Retrieve the complete status history for an application.
    """

    conn = get_connection()

    try:
        with conn.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    id,
                    old_status,
                    new_status,
                    changed_by,
                    reason,
                    created_at
                FROM application_status_history
                WHERE application_id = %s
                ORDER BY id;
                """,
                (application_id,),
            )

            history = cursor.fetchall()

            return [
                {
                    "id": row[0],
                    "old_status": row[1],
                    "new_status": row[2],
                    "changed_by": row[3],
                    "reason": row[4],
                    "created_at": row[5],
                }
                for row in history
            ]

    finally:
        conn.close()
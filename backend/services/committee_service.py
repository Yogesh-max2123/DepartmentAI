from datetime import datetime

from backend.database.connection import get_connection
from backend.services.application_service import get_application
from backend.services.audit_service import log_action


VALID_COMMITTEES = {"DUGC", "DMPC", "DDPC"}
VALID_DECISIONS = {"APPROVED", "REJECTED"}


def assign_to_committee(application_id: int, committee_type: str):
    """
    Assign an application to an academic committee.

    Allowed committees:
    DUGC, DMPC, DDPC

    The application must be in COMMITTEE_REVIEW status.
    """

    committee_type = committee_type.upper().strip()

    if committee_type not in VALID_COMMITTEES:
        raise ValueError(
            f"Invalid committee type '{committee_type}'. "
            f"Allowed values: {', '.join(sorted(VALID_COMMITTEES))}."
        )

    application = get_application(application_id)

    if application is None:
        raise ValueError(
            f"Application with id {application_id} does not exist."
        )

    if application["status"] != "COMMITTEE_REVIEW":
        raise ValueError(
            f"Application must be in COMMITTEE_REVIEW status before "
            f"committee assignment. Current status: {application['status']}."
        )

    conn = get_connection()

    try:
        with conn.cursor() as cursor:

            # Prevent duplicate active committee assignments.
            cursor.execute(
                """
                SELECT id
                FROM committee_reviews
                WHERE application_id = %s
                  AND committee_type = %s
                  AND review_status IN ('PENDING', 'IN_REVIEW')
                LIMIT 1;
                """,
                (application_id, committee_type),
            )

            existing_review = cursor.fetchone()

            if existing_review is not None:
                raise ValueError(
                    f"Application {application_id} is already assigned "
                    f"to {committee_type}."
                )

            cursor.execute(
                """
                INSERT INTO committee_reviews (
                    application_id,
                    committee_type,
                    review_status
                )
                VALUES (%s, %s, 'PENDING')
                RETURNING id, application_id, committee_type,
                          assigned_at, review_status;
                """,
                (application_id, committee_type),
            )

            row = cursor.fetchone()

        conn.commit()

        # Record committee assignment in the audit trail.
        log_action(
            application_id=application_id,
            actor_type="SYSTEM",
            actor_id="SYSTEM",
            action="COMMITTEE_ASSIGNED",
            details={
                "committee_type": committee_type,
                "review_status": "PENDING",
            },
        )

        return {
            "id": row[0],
            "application_id": row[1],
            "committee_type": row[2],
            "assigned_at": row[3],
            "review_status": row[4],
        }

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def get_committee_reviews(application_id: int):
    """
    Get all committee reviews for an application.
    """

    application = get_application(application_id)

    if application is None:
        raise ValueError(
            f"Application with id {application_id} does not exist."
        )

    conn = get_connection()

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    application_id,
                    committee_type,
                    assigned_at,
                    review_status,
                    decision,
                    decision_reason,
                    decided_by,
                    decided_at
                FROM committee_reviews
                WHERE application_id = %s
                ORDER BY assigned_at ASC, id ASC;
                """,
                (application_id,),
            )

            rows = cursor.fetchall()

        return [
            {
                "id": row[0],
                "application_id": row[1],
                "committee_type": row[2],
                "assigned_at": row[3],
                "review_status": row[4],
                "decision": row[5],
                "decision_reason": row[6],
                "decided_by": row[7],
                "decided_at": row[8],
            }
            for row in rows
        ]

    finally:
        conn.close()


def record_committee_decision(
    review_id: int,
    decision: str,
    decision_reason: str,
    decided_by: str,
):
    """
    Record the final human committee decision.

    AI does not make this decision.
    An authorized committee member provides the decision.
    """

    decision = decision.upper().strip()

    if decision not in VALID_DECISIONS:
        raise ValueError(
            f"Invalid decision '{decision}'. "
            f"Allowed values: APPROVED, REJECTED."
        )

    if not decision_reason or not decision_reason.strip():
        raise ValueError("Decision reason is required.")

    if not decided_by or not decided_by.strip():
        raise ValueError("Decided_by is required.")

    conn = get_connection()

    try:
        with conn.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    id,
                    application_id,
                    committee_type,
                    review_status
                FROM committee_reviews
                WHERE id = %s;
                """,
                (review_id,),
            )

            review = cursor.fetchone()

            if review is None:
                raise ValueError(
                    f"Committee review with id {review_id} does not exist."
                )

            application_id = review[1]
            committee_type = review[2]
            review_status = review[3]

            if review_status == "COMPLETED":
                raise ValueError(
                    f"Committee review {review_id} has already been completed."
                )

            if review_status not in {"PENDING", "IN_REVIEW"}:
                raise ValueError(
                    f"Committee review {review_id} cannot be completed "
                    f"from status '{review_status}'."
                )

            now = datetime.now()

            # Complete the committee review.
            cursor.execute(
                """
                UPDATE committee_reviews
                SET
                    review_status = 'COMPLETED',
                    decision = %s,
                    decision_reason = %s,
                    decided_by = %s,
                    decided_at = %s
                WHERE id = %s;
                """,
                (
                    decision,
                    decision_reason.strip(),
                    decided_by.strip(),
                    now,
                    review_id,
                ),
            )

            # Update the application status to match the human decision.
            old_status = "COMMITTEE_REVIEW"
            new_status = decision

            cursor.execute(
                """
                UPDATE applications
                SET
                    status = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                  AND status = 'COMMITTEE_REVIEW';
                """,
                (new_status, application_id),
            )

            if cursor.rowcount != 1:
                raise ValueError(
                    f"Application {application_id} is not currently "
                    f"in COMMITTEE_REVIEW status."
                )

            # Record the status transition.
            cursor.execute(
                """
                INSERT INTO application_status_history (
                    application_id,
                    old_status,
                    new_status,
                    changed_by,
                    reason
                )
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id;
                """,
                (
                    application_id,
                    old_status,
                    new_status,
                    decided_by.strip(),
                    f"{committee_type} committee decision: "
                    f"{decision_reason.strip()}",
                ),
            )

            history_id = cursor.fetchone()[0]

            # Fetch the completed review.
            cursor.execute(
                """
                SELECT
                    id,
                    application_id,
                    committee_type,
                    assigned_at,
                    review_status,
                    decision,
                    decision_reason,
                    decided_by,
                    decided_at
                FROM committee_reviews
                WHERE id = %s;
                """,
                (review_id,),
            )

            completed_review = cursor.fetchone()

        conn.commit()

        # Record the human committee decision in the audit trail.
        log_action(
            application_id=application_id,
            actor_type="COMMITTEE",
            actor_id=decided_by.strip(),
            action="COMMITTEE_DECISION_RECORDED",
            details={
                "review_id": review_id,
                "committee_type": committee_type,
                "decision": decision,
                "decision_reason": decision_reason.strip(),
                "status_history_id": history_id,
            },
        )

        return {
            "review": {
                "id": completed_review[0],
                "application_id": completed_review[1],
                "committee_type": completed_review[2],
                "assigned_at": completed_review[3],
                "review_status": completed_review[4],
                "decision": completed_review[5],
                "decision_reason": completed_review[6],
                "decided_by": completed_review[7],
                "decided_at": completed_review[8],
            },
            "application_status": new_status,
            "status_history_id": history_id,
        }

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()
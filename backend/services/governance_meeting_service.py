from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import re

import psycopg

from backend.database.connection import get_connection
from backend.services.auth_service import AuthenticatedUser
from backend.services.governance_workflow_registry import (
    get_committee_workflow_policy,
    load_governance_workflow_registry,
)
from backend.services import yogesh_integration_service


COMMITTEE_PROGRAMMES = {"DUGC": "UG", "DMPC": "MTECH", "DDPC": "PHD"}


class GovernanceWorkflowError(ValueError):
    def __init__(self, code: str, message: str, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def _require_committee_membership(cursor, user: AuthenticatedUser, committee):
    if user.role != "DUGC":
        raise GovernanceWorkflowError(
            "COMMITTEE_ROLE_REQUIRED",
            "Only an authenticated committee account can access this workflow.",
            403,
        )
    cursor.execute(
        """
        SELECT 1
        FROM committee_memberships
        WHERE user_id = %s AND committee_type = %s;
        """,
        (user.id, committee),
    )
    if cursor.fetchone() is None:
        raise GovernanceWorkflowError(
            "COMMITTEE_MEMBERSHIP_REQUIRED",
            "You are not a member of this committee.",
            404,
        )


def _require_application_committee_access(cursor, user, application_id, committee):
    if user.role == "OFFICIAL":
        cursor.execute(
            """
            SELECT 1
            FROM official_application_assignments x
            JOIN committee_reviews r ON r.application_id = x.application_id
            JOIN committee_memberships m
              ON m.committee_type = r.committee_type
            WHERE x.application_id = %s
              AND x.user_id = %s
              AND r.committee_type = %s
            LIMIT 1;
            """,
            (application_id, user.id, committee),
        )
        if cursor.fetchone() is None:
            raise GovernanceWorkflowError(
                "APPLICATION_SCOPE_DENIED",
                "An agenda application is not assigned to you with an active committee assignment.",
                404,
            )
        return
    cursor.execute(
        """
        SELECT 1
        FROM applications a
        JOIN committee_reviews r ON r.application_id = a.id
        JOIN committee_memberships m
          ON m.committee_type = r.committee_type
        WHERE a.id = %s
          AND r.committee_type = %s
          AND m.user_id = %s
        LIMIT 1;
        """,
        (application_id, committee, user.id),
    )
    if cursor.fetchone() is None:
        raise GovernanceWorkflowError(
            "APPLICATION_SCOPE_DENIED",
            "An agenda application is not assigned to a committee you belong to.",
            404,
        )


def _audit(cursor, user, action, details):
    cursor.execute(
        """
        INSERT INTO audit_logs (
            application_id, actor_type, actor_id, action, details
        )
        VALUES (NULL, %s, %s, %s, %s::jsonb);
        """,
        (user.role, user.username, action, json.dumps(details)),
    )


def _meeting_dict(row):
    return {
        "id": row[0],
        "committee_type": row[1],
        "organizer_user_id": row[2],
        "title": row[3],
        "purpose": row[4],
        "proposed_start": row[5],
        "proposed_end": row[6],
        "duration_minutes": row[7],
        "proposed_slot_start": row[8],
        "status": row[9],
        "agenda": row[10],
        "created_at": row[11],
        "updated_at": row[12],
        "approved_by": row[13],
        "approved_at": row[14],
    }


MEETING_SELECT = """
    SELECT g.id, g.committee_type, g.organizer_user_id, g.title, g.purpose,
           g.proposed_start, g.proposed_end, g.duration_minutes,
           g.proposed_slot_start, g.status, g.agenda, g.created_at,
           g.updated_at,            g.approved_by, g.approved_at, g.request_fingerprint
    FROM governance_meetings g
"""


def list_committee_workspaces(user):
    if user.role != "OFFICIAL":
        raise GovernanceWorkflowError(
            "COMMITTEE_ROLE_REQUIRED",
            "Only Officials can open the meeting scheduling workspace.",
            403,
        )
    registry = load_governance_workflow_registry()
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT r.committee_type
                FROM official_application_assignments x
                JOIN committee_reviews r
                  ON r.application_id = x.application_id
                WHERE x.user_id = %s
                  AND EXISTS (
                      SELECT 1 FROM committee_memberships m
                      JOIN auth_users u ON u.id = m.user_id
                      WHERE m.committee_type = r.committee_type
                        AND u.is_active = TRUE
                  )
                ORDER BY r.committee_type;
                """,
                (user.id,),
            )
            committees = [row[0] for row in cursor.fetchall()]
        return {
            "workflow_registry_status": registry["status"],
            "committees": [
                {
                    "committee_type": committee,
                    "programme": COMMITTEE_PROGRAMMES[committee],
                    "approval_policy_configured": (
                        get_committee_workflow_policy(committee, registry)
                        is not None
                    ),
                    "availability_source": "EXPLICIT_MEMBER_SUBMISSIONS_ONLY",
                    "calendar_integration": "NOT_CONFIGURED",
                    "faculty_timetable": "NOT_CONFIGURED",
                    "notification_provider": "NOT_CONFIGURED",
                }
                for committee in committees
            ],
        }
    finally:
        connection.close()


def _normalize_agenda(agenda):
    normalized = []
    for index, item in enumerate(agenda):
        if not isinstance(item, dict):
            raise GovernanceWorkflowError(
                "AGENDA_INVALID", "Each agenda item must be an object."
            )
        title = item.get("title")
        description = item.get("description", "")
        application_ids = item.get("application_ids", [])
        if not isinstance(title, str) or not title.strip():
            raise GovernanceWorkflowError(
                "AGENDA_INVALID", "Each agenda item needs a title."
            )
        if not isinstance(description, str) or len(description) > 2000:
            raise GovernanceWorkflowError(
                "AGENDA_INVALID", "Agenda descriptions must be at most 2,000 characters."
            )
        if not isinstance(application_ids, list) or any(
            not isinstance(value, int) or value <= 0
            for value in application_ids
        ):
            raise GovernanceWorkflowError(
                "AGENDA_INVALID", "Agenda application IDs must be positive integers."
            )
        if len(set(application_ids)) != len(application_ids):
            raise GovernanceWorkflowError(
                "AGENDA_INVALID", "Duplicate application IDs are not allowed."
            )
        normalized.append(
            {
                "index": index,
                "title": title.strip(),
                "description": description.strip(),
                "application_ids": application_ids,
            }
        )
    return normalized


def create_meeting(user, payload, idempotency_key=None):
    if user.role != "OFFICIAL":
        raise GovernanceWorkflowError(
            "COMMITTEE_ROLE_REQUIRED",
            "Only an Official can create a meeting proposal.",
            403,
        )
    agenda = _normalize_agenda(payload["agenda"])
    if user.role == "OFFICIAL" and not any(
        item["application_ids"] for item in agenda
    ):
        raise GovernanceWorkflowError(
            "APPLICATION_LINK_REQUIRED",
            "An Official must link at least one application assigned to their account.",
            422,
        )
    fingerprint = hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    connection = get_connection()
    try:
        with connection:
            with connection.cursor() as cursor:
                for item in agenda:
                    for application_id in item["application_ids"]:
                        _require_application_committee_access(
                            cursor,
                            user,
                            application_id,
                            payload["committee_type"],
                        )
                if idempotency_key:
                    cursor.execute(
                        MEETING_SELECT
                        + """
                        WHERE g.organizer_user_id = %s
                          AND g.idempotency_key = %s;
                        """,
                        (user.id, idempotency_key),
                    )
                    existing = cursor.fetchone()
                    if existing:
                        if existing[15] != fingerprint:
                            raise GovernanceWorkflowError(
                                "IDEMPOTENCY_KEY_REUSED",
                                "This idempotency key was already used with different meeting data.",
                                409,
                            )
                        return _meeting_dict(existing)

                cursor.execute(
                    """
                    INSERT INTO governance_meetings (
                        committee_type, organizer_user_id, title, purpose,
                        proposed_start, proposed_end, duration_minutes,
                        agenda, idempotency_key, request_fingerprint
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
                    RETURNING id;
                    """,
                    (
                        payload["committee_type"],
                        user.id,
                        payload["title"].strip(),
                        payload["purpose"].strip(),
                        payload["proposed_start"],
                        payload["proposed_end"],
                        payload["duration_minutes"],
                        json.dumps(agenda),
                        idempotency_key,
                        fingerprint,
                    ),
                )
                meeting_id = cursor.fetchone()[0]
                for item in agenda:
                    for application_id in item["application_ids"]:
                        cursor.execute(
                            """
                            INSERT INTO meeting_application_links (
                                meeting_id, application_id, agenda_item_index
                            )
                            VALUES (%s, %s, %s);
                            """,
                            (meeting_id, application_id, item["index"]),
                        )
                _audit(
                    cursor,
                    user,
                    "GOVERNANCE_MEETING_CREATED",
                    {
                        "meeting_id": meeting_id,
                        "committee_type": payload["committee_type"],
                    },
                )
                cursor.execute(
                    MEETING_SELECT + "WHERE g.id = %s;",
                    (meeting_id,),
                )
                return _meeting_dict(cursor.fetchone())
    except psycopg.errors.UniqueViolation as error:
        raise GovernanceWorkflowError(
            "DUPLICATE_MEETING_REQUEST",
            "A meeting with this idempotency key already exists.",
            409,
        ) from error
    finally:
        connection.close()


def list_meetings(user, committee_type=None):
    if user.role != "OFFICIAL":
        raise GovernanceWorkflowError(
            "COMMITTEE_ROLE_REQUIRED",
            "Only Officials can list their meeting proposals.",
            403,
        )
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                MEETING_SELECT
                + """
                WHERE g.organizer_user_id = %s
                  AND (%s::text IS NULL OR g.committee_type = %s)
                  AND EXISTS (
                      SELECT 1
                      FROM meeting_application_links ml
                      JOIN official_application_assignments x
                        ON x.application_id = ml.application_id
                      WHERE ml.meeting_id = g.id AND x.user_id = %s
                  )
                  AND NOT EXISTS (
                      SELECT 1
                      FROM meeting_application_links ml
                      LEFT JOIN official_application_assignments x
                        ON x.application_id = ml.application_id
                       AND x.user_id = %s
                      WHERE ml.meeting_id = g.id
                        AND x.application_id IS NULL
                  )
                ORDER BY g.proposed_start DESC, g.id DESC;
                """,
                (
                    user.id,
                    committee_type,
                    committee_type,
                    user.id,
                    user.id,
                ),
            )
            return [_meeting_dict(row) for row in cursor.fetchall()]
    finally:
        connection.close()


def get_meeting(user, meeting_id, allow_official_organizer=False):
    if user.role == "OFFICIAL" and allow_official_organizer:
        access_clause = """
            WHERE g.id = %s
              AND g.organizer_user_id = %s
              AND EXISTS (
                  SELECT 1
                  FROM meeting_application_links ml
                  JOIN official_application_assignments x
                    ON x.application_id = ml.application_id
                  WHERE ml.meeting_id = g.id AND x.user_id = %s
              )
              AND NOT EXISTS (
                  SELECT 1
                  FROM meeting_application_links ml
                  LEFT JOIN official_application_assignments x
                    ON x.application_id = ml.application_id
                   AND x.user_id = %s
                  WHERE ml.meeting_id = g.id
                    AND x.application_id IS NULL
              )
        """
        parameters = (meeting_id, user.id, user.id, user.id)
    elif user.role == "DUGC":
        access_clause = """
            JOIN committee_memberships m
              ON m.committee_type = g.committee_type
            WHERE g.id = %s AND m.user_id = %s
        """
        parameters = (meeting_id, user.id)
    else:
        raise GovernanceWorkflowError(
            "COMMITTEE_ROLE_REQUIRED",
            "This account cannot access the meeting.",
            403,
        )
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                MEETING_SELECT + access_clause + ";",
                parameters,
            )
            row = cursor.fetchone()
            if row is None:
                raise GovernanceWorkflowError(
                    "MEETING_NOT_FOUND",
                    "Meeting not found.",
                    404,
                )
            meeting = _meeting_dict(row)
            if user.role == "DUGC":
                cursor.execute(
                    """
                SELECT ml.application_id, ml.agenda_item_index,
                       a.application_number, a.title, a.status
                FROM meeting_application_links ml
                JOIN applications a ON a.id = ml.application_id
                JOIN committee_reviews r
                  ON r.application_id = a.id
                 AND r.committee_type = %s
                JOIN committee_memberships am
                  ON am.committee_type = r.committee_type
                 AND am.user_id = %s
                WHERE ml.meeting_id = %s
                ORDER BY ml.agenda_item_index, ml.application_id;
                """,
                    (meeting["committee_type"], user.id, meeting_id),
                )
            else:
                cursor.execute(
                    """
                    SELECT ml.application_id, ml.agenda_item_index,
                           a.application_number, a.title, a.status
                    FROM meeting_application_links ml
                    JOIN applications a ON a.id = ml.application_id
                    JOIN official_application_assignments x
                      ON x.application_id = a.id AND x.user_id = %s
                    WHERE ml.meeting_id = %s
                    ORDER BY ml.agenda_item_index, ml.application_id;
                    """,
                    (user.id, meeting_id),
                )
            meeting["applications"] = [
                {
                    "application_id": item[0],
                    "agenda_item_index": item[1],
                    "application_number": item[2],
                    "title": item[3],
                    "status": item[4],
                }
                for item in cursor.fetchall()
            ]
            cursor.execute(
                """
                SELECT u.username, c.response, c.responded_at
                FROM meeting_confirmations c
                JOIN auth_users u ON u.id = c.user_id
                WHERE c.meeting_id = %s
                ORDER BY u.username;
                """,
                (meeting_id,),
            )
            meeting["confirmations"] = [
                {
                    "username": item[0],
                    "response": item[1],
                    "responded_at": item[2],
                }
                for item in cursor.fetchall()
            ]
            meeting["workflow_policy"] = get_committee_workflow_policy(
                meeting["committee_type"]
            )
            return meeting
    finally:
        connection.close()


def update_member_availability(
    user, committee_type, available_from, available_until, availability
):
    connection = get_connection()
    try:
        with connection:
            with connection.cursor() as cursor:
                _require_committee_membership(cursor, user, committee_type)
                cursor.execute(
                    """
                    SELECT availability
                    FROM meeting_member_availability
                    WHERE committee_type = %s AND user_id = %s
                      AND available_from < %s AND available_until > %s
                      AND NOT (
                          available_from = %s AND available_until = %s
                      )
                      AND availability <> %s;
                    """,
                    (
                        committee_type,
                        user.id,
                        available_until,
                        available_from,
                        available_from,
                        available_until,
                        availability,
                    ),
                )
                if cursor.fetchone():
                    raise GovernanceWorkflowError(
                        "AVAILABILITY_CONFLICT",
                        "The submitted interval overlaps a conflicting availability entry.",
                        409,
                    )
                cursor.execute(
                    """
                    INSERT INTO meeting_member_availability (
                        committee_type, user_id, available_from,
                        available_until, availability
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (
                        committee_type, user_id, available_from, available_until
                    )
                    DO UPDATE SET availability = EXCLUDED.availability,
                                  updated_at = CURRENT_TIMESTAMP;
                    """,
                    (
                        committee_type,
                        user.id,
                        available_from,
                        available_until,
                        availability,
                    ),
                )
                _audit(
                    cursor,
                    user,
                    "MEETING_AVAILABILITY_RECORDED",
                    {
                        "committee_type": committee_type,
                        "available_from": available_from.isoformat(),
                        "available_until": available_until.isoformat(),
                        "availability": availability,
                    },
                )
        return {"status": "RECORDED", "source": "MEMBER_SUBMITTED"}
    finally:
        connection.close()


def calculate_candidate_slots(
    user,
    committee_type,
    range_start,
    range_end,
    duration_minutes,
    exclude_meeting_id=None,
):
    if range_end <= range_start or (range_end - range_start) > timedelta(days=90):
        raise GovernanceWorkflowError(
            "DATE_RANGE_INVALID",
            "Availability search range must be positive and no longer than 90 days.",
        )
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            if user.role == "OFFICIAL":
                if exclude_meeting_id is None:
                    raise GovernanceWorkflowError(
                        "MEETING_NOT_FOUND",
                        "Officials can search slots only for their own persisted proposals.",
                        404,
                    )
                excluded_meeting = get_meeting(
                    user,
                    exclude_meeting_id,
                    allow_official_organizer=True,
                )
                if excluded_meeting["committee_type"] != committee_type:
                    raise GovernanceWorkflowError(
                        "MEETING_NOT_FOUND",
                        "Meeting not found.",
                        404,
                    )
            else:
                _require_committee_membership(cursor, user, committee_type)
            if exclude_meeting_id is not None:
                excluded_meeting = (
                    get_meeting(
                        user,
                        exclude_meeting_id,
                        allow_official_organizer=True,
                    )
                    if user.role == "OFFICIAL"
                    else get_meeting(user, exclude_meeting_id)
                )
                if excluded_meeting["committee_type"] != committee_type:
                    raise GovernanceWorkflowError(
                        "MEETING_NOT_FOUND",
                        "Meeting not found.",
                        404,
                    )
            cursor.execute(
                """
                SELECT m.user_id, u.username
                FROM committee_memberships m
                JOIN auth_users u ON u.id = m.user_id
                WHERE m.committee_type = %s AND u.is_active = TRUE
                ORDER BY m.user_id;
                """,
                (committee_type,),
            )
            members = cursor.fetchall()
            cursor.execute(
                """
                SELECT user_id, available_from, available_until, availability
                FROM meeting_member_availability
                WHERE committee_type = %s
                  AND available_from < %s AND available_until > %s;
                """,
                (committee_type, range_end, range_start),
            )
            availability = cursor.fetchall()
            cursor.execute(
                """
                SELECT proposed_slot_start,
                       proposed_slot_start + duration_minutes * INTERVAL '1 minute'
                FROM governance_meetings
                WHERE committee_type = %s
                  AND (%s::int IS NULL OR id <> %s)
                  AND status IN (
                      'PROPOSED', 'APPROVED_PENDING_CONFIRMATIONS', 'CONFIRMED'
                  )
                  AND proposed_slot_start IS NOT NULL
                  AND proposed_slot_start < %s
                  AND proposed_slot_start
                      + duration_minutes * INTERVAL '1 minute' > %s;
                """,
                (
                    committee_type,
                    exclude_meeting_id,
                    exclude_meeting_id,
                    range_end,
                    range_start,
                ),
            )
            booked = cursor.fetchall()

        per_member = {}
        for user_id, start, end, status in availability:
            per_member.setdefault(user_id, []).append((start, end, status))
        missing_members = [
            {"user_id": member_id, "username": username}
            for member_id, username in members
            if not per_member.get(member_id)
        ]
        if not members:
            return {
                "status": "NO_COMMITTEE_MEMBERS",
                "availability_source": "EXPLICIT_MEMBER_SUBMISSIONS_ONLY",
                "faculty_timetable": "NOT_CONFIGURED",
                "missing_members": [],
                "candidate_slots": [],
            }
        duration = timedelta(minutes=duration_minutes)
        slots = []
        cursor_time = range_start.replace(
            minute=(range_start.minute // 30) * 30,
            second=0,
            microsecond=0,
        )
        if cursor_time < range_start:
            cursor_time += timedelta(minutes=30)
        while cursor_time + duration <= range_end:
            slot_end = cursor_time + duration
            unavailable = []
            incomplete = []
            for member_id, username in members:
                if not any(
                    status == "AVAILABLE"
                    and start <= cursor_time
                    and end >= slot_end
                    for start, end, status in per_member.get(member_id, [])
                ):
                    unavailable.append(username)
                    if not per_member.get(member_id):
                        incomplete.append(username)
            booked_conflicts = [
                {"start": start, "end": end}
                for start, end in booked
                if start < slot_end and end > cursor_time
            ]
            is_available = not unavailable and not booked_conflicts
            slots.append(
                    {
                        "start": cursor_time,
                        "end": slot_end,
                        "availability_status": (
                            "ALL_MEMBERS_AVAILABLE"
                            if not unavailable
                            else "CONFLICT"
                        ),
                        "unavailable_members": unavailable,
                        "members_without_data": incomplete,
                        "conflict_status": (
                            "BOOKED_MEETING_OVERLAP"
                            if booked_conflicts
                            else "NO_BOOKED_MEETING_OVERLAP"
                        ),
                        "conflicting_meetings": booked_conflicts,
                        "candidate": is_available,
                    }
            )
            cursor_time += timedelta(minutes=30)
        candidate_slots = [slot for slot in slots if slot["candidate"]]
        result = {
            "status": (
                "COMPLETED"
                if candidate_slots
                else (
                    "INCOMPLETE_AVAILABILITY"
                    if missing_members
                    else "NO_CANDIDATE_SLOTS"
                )
            ),
            "availability_source": "EXPLICIT_MEMBER_SUBMISSIONS_ONLY",
            "faculty_timetable": "NOT_CONFIGURED",
            "missing_members": missing_members,
            "candidate_slots": slots,
        }
        programme = COMMITTEE_PROGRAMMES.get(committee_type)
        if (
            yogesh_integration_service.is_integration_enabled()
            and programme in {"MTECH", "PHD"}
        ):
            try:
                options = yogesh_integration_service.get_meeting_options(
                    programme,
                    range_start,
                    range_end,
                    duration_minutes,
                    [
                        {"start": start, "end": end}
                        for start, end in booked
                    ],
                )
            except yogesh_integration_service.YogeshIntegrationError as error:
                raise GovernanceWorkflowError(
                    "YOGESH_SCHEDULER_UNAVAILABLE",
                    str(error),
                    error.status_code,
                ) from error

            reference_candidates = {}
            for slot in options["candidate_slots"]:
                reference_start = datetime.fromisoformat(slot["start"])
                reference_candidates[
                    reference_start.astimezone(timezone.utc)
                ] = slot["candidate"]
            for slot in slots:
                reference_available = reference_candidates.get(
                    slot["start"].astimezone(timezone.utc),
                    False,
                )
                slot["yogesh_candidate"] = reference_available
                slot["candidate"] = (
                    slot["candidate"] and reference_available
                )
                slot["yogesh_conflict_status"] = (
                    "AVAILABLE" if reference_available else "CONFLICT"
                )
            result["status"] = (
                "COMPLETED"
                if any(slot["candidate"] for slot in slots)
                else (
                    "INCOMPLETE_AVAILABILITY"
                    if missing_members
                    else "NO_CANDIDATE_SLOTS"
                )
            )
            result["scheduler_integration"] = {
                "status": options.get("status", "COMPLETED"),
                "programme": programme,
                "source": "YOGESH_REFERENCE_AND_SOSTUDY_PERSISTED_AVAILABILITY",
            }
            result["availability_source"] = (
                "SOSTUDY_EXPLICIT_MEMBER_SUBMISSIONS_AND_YOGESH_REFERENCE"
            )
        return result
    finally:
        connection.close()


def select_meeting_slot(user, meeting_id, proposed_slot_start):
    if user.role != "OFFICIAL":
        raise GovernanceWorkflowError(
            "COMMITTEE_ROLE_REQUIRED",
            "Only the assigned Official can select a meeting slot.",
            403,
        )
    meeting = (
        get_meeting(user, meeting_id, allow_official_organizer=True)
        if user.role == "OFFICIAL"
        else get_meeting(user, meeting_id)
    )
    if meeting["status"] != "PROPOSED":
        raise GovernanceWorkflowError(
            "MEETING_NOT_EDITABLE", "The meeting slot can no longer be changed.", 409
        )
    range_result = calculate_candidate_slots(
        user,
        meeting["committee_type"],
        meeting["proposed_start"],
        meeting["proposed_end"],
        meeting["duration_minutes"],
        exclude_meeting_id=meeting_id,
    )
    if not any(
        slot["start"] == proposed_slot_start and slot["candidate"]
        for slot in range_result["candidate_slots"]
    ):
        raise GovernanceWorkflowError(
            "SLOT_NOT_AVAILABLE",
            "The selected slot is not supported by complete member availability.",
            409,
        )
    connection = get_connection()
    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE governance_meetings
                    SET proposed_slot_start = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s AND status = 'PROPOSED'
                    RETURNING id;
                    """,
                    (proposed_slot_start, meeting_id),
                )
                if cursor.fetchone() is None:
                    raise GovernanceWorkflowError(
                        "MEETING_NOT_EDITABLE",
                        "The meeting slot can no longer be changed.",
                        409,
                    )
                _audit(
                    cursor,
                    user,
                    "MEETING_SLOT_PROPOSED",
                    {
                        "meeting_id": meeting_id,
                        "proposed_slot_start": proposed_slot_start.isoformat(),
                    },
                )
    finally:
        connection.close()
    return (
        get_meeting(user, meeting_id, allow_official_organizer=True)
        if user.role == "OFFICIAL"
        else get_meeting(user, meeting_id)
    )


def approve_meeting(user, meeting_id, application_id=None):
    if user.role != "DUGC":
        raise GovernanceWorkflowError(
            "COMMITTEE_ROLE_REQUIRED",
            "Only an assigned DUGC approver can approve a meeting.",
            403,
        )
    if application_id is None:
        raise GovernanceWorkflowError(
            "APPLICATION_SCOPE_REQUIRED",
            "Approve a meeting from its linked application.",
            403,
        )
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            _require_application_meeting_access(
                cursor, user, application_id, meeting_id
            )
    finally:
        connection.close()
    meeting = get_meeting(user, meeting_id)
    policy = get_committee_workflow_policy(meeting["committee_type"])
    if policy is None:
        raise GovernanceWorkflowError(
            "MEETING_APPROVAL_POLICY_UNCONFIGURED",
            "Meeting approval is blocked until an institutionally approved committee workflow policy and approver are configured.",
            409,
        )
    if user.username.lower() not in policy["meeting_approver_usernames"]:
        raise GovernanceWorkflowError(
            "MEETING_APPROVER_REQUIRED",
            "This account is not a configured meeting approver.",
            403,
        )
    if meeting["status"] == "CONFIRMED":
        return meeting
    if meeting["status"] == "APPROVED_PENDING_CONFIRMATIONS":
        return meeting
    if meeting["status"] != "PROPOSED" or meeting["proposed_slot_start"] is None:
        raise GovernanceWorkflowError(
            "MEETING_SLOT_REQUIRED",
            "Choose a supported candidate slot before approval.",
            409,
        )
    current_slots = calculate_candidate_slots(
        user,
        meeting["committee_type"],
        meeting["proposed_start"],
        meeting["proposed_end"],
        meeting["duration_minutes"],
        exclude_meeting_id=meeting_id,
    )
    if not any(
        slot["start"] == meeting["proposed_slot_start"] and slot["candidate"]
        for slot in current_slots["candidate_slots"]
    ):
        raise GovernanceWorkflowError(
            "SLOT_NOT_AVAILABLE",
            "The proposed slot is no longer a conflict-free candidate; rerun availability before approval.",
            409,
        )
    connection = get_connection()
    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE governance_meetings
                    SET status = 'APPROVED_PENDING_CONFIRMATIONS',
                        approved_by = %s, approved_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s AND status = 'PROPOSED'
                    RETURNING committee_type;
                    """,
                    (user.id, meeting_id),
                )
                if cursor.fetchone() is None:
                    raise GovernanceWorkflowError(
                        "MEETING_STATE_CONFLICT",
                        "The meeting state changed; reload before approving.",
                        409,
                    )
                _audit(
                    cursor,
                    user,
                    "GOVERNANCE_MEETING_APPROVED",
                    {"meeting_id": meeting_id},
                )
    finally:
        connection.close()
    return get_meeting(user, meeting_id)


def respond_to_meeting(user, meeting_id, response, application_id=None):
    if user.role != "DUGC":
        raise GovernanceWorkflowError(
            "COMMITTEE_ROLE_REQUIRED",
            "Only assigned DUGC members can respond to a meeting.",
            403,
        )
    if application_id is None:
        raise GovernanceWorkflowError(
            "APPLICATION_SCOPE_REQUIRED",
            "Confirm or decline a meeting from its linked application.",
            403,
        )
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            _require_application_meeting_access(
                cursor, user, application_id, meeting_id
            )
    finally:
        connection.close()
    meeting = get_meeting(user, meeting_id)
    if meeting["status"] != "APPROVED_PENDING_CONFIRMATIONS":
        raise GovernanceWorkflowError(
            "MEETING_NOT_AWAITING_CONFIRMATION",
            "The meeting is not awaiting participant confirmation.",
            409,
        )
    connection = get_connection()
    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT response
                    FROM meeting_confirmations
                    WHERE meeting_id = %s AND user_id = %s
                    FOR UPDATE;
                    """,
                    (meeting_id, user.id),
                )
                existing = cursor.fetchone()
                if existing and existing[0] != response:
                    raise GovernanceWorkflowError(
                        "CONFIRMATION_CONFLICT",
                        "A response was already recorded. Contact the meeting organizer to resolve a changed response.",
                        409,
                    )
                if not existing:
                    cursor.execute(
                        """
                        INSERT INTO meeting_confirmations (
                            meeting_id, user_id, response
                        )
                        VALUES (%s, %s, %s)
                        ON CONFLICT (meeting_id, user_id) DO NOTHING;
                        """,
                        (meeting_id, user.id, response),
                    )
                    _audit(
                        cursor,
                        user,
                        "MEETING_PARTICIPANT_" + response,
                        {"meeting_id": meeting_id},
                    )
                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM meeting_confirmations
                    WHERE meeting_id = %s AND response = 'CONFIRMED';
                    """,
                    (meeting_id,),
                )
                confirmed_count = cursor.fetchone()[0]
                policy = get_committee_workflow_policy(
                    meeting["committee_type"]
                )
                if (
                    meeting["status"] == "APPROVED_PENDING_CONFIRMATIONS"
                    and policy is not None
                    and confirmed_count >= policy["minimum_confirmations"]
                ):
                    cursor.execute(
                        """
                        UPDATE governance_meetings
                        SET status = 'CONFIRMED',
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                          AND status = 'APPROVED_PENDING_CONFIRMATIONS';
                        """,
                        (meeting_id,),
                    )
                    _audit(
                        cursor,
                        user,
                        "GOVERNANCE_MEETING_CONFIRMED",
                        {"meeting_id": meeting_id},
                    )
    finally:
        connection.close()
    return get_meeting(user, meeting_id)


def _require_application_meeting_access(cursor, user, application_id, meeting_id):
    if user.role != "DUGC":
        raise GovernanceWorkflowError(
            "COMMITTEE_ROLE_REQUIRED",
            "Only assigned DUGC members can manage application meeting responses.",
            403,
        )
    cursor.execute(
        """
        SELECT 1
        FROM meeting_application_links ml
        JOIN governance_meetings g ON g.id = ml.meeting_id
        JOIN committee_reviews r
          ON r.application_id = ml.application_id
         AND r.committee_type = g.committee_type
        JOIN committee_memberships m
          ON m.committee_type = r.committee_type
        WHERE ml.application_id = %s
          AND ml.meeting_id = %s
          AND m.user_id = %s
        LIMIT 1;
        """,
        (application_id, meeting_id, user.id),
    )
    if cursor.fetchone() is None:
        raise GovernanceWorkflowError(
            "APPLICATION_SCOPE_DENIED",
            "This meeting is not linked to an application assigned to your committee.",
            404,
        )


def get_application_meetings(user, application_id):
    if user.role != "DUGC":
        raise GovernanceWorkflowError(
            "COMMITTEE_ROLE_REQUIRED",
            "Only assigned DUGC members can view application meeting actions.",
            403,
        )
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT g.id, g.committee_type, g.title, g.status,
                       g.proposed_start, g.proposed_end,
                       g.proposed_slot_start, g.duration_minutes,
                       c.response
                FROM meeting_application_links ml
                JOIN governance_meetings g ON g.id = ml.meeting_id
                JOIN committee_reviews r
                  ON r.application_id = ml.application_id
                 AND r.committee_type = g.committee_type
                JOIN committee_memberships m
                  ON m.committee_type = r.committee_type
                LEFT JOIN meeting_confirmations c
                  ON c.meeting_id = g.id AND c.user_id = m.user_id
                WHERE ml.application_id = %s AND m.user_id = %s
                ORDER BY g.proposed_slot_start NULLS LAST, g.id;
                """,
                (application_id, user.id),
            )
            meetings = cursor.fetchall()
        results = []
        for row in meetings:
            policy = get_committee_workflow_policy(row[1])
            approvers = (
                policy.get("meeting_approver_usernames", [])
                if policy
                else []
            )
            results.append(
                {
                    "id": row[0],
                    "committee_type": row[1],
                    "title": row[2],
                    "status": row[3],
                    "proposed_start": row[4],
                    "proposed_end": row[5],
                    "proposed_slot_start": row[6],
                    "duration_minutes": row[7],
                    "response": row[8],
                    "can_approve": (
                        row[3] == "PROPOSED"
                        and row[6] is not None
                        and user.username.lower()
                        in {name.lower() for name in approvers}
                    ),
                    "can_confirm": (
                        row[3] == "APPROVED_PENDING_CONFIRMATIONS"
                        and row[8] is None
                    ),
                }
            )
        return {"meetings": results}
    finally:
        connection.close()


def approve_application_meeting(user, application_id, meeting_id):
    return approve_meeting(user, meeting_id, application_id)


def respond_to_application_meeting(
    user, application_id, meeting_id, response
):
    return respond_to_meeting(user, meeting_id, response, application_id)


def get_agenda(user, meeting_id):
    meeting = get_meeting(user, meeting_id)
    return {
        "meeting_id": meeting_id,
        "status": meeting["status"],
        "agenda": meeting["agenda"],
        "applications": meeting["applications"],
        "generated_from": "PERSISTED_MEETING_RECORDS",
        "distribution_status": "NOT_SENT",
        "notification_provider": "NOT_CONFIGURED",
    }


def update_meeting_agenda(user, meeting_id, agenda):
    if user.role != "OFFICIAL":
        raise GovernanceWorkflowError(
            "COMMITTEE_ROLE_REQUIRED",
            "Only the assigned Official can revise a meeting proposal.",
            403,
        )
    meeting = (
        get_meeting(user, meeting_id, allow_official_organizer=True)
        if user.role == "OFFICIAL"
        else get_meeting(user, meeting_id)
    )
    if meeting["status"] != "PROPOSED":
        raise GovernanceWorkflowError(
            "MEETING_NOT_EDITABLE",
            "The agenda can only be revised before the meeting is approved.",
            409,
        )
    normalized_agenda = _normalize_agenda(agenda)
    if not normalized_agenda or any(not item["title"] for item in normalized_agenda):
        raise GovernanceWorkflowError(
            "AGENDA_INVALID", "Agenda items require a non-empty title.", 422
        )
    connection = get_connection()
    try:
        with connection:
            with connection.cursor() as cursor:
                for item in normalized_agenda:
                    for application_id in item["application_ids"]:
                        _require_application_committee_access(
                            cursor,
                            user,
                            application_id,
                            meeting["committee_type"],
                        )
                cursor.execute(
                    """
                    UPDATE governance_meetings
                    SET agenda = %s::jsonb, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s AND status = 'PROPOSED'
                    RETURNING id;
                    """,
                    (json.dumps(normalized_agenda), meeting_id),
                )
                if cursor.fetchone() is None:
                    raise GovernanceWorkflowError(
                        "MEETING_NOT_EDITABLE",
                        "The meeting state changed; reload before revising the agenda.",
                        409,
                    )
                cursor.execute(
                    "DELETE FROM meeting_application_links WHERE meeting_id = %s;",
                    (meeting_id,),
                )
                for item in normalized_agenda:
                    for application_id in item["application_ids"]:
                        cursor.execute(
                            """
                            INSERT INTO meeting_application_links (
                                meeting_id, application_id, agenda_item_index
                            )
                            VALUES (%s, %s, %s);
                            """,
                            (meeting_id, application_id, item["index"]),
                        )
                _audit(
                    cursor,
                    user,
                    "GOVERNANCE_MEETING_AGENDA_REVISED",
                    {"meeting_id": meeting_id},
                )
    finally:
        connection.close()
    return (
        get_meeting(user, meeting_id, allow_official_organizer=True)
        if user.role == "OFFICIAL"
        else get_meeting(user, meeting_id)
    )


def get_meeting_notice(user, meeting_id):
    meeting = get_meeting(user, meeting_id)
    return {
        "meeting_id": meeting_id,
        "title": meeting["title"],
        "purpose": meeting["purpose"],
        "committee_type": meeting["committee_type"],
        "proposed_slot_start": meeting["proposed_slot_start"],
        "duration_minutes": meeting["duration_minutes"],
        "agenda": meeting["agenda"],
        "applications": meeting["applications"],
        "status": "DRAFT",
        "distribution_status": "NOT_SENT",
        "notification_provider": "NOT_CONFIGURED",
    }


def add_meeting_record(user, meeting_id, agenda_item_index, record_type, content):
    meeting = get_meeting(user, meeting_id)
    if meeting["status"] == "CANCELLED":
        raise GovernanceWorkflowError(
            "MEETING_CLOSED",
            "Records cannot be added to a cancelled meeting.",
            409,
        )
    if meeting["status"] != "CONFIRMED":
        raise GovernanceWorkflowError(
            "MEETING_NOT_CONFIRMED",
            "Meeting records can only be added after the meeting is confirmed.",
            409,
        )
    if agenda_item_index is not None and not (
        0 <= agenda_item_index < len(meeting["agenda"])
    ):
        raise GovernanceWorkflowError(
            "AGENDA_ITEM_NOT_FOUND",
            "The agenda item index does not exist for this meeting.",
        )
    connection = get_connection()
    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id FROM governance_meetings WHERE id = %s FOR UPDATE;",
                    (meeting_id,),
                )
                cursor.execute(
                    """
                    SELECT 1
                    FROM meeting_minutes_versions
                    WHERE meeting_id = %s AND status = 'FINALIZED'
                    LIMIT 1;
                    """,
                    (meeting_id,),
                )
                if cursor.fetchone():
                    raise GovernanceWorkflowError(
                        "MEETING_MINUTES_FINALIZED",
                        "Meeting records cannot change after minutes are finalized.",
                        409,
                    )
                cursor.execute(
                    """
                    INSERT INTO meeting_records (
                        meeting_id, agenda_item_index, record_type, content,
                        created_by
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id, created_at;
                    """,
                    (
                        meeting_id,
                        agenda_item_index,
                        record_type,
                        content.strip(),
                        user.id,
                    ),
                )
                row = cursor.fetchone()
                _audit(
                    cursor,
                    user,
                    "MEETING_RECORD_ADDED",
                    {
                        "meeting_id": meeting_id,
                        "record_id": row[0],
                        "record_type": record_type,
                    },
                )
        return {
            "id": row[0],
            "meeting_id": meeting_id,
            "agenda_item_index": agenda_item_index,
            "record_type": record_type,
            "content": content.strip(),
            "created_by": user.username,
            "created_at": row[1],
        }
    finally:
        connection.close()


def _minutes_context(user, meeting_id):
    meeting = get_meeting(user, meeting_id)
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT r.id, r.agenda_item_index, r.record_type, r.content,
                       u.username, r.created_at
                FROM meeting_records r
                JOIN auth_users u ON u.id = r.created_by
                WHERE r.meeting_id = %s
                ORDER BY r.created_at, r.id;
                """,
                (meeting_id,),
            )
            records = [
                {
                    "id": row[0],
                    "agenda_item_index": row[1],
                    "record_type": row[2],
                    "content": row[3],
                    "recorded_by": row[4],
                    "created_at": row[5],
                }
                for row in cursor.fetchall()
            ]
            cursor.execute(
                """
                SELECT id, version_number, status, generation_method, content,
                       source_references, created_by, created_at,
                       finalized_by, finalized_at
                FROM meeting_minutes_versions
                WHERE meeting_id = %s
                ORDER BY version_number DESC;
                """,
                (meeting_id,),
            )
            versions = [
                {
                    "id": row[0],
                    "version_number": row[1],
                    "status": row[2],
                    "generation_method": row[3],
                    "content": row[4],
                    "source_references": row[5],
                    "created_by": row[6],
                    "created_at": row[7],
                    "finalized_by": row[8],
                    "finalized_at": row[9],
                }
                for row in cursor.fetchall()
            ]
            return meeting, records, versions
    finally:
        connection.close()


def get_minutes_workspace(user, meeting_id):
    meeting, records, versions = _minutes_context(user, meeting_id)
    latest = versions[0] if versions else None
    comments = []
    if latest:
        connection = get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT c.id, u.username, c.comment, c.created_at
                    FROM meeting_minutes_comments c
                    JOIN auth_users u ON u.id = c.user_id
                    WHERE c.minutes_version_id = %s
                    ORDER BY c.created_at, c.id;
                    """,
                    (latest["id"],),
                )
                comments = [
                    {
                        "id": row[0],
                        "username": row[1],
                        "comment": row[2],
                        "created_at": row[3],
                    }
                    for row in cursor.fetchall()
                ]
        finally:
            connection.close()
    return {
        "meeting": meeting,
        "records": records,
        "versions": versions,
        "latest_version": latest,
        "comments": comments,
        "review_issues": _minutes_review_issues(meeting, records),
        "ai_generation": "CHECK_INTEGRATIONS_BEFORE_REQUEST",
        "finalization_configured": bool(
            get_committee_workflow_policy(meeting["committee_type"])
            and get_committee_workflow_policy(
                meeting["committee_type"]
            )["minutes_approver_usernames"]
        ),
    }


def _minutes_review_issues(meeting, records):
    decisions_by_agenda = {}
    for record in records:
        if record["record_type"] == "DECISION":
            decisions_by_agenda.setdefault(
                record["agenda_item_index"], []
            ).append(record)

    positive = {"approve", "approved", "accept", "accepted", "proceed"}
    negative = {"reject", "rejected", "deny", "denied", "defer", "deferred"}
    issues = []
    for agenda_item in meeting["agenda"]:
        index = agenda_item["index"]
        decisions = decisions_by_agenda.get(index, [])
        if not decisions:
            issues.append(
                {
                    "kind": "UNRESOLVED_AGENDA_ITEM",
                    "agenda_item_index": index,
                    "message": "No human decision or explicit deferral is recorded.",
                    "requires_human_review": True,
                }
            )
            continue
        tagged = []
        for decision in decisions:
            words = set(re.findall(r"[a-z]+", decision["content"].lower()))
            has_positive = bool(words & positive)
            has_negative = bool(words & negative)
            if has_positive and has_negative:
                issues.append(
                    {
                        "kind": "POSSIBLE_CONFLICT",
                        "agenda_item_index": index,
                        "record_ids": [decision["id"]],
                        "message": "One decision record contains opposing outcome terms.",
                        "requires_human_review": True,
                    }
                )
            elif has_positive or has_negative:
                tagged.append((decision, has_positive))
        for position, (first, first_positive) in enumerate(tagged):
            for second, second_positive in tagged[position + 1 :]:
                if first_positive != second_positive:
                    issues.append(
                        {
                            "kind": "POSSIBLE_CONFLICT",
                            "agenda_item_index": index,
                            "record_ids": [first["id"], second["id"]],
                            "message": "Decision records contain opposing outcome terms.",
                            "requires_human_review": True,
                        }
                    )
    return issues


def _validate_minutes_context(meeting, records):
    if meeting["status"] != "CONFIRMED":
        raise GovernanceWorkflowError(
            "MEETING_NOT_CONFIRMED",
            "Minutes can only be generated for a confirmed meeting.",
            409,
        )
    missing = []
    for record_type in ("ATTENDANCE", "NOTE", "OBSERVATION"):
        if not any(item["record_type"] == record_type for item in records):
            missing.append(record_type.lower())
    decisions = [
        item for item in records if item["record_type"] == "DECISION"
    ]
    unresolved = [
        item["index"]
        for item in meeting["agenda"]
        if not any(
            decision["agenda_item_index"] == item["index"]
            for decision in decisions
        )
    ]
    if unresolved:
        missing.append(
            "human decision or explicit deferral for agenda items "
            + ", ".join(str(item + 1) for item in unresolved)
        )
    possible_conflicts = [
        issue
        for issue in _minutes_review_issues(meeting, records)
        if issue["kind"] == "POSSIBLE_CONFLICT"
    ]
    if possible_conflicts:
        raise GovernanceWorkflowError(
            "MINUTES_DECISION_CONFLICT",
            "Conflicting human decision records require committee resolution before drafting or finalization.",
            409,
        )
    if missing:
        raise GovernanceWorkflowError(
            "MINUTES_INPUTS_MISSING",
            "Minutes draft generation requires recorded " + "; ".join(missing) + ".",
            409,
        )


def _generate_minutes_content(meeting, records, source_references):
    from backend.llm.minutes_generator import (
        MinutesGenerationUnavailable,
        generate_minutes_draft,
    )

    try:
        return generate_minutes_draft(meeting, records, source_references)
    except MinutesGenerationUnavailable as error:
        raise GovernanceWorkflowError(
            "MINUTES_GENERATION_UNAVAILABLE",
            str(error),
            503,
        ) from error


def create_minutes_draft(user, meeting_id):
    meeting, records, _ = _minutes_context(user, meeting_id)
    _validate_minutes_context(meeting, records)
    content = {
        "draft_notice": "Human-authored draft; committee review and approval required.",
        "meeting": {
            "committee_type": meeting["committee_type"],
            "title": meeting["title"],
            "purpose": meeting["purpose"],
            "scheduled_start": (
                meeting["proposed_slot_start"].isoformat()
                if meeting["proposed_slot_start"] is not None
                else None
            ),
        },
        "attendance_as_recorded": [
            record["content"]
            for record in records
            if record["record_type"] == "ATTENDANCE"
        ],
        "sections": [
            {
                "agenda_item_index": agenda_item["index"],
                "title": agenda_item["title"],
                "human_records_as_recorded": [
                    {
                        "record_type": record["record_type"],
                        "content": record["content"],
                        "recorded_by": record["recorded_by"],
                    }
                    for record in records
                    if record["agenda_item_index"] == agenda_item["index"]
                ],
            }
            for agenda_item in meeting["agenda"]
        ],
        "source_references": [],
    }
    return _insert_minutes_version(
        user,
        meeting_id,
        content,
        [],
        "HUMAN",
    )


def _insert_minutes_version(user, meeting_id, content, source_references, method):
    connection = get_connection()
    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id FROM governance_meetings WHERE id = %s FOR UPDATE;",
                    (meeting_id,),
                )
                cursor.execute(
                    """
                    SELECT COALESCE(MAX(version_number), 0) + 1
                    FROM meeting_minutes_versions
                    WHERE meeting_id = %s;
                    """,
                    (meeting_id,),
                )
                version = cursor.fetchone()[0]
                cursor.execute(
                    """
                    INSERT INTO meeting_minutes_versions (
                        meeting_id, version_number, status, generation_method,
                        content, source_references, created_by
                    )
                    VALUES (%s, %s, 'DRAFT', %s, %s::jsonb, %s::jsonb, %s)
                    RETURNING id, created_at;
                    """,
                    (
                        meeting_id,
                        version,
                        method,
                        json.dumps(content),
                        json.dumps(source_references),
                        user.id,
                    ),
                )
                row = cursor.fetchone()
                _audit(
                    cursor,
                    user,
                    "MEETING_MINUTES_DRAFT_CREATED",
                    {
                        "meeting_id": meeting_id,
                        "version_id": row[0],
                        "version_number": version,
                        "generation_method": method,
                    },
                )
        return {
            "id": row[0],
            "meeting_id": meeting_id,
            "version_number": version,
            "status": "DRAFT",
            "generation_method": method,
            "content": content,
            "source_references": source_references,
            "created_at": row[1],
        }
    finally:
        connection.close()


def generate_minutes(user, meeting_id):
    meeting, records, versions = _minutes_context(user, meeting_id)
    _validate_minutes_context(meeting, records)

    references = []
    from backend.services.knowledge_retrieval_service import (
        KnowledgeRetrievalUnavailable,
        retrieve_knowledge,
    )

    queries = [
        " ".join([item["title"], item["description"]]).strip()
        for item in meeting["agenda"]
    ]
    try:
        for query in queries:
            if query:
                result = retrieve_knowledge(
                    query,
                    COMMITTEE_PROGRAMMES[meeting["committee_type"]],
                    limit=3,
                )
                references.extend(
                    {
                        "source_id": item.get("source_id"),
                        "source_version": item.get("source_version"),
                        "source_sha256": item.get("source_sha256"),
                        "chunk_id": item.get("chunk_id"),
                        "section_number": item.get("section_number"),
                        "page_start": item.get("page_start"),
                        "applicability": "CANDIDATE",
                        "source_metadata_status": item.get(
                            "source_metadata_status"
                        ),
                    }
                    for item in result["results"]
                )
    except KnowledgeRetrievalUnavailable as error:
        raise GovernanceWorkflowError(
            "MINUTES_SOURCE_RETRIEVAL_UNAVAILABLE",
            "Approved ordinance retrieval is unavailable; a grounded minutes draft was not generated.",
            503,
        ) from error

    content = _generate_minutes_content(meeting, records, references)
    if not isinstance(content, dict) or not isinstance(
        content.get("sections"), list
    ):
        raise GovernanceWorkflowError(
            "MINUTES_GENERATION_INVALID_OUTPUT",
            "The configured minutes generator did not return a valid structured draft.",
            503,
        )
    return _insert_minutes_version(user, meeting_id, content, references, "AI")


def _get_minutes_version(cursor, version_id):
    cursor.execute(
        """
        SELECT v.id, v.meeting_id, v.version_number, v.status,
               v.generation_method, v.content, v.source_references,
               v.created_by, g.committee_type, v.finalized_by
        FROM meeting_minutes_versions v
        JOIN governance_meetings g ON g.id = v.meeting_id
        WHERE v.id = %s;
        """,
        (version_id,),
    )
    return cursor.fetchone()


def save_minutes_draft(user, meeting_id, version_id, content):
    meeting = get_meeting(user, meeting_id)
    connection = get_connection()
    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id FROM governance_meetings WHERE id = %s FOR UPDATE;",
                    (meeting_id,),
                )
                version = _get_minutes_version(cursor, version_id)
                if version is None or version[1] != meeting_id:
                    raise GovernanceWorkflowError(
                        "MINUTES_VERSION_NOT_FOUND", "Minutes version not found.", 404
                    )
                if version[3] not in {"DRAFT", "SUBMITTED"}:
                    raise GovernanceWorkflowError(
                        "MINUTES_VERSION_LOCKED",
                        "Finalized minutes cannot be revised.",
                        409,
                    )
                if not isinstance(content, dict) or not isinstance(
                    content.get("sections"), list
                ):
                    raise GovernanceWorkflowError(
                        "MINUTES_CONTENT_INVALID",
                        "Minutes content must contain a sections array.",
                        422,
                    )
                if len(json.dumps(content, ensure_ascii=False)) > 100_000:
                    raise GovernanceWorkflowError(
                        "MINUTES_CONTENT_TOO_LARGE",
                        "Minutes content cannot exceed 100,000 characters.",
                        413,
                    )
                cursor.execute(
                    """
                    SELECT COALESCE(MAX(version_number), 0) + 1
                    FROM meeting_minutes_versions
                    WHERE meeting_id = %s;
                    """,
                    (meeting_id,),
                )
                new_version_number = cursor.fetchone()[0]
                cursor.execute(
                    """
                    INSERT INTO meeting_minutes_versions (
                        meeting_id, version_number, status, generation_method,
                        content, source_references, created_by
                    )
                    VALUES (%s, %s, 'DRAFT', 'HUMAN', %s::jsonb, %s::jsonb, %s)
                    RETURNING id, created_at;
                    """,
                    (
                        meeting_id,
                        new_version_number,
                        json.dumps(content),
                        json.dumps(version[6]),
                        user.id,
                    ),
                )
                row = cursor.fetchone()
                _audit(
                    cursor,
                    user,
                    "MEETING_MINUTES_REVISION_SAVED",
                    {
                        "meeting_id": meeting_id,
                        "previous_version_id": version_id,
                        "version_id": row[0],
                        "version_number": new_version_number,
                    },
                )
        return {
            "id": row[0],
            "meeting_id": meeting_id,
            "version_number": new_version_number,
            "status": "DRAFT",
            "generation_method": "HUMAN",
            "content": content,
            "source_references": version[6],
            "created_at": row[1],
        }
    finally:
        connection.close()


def submit_minutes_for_review(user, version_id):
    connection = get_connection()
    try:
        with connection:
            with connection.cursor() as cursor:
                version = _get_minutes_version(cursor, version_id)
                if version is None:
                    raise GovernanceWorkflowError(
                        "MINUTES_VERSION_NOT_FOUND", "Minutes version not found.", 404
                    )
                cursor.execute(
                    "SELECT id FROM governance_meetings WHERE id = %s FOR UPDATE;",
                    (version[1],),
                )
                _require_committee_membership(cursor, user, version[8])
                if version[3] not in {"DRAFT", "SUBMITTED"}:
                    raise GovernanceWorkflowError(
                        "MINUTES_NOT_DRAFT",
                        "Only a draft version can be submitted for review.",
                        409,
                    )
                if version[3] == "DRAFT":
                    cursor.execute(
                        """
                        UPDATE meeting_minutes_versions
                        SET status = 'SUBMITTED'
                        WHERE id = %s AND status = 'DRAFT';
                        """,
                        (version_id,),
                    )
                    _audit(
                        cursor,
                        user,
                        "MEETING_MINUTES_SUBMITTED_FOR_REVIEW",
                        {"meeting_id": version[1], "version_id": version_id},
                    )
        return get_minutes_workspace(user, version[1])
    finally:
        connection.close()


def add_minutes_comment(user, version_id, comment):
    connection = get_connection()
    try:
        with connection:
            with connection.cursor() as cursor:
                version = _get_minutes_version(cursor, version_id)
                if version is None:
                    raise GovernanceWorkflowError(
                        "MINUTES_VERSION_NOT_FOUND", "Minutes version not found.", 404
                    )
                cursor.execute(
                    "SELECT id FROM governance_meetings WHERE id = %s FOR UPDATE;",
                    (version[1],),
                )
                _require_committee_membership(cursor, user, version[8])
                if version[3] != "SUBMITTED":
                    raise GovernanceWorkflowError(
                        "MINUTES_NOT_UNDER_REVIEW",
                        "Comments are available only while a version is under review.",
                        409,
                    )
                cursor.execute(
                    """
                    INSERT INTO meeting_minutes_comments (
                        minutes_version_id, user_id, comment
                    )
                    VALUES (%s, %s, %s)
                    RETURNING id, created_at;
                    """,
                    (version_id, user.id, comment.strip()),
                )
                row = cursor.fetchone()
                _audit(
                    cursor,
                    user,
                    "MEETING_MINUTES_COMMENT_ADDED",
                    {"meeting_id": version[1], "version_id": version_id},
                )
        return {
            "id": row[0],
            "minutes_version_id": version_id,
            "comment": comment.strip(),
            "created_at": row[1],
        }
    finally:
        connection.close()


def approve_minutes(user, version_id):
    registry = load_governance_workflow_registry()
    connection = get_connection()
    try:
        with connection:
            with connection.cursor() as cursor:
                version = _get_minutes_version(cursor, version_id)
                if version is None:
                    raise GovernanceWorkflowError(
                        "MINUTES_VERSION_NOT_FOUND", "Minutes version not found.", 404
                    )
                meeting = get_meeting(user, version[1])
                cursor.execute(
                    "SELECT id FROM governance_meetings WHERE id = %s FOR UPDATE;",
                    (version[1],),
                )
                _require_committee_membership(cursor, user, version[8])
                policy = get_committee_workflow_policy(version[8], registry)
                if policy is None or not policy["minutes_approver_usernames"]:
                    raise GovernanceWorkflowError(
                        "MINUTES_APPROVAL_POLICY_UNCONFIGURED",
                        "Final minutes approval is blocked until an institutionally approved signatory policy is configured.",
                        409,
                    )
                if user.username.lower() not in policy["minutes_approver_usernames"]:
                    raise GovernanceWorkflowError(
                        "MINUTES_APPROVER_REQUIRED",
                        "This account is not a configured minutes approver.",
                        403,
                    )
                cursor.execute(
                    """
                    SELECT id, version_number
                    FROM meeting_minutes_versions
                    WHERE meeting_id = %s
                    ORDER BY version_number DESC
                    LIMIT 1
                    FOR UPDATE;
                    """,
                    (version[1],),
                )
                latest_version = cursor.fetchone()
                if latest_version is None or latest_version[0] != version_id:
                    raise GovernanceWorkflowError(
                        "MINUTES_VERSION_NOT_LATEST",
                        "Only the latest minutes revision can be finalized.",
                        409,
                    )
                cursor.execute(
                    """
                    SELECT r.id, r.agenda_item_index, r.record_type, r.content,
                           u.username, r.created_at
                    FROM meeting_records r
                    JOIN auth_users u ON u.id = r.created_by
                    WHERE r.meeting_id = %s
                    ORDER BY r.created_at, r.id;
                    """,
                    (version[1],),
                )
                records = [
                    {
                        "id": row[0],
                        "agenda_item_index": row[1],
                        "record_type": row[2],
                        "content": row[3],
                        "recorded_by": row[4],
                        "created_at": row[5],
                    }
                    for row in cursor.fetchall()
                ]
                _validate_minutes_context(meeting, records)
                if version[3] == "FINALIZED":
                    if version[9] != user.id:
                        raise GovernanceWorkflowError(
                            "MINUTES_ALREADY_FINALIZED",
                            "These minutes were finalized by another authorized signatory.",
                            409,
                        )
                    return {
                        "id": version_id,
                        "meeting_id": version[1],
                        "version_number": version[2],
                        "status": "FINALIZED",
                        "indexing_status": (
                            "INDEXER_NOT_IMPLEMENTED"
                            if policy["index_finalized_minutes"]
                            else "NOT_CONFIGURED"
                        ),
                        "indexing_note": (
                            "The shared finalized-minutes indexer is not implemented."
                            if policy["index_finalized_minutes"]
                            else "Minutes indexing is disabled by the workflow policy."
                        ),
                    }
                if version[3] != "SUBMITTED":
                    raise GovernanceWorkflowError(
                        "MINUTES_NOT_SUBMITTED",
                        "Only submitted minutes can be finalized.",
                        409,
                    )
                cursor.execute(
                    """
                    UPDATE meeting_minutes_versions
                    SET status = 'FINALIZED',
                        finalized_by = %s,
                        finalized_at = CURRENT_TIMESTAMP
                    WHERE id = %s AND status = 'SUBMITTED'
                    RETURNING meeting_id, version_number;
                    """,
                    (user.id, version_id),
                )
                finalized = cursor.fetchone()
                if finalized is None:
                    raise GovernanceWorkflowError(
                        "MINUTES_STATE_CONFLICT",
                        "The minutes state changed; reload before approval.",
                        409,
                    )
                _audit(
                    cursor,
                    user,
                    "MEETING_MINUTES_FINALIZED",
                    {
                        "meeting_id": finalized[0],
                        "version_id": version_id,
                        "version_number": finalized[1],
                        "registry_version": registry["registry_version"],
                        "index_finalized_minutes": policy[
                            "index_finalized_minutes"
                        ],
                    },
                )
                return {
                    "id": version_id,
                    "meeting_id": finalized[0],
                    "version_number": finalized[1],
                    "status": "FINALIZED",
                    "indexing_status": (
                        "INDEXER_NOT_IMPLEMENTED"
                        if policy["index_finalized_minutes"]
                        else "NOT_CONFIGURED"
                    ),
                    "indexing_note": (
                        "The shared finalized-minutes indexer is not implemented."
                        if policy["index_finalized_minutes"]
                        else "Minutes indexing is disabled by the workflow policy."
                    ),
                }
    finally:
        connection.close()

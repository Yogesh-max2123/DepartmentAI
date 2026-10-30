import pytest
from datetime import datetime, timedelta, timezone

from backend.api.governance_routes import router
from backend.llm.minutes_generator import (
    MinutesGenerationUnavailable,
    generate_minutes_draft,
)
from backend.services.governance_meeting_service import (
    _minutes_review_issues,
)
from backend.services import governance_meeting_service as meeting_service
from backend.services.governance_workflow_registry import (
    _validate,
    load_governance_workflow_registry,
)


def _policy():
    return {
        "committee_type": "DUGC",
        "approval_status": "APPROVED",
        "activation_scope": "TEST_ONLY",
        "approval_evidence": "Synthetic test policy.",
        "minimum_confirmations": 1,
        "meeting_approver_usernames": ["synthetic-approver"],
        "minutes_approver_usernames": ["synthetic-signatory"],
        "index_finalized_minutes": False,
    }


def test_empty_governance_policy_registry_is_unconfigured():
    result = _validate(
        {
            "schema_version": 1,
            "registry_version": "empty-test",
            "committee_policies": [],
        }
    )

    assert result["status"] == "UNCONFIGURED"
    assert result["committee_policies"] == []


def test_governance_policy_registry_accepts_scoped_test_policy():
    result = _validate(
        {
            "schema_version": 1,
            "registry_version": "valid-test",
            "committee_policies": [_policy()],
        }
    )

    assert result["status"] == "AVAILABLE"
    assert result["committee_policies"][0]["meeting_approver_usernames"] == [
        "synthetic-approver"
    ]


def test_governance_policy_registry_rejects_duplicate_approvers():
    policy = _policy()
    policy["meeting_approver_usernames"] = [
        "synthetic-approver",
        "SYNTHETIC-APPROVER",
    ]

    result = _validate(
        {
            "schema_version": 1,
            "registry_version": "invalid-test",
            "committee_policies": [policy],
        }
    )

    assert result["status"] == "UNAVAILABLE"
    assert "cannot contain duplicates" in result["diagnostics"][0]


def test_governance_registry_reports_missing_configuration(tmp_path):
    registry = tmp_path / "missing.json"

    with pytest.raises(OSError):
        registry.read_text(encoding="utf-8")
    result = load_governance_workflow_registry(str(registry))

    assert result["status"] == "UNAVAILABLE"


def test_minutes_review_detects_unresolved_and_conflicting_decisions():
    meeting = {
        "agenda": [
            {"index": 0, "title": "Admission review"},
            {"index": 1, "title": "Research progress"},
        ]
    }
    records = [
        {
            "id": 10,
            "agenda_item_index": 0,
            "record_type": "DECISION",
            "content": "The committee approved the application.",
        },
        {
            "id": 11,
            "agenda_item_index": 0,
            "record_type": "DECISION",
            "content": "The committee rejected the application.",
        },
    ]

    issues = _minutes_review_issues(meeting, records)

    assert {issue["kind"] for issue in issues} == {
        "UNRESOLVED_AGENDA_ITEM",
        "POSSIBLE_CONFLICT",
    }
    assert any(issue.get("record_ids") == [10, 11] for issue in issues)


def test_minutes_review_accepts_a_human_recorded_deferral():
    meeting = {"agenda": [{"index": 0, "title": "Admission review"}]}
    records = [
        {
            "id": 12,
            "agenda_item_index": 0,
            "record_type": "DECISION",
            "content": "Decision deferred pending additional evidence.",
        }
    ]

    assert _minutes_review_issues(meeting, records) == []


def test_minutes_generation_fails_closed_without_data_sharing_approval(
    monkeypatch,
):
    monkeypatch.delenv("DEPARTMENTAI_MINUTES_LLM_APPROVED", raising=False)

    with pytest.raises(MinutesGenerationUnavailable, match="data-sharing approval"):
        generate_minutes_draft({}, [], [])


def test_governance_routes_are_exposed_under_authenticated_api():
    paths = {route.path for route in router.routes}

    assert "/governance/meetings" in paths
    assert "/governance/meetings/{meeting_id}/agenda" in paths
    assert "/governance/meetings/{meeting_id}/notice" in paths
    assert "/governance/meetings/{meeting_id}/minutes" in paths
    assert "/governance/minutes/{version_id}/approve" in paths
    assert "/governance/applications/{application_id}/meetings" in paths
    assert (
        "/governance/applications/{application_id}/meetings/{meeting_id}/approve"
        in paths
    )
    assert (
        "/governance/applications/{application_id}/meetings/{meeting_id}/response"
        in paths
    )


class _ScopeCursor:
    def __init__(self, result):
        self.result = result
        self.query = None
        self.parameters = None

    def execute(self, query, parameters):
        self.query = query
        self.parameters = parameters

    def fetchone(self):
        return self.result


def test_official_meeting_scope_requires_owned_application_and_matching_committee():
    cursor = _ScopeCursor((1,))
    user = type("User", (), {"id": 31, "role": "OFFICIAL"})()

    meeting_service._require_application_committee_access(
        cursor,
        user,
        application_id=55,
        committee="DUGC",
    )

    assert "official_application_assignments" in cursor.query
    assert "committee_memberships" in cursor.query
    assert cursor.parameters == (55, 31, "DUGC")


def test_official_meeting_scope_rejects_unassigned_application():
    cursor = _ScopeCursor(None)
    user = type("User", (), {"id": 31, "role": "OFFICIAL"})()

    with pytest.raises(meeting_service.GovernanceWorkflowError) as error:
        meeting_service._require_application_committee_access(
            cursor,
            user,
            application_id=55,
            committee="DUGC",
        )

    assert error.value.code == "APPLICATION_SCOPE_DENIED"


def test_official_cannot_create_unlinked_meeting_or_confirm_meetings():
    user = type(
        "User",
        (),
        {"id": 31, "role": "OFFICIAL", "username": "synthetic-official"},
    )()
    payload = {
        "agenda": [{"title": "Review", "application_ids": []}],
    }

    with pytest.raises(meeting_service.GovernanceWorkflowError) as create_error:
        meeting_service.create_meeting(user, payload)

    assert create_error.value.code == "APPLICATION_LINK_REQUIRED"
    with pytest.raises(meeting_service.GovernanceWorkflowError) as approve_error:
        meeting_service.approve_meeting(user, 1)
    assert approve_error.value.code == "COMMITTEE_ROLE_REQUIRED"
    with pytest.raises(meeting_service.GovernanceWorkflowError) as response_error:
        meeting_service.respond_to_meeting(user, 1, "CONFIRMED")
    assert response_error.value.code == "COMMITTEE_ROLE_REQUIRED"


def test_dugc_cannot_create_meeting_proposals():
    user = type(
        "User",
        (),
        {"id": 41, "role": "DUGC", "username": "synthetic-member"},
    )()
    payload = {
        "agenda": [{"title": "Review", "application_ids": [55]}],
    }

    with pytest.raises(meeting_service.GovernanceWorkflowError) as error:
        meeting_service.create_meeting(user, payload)

    assert error.value.code == "COMMITTEE_ROLE_REQUIRED"


class _ApplicationMeetingsCursor:
    def __init__(self):
        self.rows = [
            (
                17,
                "DUGC",
                "Synthetic proposal",
                "APPROVED_PENDING_CONFIRMATIONS",
                datetime.now(timezone.utc),
                datetime.now(timezone.utc) + timedelta(hours=2),
                datetime.now(timezone.utc) + timedelta(days=1),
                60,
                None,
            )
        ]
        self.query = ""

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, _parameters=None):
        self.query = query

    def fetchall(self):
        return self.rows


class _ApplicationMeetingsConnection:
    def __init__(self):
        self.active_cursor = _ApplicationMeetingsCursor()

    def cursor(self):
        return self.active_cursor

    def close(self):
        pass


def test_linked_application_exposes_pending_confirmation_action(monkeypatch):
    connection = _ApplicationMeetingsConnection()
    monkeypatch.setattr(meeting_service, "get_connection", lambda: connection)
    monkeypatch.setattr(
        meeting_service,
        "get_committee_workflow_policy",
        lambda _committee: {
            "meeting_approver_usernames": ["synthetic-approver"],
            "minimum_confirmations": 1,
        },
    )
    user = type(
        "User",
        (),
        {
            "id": 7,
            "role": "DUGC",
            "username": "synthetic-member",
        },
    )()

    result = meeting_service.get_application_meetings(user, 55)

    assert "committee_memberships" in connection.active_cursor.query
    assert result["meetings"][0]["can_confirm"] is True
    assert result["meetings"][0]["can_approve"] is False


class _CandidateCursor:
    def __init__(self):
        self.rows = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, _parameters=None):
        if "SELECT 1" in query:
            self.rows = [(1,)]
        elif "SELECT m.user_id, u.username" in query:
            self.rows = [(7, "member-without-availability")]
        elif "SELECT user_id, available_from" in query:
            self.rows = []
        elif "SELECT proposed_slot_start" in query:
            self.rows = []
        else:
            raise AssertionError(f"Unexpected query: {query}")

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None

    def fetchall(self):
        rows, self.rows = self.rows, []
        return rows


class _CandidateConnection:
    def __init__(self):
        self.active_cursor = _CandidateCursor()

    def cursor(self):
        return self.active_cursor

    def close(self):
        pass


def test_candidate_slot_search_handles_members_without_submissions(monkeypatch):
    monkeypatch.setattr(
        meeting_service,
        "get_connection",
        _CandidateConnection,
    )
    now = datetime.now(timezone.utc) + timedelta(days=1)

    result = meeting_service.calculate_candidate_slots(
        user=type("User", (), {"id": 7, "role": "DUGC"})(),
        committee_type="DUGC",
        range_start=now,
        range_end=now + timedelta(hours=2),
        duration_minutes=60,
    )

    assert result["status"] == "INCOMPLETE_AVAILABILITY"
    assert result["missing_members"] == [
        {"user_id": 7, "username": "member-without-availability"}
    ]
    assert result["candidate_slots"]
    assert not any(slot["candidate"] for slot in result["candidate_slots"])


def test_conflicting_candidate_slot_cannot_be_proposed(monkeypatch):
    start = datetime.now(timezone.utc) + timedelta(days=1)
    meeting = {
        "id": 4,
        "committee_type": "DUGC",
        "status": "PROPOSED",
        "proposed_start": start,
        "proposed_end": start + timedelta(hours=2),
        "duration_minutes": 60,
    }
    monkeypatch.setattr(
        meeting_service,
        "get_meeting",
        lambda *_args, **_kwargs: meeting,
    )
    monkeypatch.setattr(
        meeting_service,
        "calculate_candidate_slots",
        lambda *_args, **_kwargs: {
            "candidate_slots": [
                {"start": start, "candidate": False},
            ]
        },
    )

    with pytest.raises(meeting_service.GovernanceWorkflowError) as error:
        meeting_service.select_meeting_slot(
            type("User", (), {"id": 7, "role": "OFFICIAL"})(),
            4,
            start,
        )

    assert error.value.code == "SLOT_NOT_AVAILABLE"

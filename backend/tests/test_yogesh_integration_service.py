from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend.api import routes
from backend.services import governance_meeting_service as meeting_service
from backend.services.local_demo import LocalDemoProgrammeIdentityProvider
from backend.services import yogesh_integration_service as integration


def _enable_local_integration(monkeypatch, programme="MTECH"):
    monkeypatch.setenv(integration.INTEGRATION_ENABLED_ENV, "true")
    monkeypatch.setenv(integration.INTEGRATION_TOKEN_ENV, "synthetic-token")
    monkeypatch.setenv(
        f"DEPARTMENTAI_YOGESH_{programme}_URL",
        "http://127.0.0.1:8003",
    )
    monkeypatch.setattr(
        integration,
        "get_database_settings",
        lambda: SimpleNamespace(
            environment="test",
            database="departmentai_test",
        ),
    )
    monkeypatch.setattr(integration, "local_demo_enabled", lambda: True)


def test_application_advisory_uses_local_programme_rag_and_persists(
    monkeypatch,
):
    _enable_local_integration(monkeypatch)
    calls = []
    monkeypatch.setattr(
        integration,
        "_post_json",
        lambda url, payload: calls.append((url, payload))
        or {
            "programme": "MTECH",
            "answer": "Consult the applicable M.Tech ordinance section.",
            "sources": [
                {
                    "source_file": (
                        "Ordinances for Masters Programme 2023.pdf"
                    ),
                    "section": "7",
                }
            ],
        },
    )
    monkeypatch.setattr(
        integration,
        "_store_advisory",
        lambda application_id, _application, programme, answer, sources: {
            "application_id": application_id,
            "programme": programme,
            "answer": answer,
            "sources": sources,
        },
    )
    application = {
        "application_type": "MTECH_TEST_APPLICATION",
        "title": "Synthetic thesis proposal",
        "description": "A synthetic project description.",
        "applicant_identifier": "MUST_NOT_BE_SENT",
    }

    result = integration.generate_application_advisory(
        42,
        application,
        "MTECH",
    )

    assert result["application_id"] == 42
    assert calls[0][0] == "http://127.0.0.1:8003/integration/ask"
    assert calls[0][1]["programme"] == "MTECH"
    assert "Synthetic thesis proposal" in calls[0][1]["question"]
    assert "MUST_NOT_BE_SENT" not in calls[0][1]["question"]


def test_application_advisory_rejects_non_loopback_upstream(monkeypatch):
    _enable_local_integration(monkeypatch)
    monkeypatch.setenv(
        "DEPARTMENTAI_YOGESH_MTECH_URL",
        "http://example.invalid:8003",
    )
    with pytest.raises(integration.YogeshIntegrationError, match="loopback"):
        integration.generate_application_advisory(
            42,
            {"application_type": "MTECH_TEST_APPLICATION"},
            "MTECH",
        )


def test_application_advisory_requires_programme_scoped_sources(monkeypatch):
    _enable_local_integration(monkeypatch)
    monkeypatch.setattr(
        integration,
        "_post_json",
        lambda *_args, **_kwargs: {
            "programme": "MTECH",
            "answer": "A sourced advisory.",
            "sources": [
                {
                    "source_file": (
                        "Ordinances_for_Doctoral_Programm2023.pdf"
                    )
                }
            ],
        },
    )
    stored = []
    monkeypatch.setattr(
        integration,
        "_store_advisory",
        lambda *args: stored.append(args),
    )

    with pytest.raises(integration.YogeshIntegrationError, match="outside"):
        integration.generate_application_advisory(
            42,
            {"application_type": "MTECH_TEST_APPLICATION"},
            "MTECH",
        )
    assert stored == []


def test_application_advisory_reports_empty_evidence_without_persisting(
    monkeypatch,
):
    _enable_local_integration(monkeypatch)
    monkeypatch.setattr(
        integration,
        "_post_json",
        lambda *_args, **_kwargs: {
            "programme": "MTECH",
            "answer": "No sources were retrieved.",
            "sources": [],
        },
    )
    stored = []
    monkeypatch.setattr(
        integration,
        "_store_advisory",
        lambda *args: stored.append(args),
    )

    with pytest.raises(integration.YogeshIntegrationError, match="no ordinance"):
        integration.generate_application_advisory(
            42,
            {"application_type": "MTECH_TEST_APPLICATION"},
            "MTECH",
        )
    assert stored == []


def test_application_advisory_requires_explicit_local_enablement(monkeypatch):
    monkeypatch.delenv(integration.INTEGRATION_ENABLED_ENV, raising=False)
    with pytest.raises(integration.YogeshIntegrationError, match="not enabled"):
        integration.generate_application_advisory(
            42,
            {"application_type": "MTECH_TEST_APPLICATION"},
            "MTECH",
        )


def test_advisory_fingerprint_tracks_only_submitted_application_fields():
    original = {
        "application_type": "MTECH_TEST_APPLICATION",
        "title": "Synthetic proposal",
        "description": "Synthetic description.",
        "applicant_identifier": "synthetic-applicant",
    }

    assert integration._application_fingerprint(original) == (
        integration._application_fingerprint(
            {
                **original,
                "applicant_identifier": "different-private-identifier",
            }
        )
    )
    assert integration._application_fingerprint(original) != (
        integration._application_fingerprint(
            {**original, "description": "Updated synthetic description."}
        )
    )


def test_internal_request_sends_server_side_shared_token(monkeypatch):
    monkeypatch.setenv(integration.INTEGRATION_TOKEN_ENV, "synthetic-token")
    requests = []

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self, _limit):
            return b'{"ok": true}'

    class _Opener:
        def open(self, request, timeout):
            requests.append((request, timeout))
            return _Response()

    monkeypatch.setattr(
        integration,
        "build_opener",
        lambda _handler: _Opener(),
    )

    result = integration._post_json(
        "http://127.0.0.1:8003/integration/ask",
        {"question": "Synthetic question"},
    )

    assert result == {"ok": True}
    token_headers = [
        value
        for key, value in requests[0][0].header_items()
        if key.lower() == "x-sostudy-integration-token"
    ]
    assert token_headers == ["synthetic-token"]
    assert requests[0][1] == integration.REQUEST_TIMEOUT_SECONDS


def test_application_advisory_route_requires_owned_draft_and_test_policy(
    monkeypatch,
):
    user = SimpleNamespace(role="STUDENT")
    application = {
        "id": 42,
        "applicant_identifier": "DEMO-MTECH-0001",
        "application_type": "MTECH_TEST_APPLICATION",
        "title": "Synthetic thesis proposal",
        "description": "Synthetic description.",
        "status": "DRAFT",
    }
    access_checks = []
    monkeypatch.setattr(
        routes,
        "require_application_access",
        lambda active_user, application_id, *roles: access_checks.append(
            (active_user, application_id, roles)
        ),
    )
    monkeypatch.setattr(routes, "get_application", lambda _id: application)
    monkeypatch.setattr(
        routes,
        "load_application_policy_registry",
        lambda: {"status": "AVAILABLE"},
    )
    monkeypatch.setattr(
        routes,
        "resolve_application_policy",
        lambda *_args: {
            "status": "RESOLVED",
            "application_type": {"activation_scope": "TEST_ONLY"},
        },
    )
    monkeypatch.setattr(
        routes,
        "generate_application_advisory",
        lambda *_args: {"status": "COMPLETED", "advisory": True},
    )

    result = routes.run_yogesh_application_advisory(
        42,
        user,
        LocalDemoProgrammeIdentityProvider(),
    )

    assert result == {"status": "COMPLETED", "advisory": True}
    assert access_checks == [(user, 42, ("STUDENT",))]


def test_application_advisory_route_rejects_non_draft(monkeypatch):
    monkeypatch.setattr(
        routes,
        "require_application_access",
        lambda *_args: None,
    )
    monkeypatch.setattr(
        routes,
        "get_application",
        lambda _id: {
            "id": 42,
            "applicant_identifier": "DEMO-MTECH-0001",
            "application_type": "MTECH_TEST_APPLICATION",
            "status": "SUBMITTED",
        },
    )

    with pytest.raises(HTTPException) as error:
        routes.run_yogesh_application_advisory(
            42,
            SimpleNamespace(role="STUDENT"),
            LocalDemoProgrammeIdentityProvider(),
        )
    assert getattr(error.value, "status_code", None) == 409


def test_application_advisory_route_is_student_only():
    with pytest.raises(HTTPException) as error:
        routes.run_yogesh_application_advisory(
            42,
            SimpleNamespace(role="OFFICIAL"),
            LocalDemoProgrammeIdentityProvider(),
        )
    assert error.value.status_code == 403


class _CandidateSlotCursor:
    def __init__(self, members, availability, booked):
        self.results = [members, availability, booked]

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def execute(self, *_args):
        return None

    def fetchall(self):
        return self.results.pop(0)


class _CandidateSlotConnection:
    def __init__(self, cursor):
        self.active_cursor = cursor
        self.closed = False

    def cursor(self):
        return self.active_cursor

    def close(self):
        self.closed = True


def test_candidate_slots_intersect_persisted_availability_with_yogesh(
    monkeypatch,
):
    range_start = datetime(2035, 1, 2, 9, tzinfo=timezone.utc)
    range_end = datetime(2035, 1, 2, 10, tzinfo=timezone.utc)
    cursor = _CandidateSlotCursor(
        [(1, "synthetic-member")],
        [(1, range_start, range_end, "AVAILABLE")],
        [],
    )
    connection = _CandidateSlotConnection(cursor)
    monkeypatch.setattr(meeting_service, "get_connection", lambda: connection)
    monkeypatch.setattr(
        meeting_service,
        "_require_committee_membership",
        lambda *_args: None,
    )
    monkeypatch.setattr(
        integration,
        "is_integration_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        integration,
        "get_meeting_options",
        lambda programme, *_args: {
            "status": "COMPLETED",
            "programme": programme,
            "candidate_slots": [
                {
                    "start": "2035-01-02T09:00:00+00:00",
                    "end": "2035-01-02T09:30:00+00:00",
                    "candidate": True,
                },
                {
                    "start": "2035-01-02T09:30:00+00:00",
                    "end": "2035-01-02T10:00:00+00:00",
                    "candidate": False,
                },
            ],
        },
    )

    result = meeting_service.calculate_candidate_slots(
        SimpleNamespace(id=1, username="synthetic-member", role="DUGC"),
        "DMPC",
        range_start,
        range_end,
        30,
    )

    assert result["scheduler_integration"]["programme"] == "MTECH"
    assert result["availability_source"] == (
        "SOSTUDY_EXPLICIT_MEMBER_SUBMISSIONS_AND_YOGESH_REFERENCE"
    )
    assert [slot["candidate"] for slot in result["candidate_slots"]] == [
        True,
        False,
    ]
    assert [slot["yogesh_candidate"] for slot in result["candidate_slots"]] == [
        True,
        False,
    ]
    assert connection.closed


def test_candidate_slots_fail_closed_when_yogesh_scheduler_is_unavailable(
    monkeypatch,
):
    range_start = datetime(2035, 1, 2, 9, tzinfo=timezone.utc)
    range_end = datetime(2035, 1, 2, 10, tzinfo=timezone.utc)
    connection = _CandidateSlotConnection(
        _CandidateSlotCursor(
            [(1, "synthetic-member")],
            [(1, range_start, range_end, "AVAILABLE")],
            [],
        )
    )
    monkeypatch.setattr(meeting_service, "get_connection", lambda: connection)
    monkeypatch.setattr(
        meeting_service,
        "_require_committee_membership",
        lambda *_args: None,
    )
    monkeypatch.setattr(
        integration,
        "is_integration_enabled",
        lambda: True,
    )

    def unavailable(*_args):
        raise integration.YogeshIntegrationError("upstream unavailable")

    monkeypatch.setattr(
        integration,
        "get_meeting_options",
        unavailable,
    )

    with pytest.raises(meeting_service.GovernanceWorkflowError) as error:
        meeting_service.calculate_candidate_slots(
            SimpleNamespace(id=1, username="synthetic-member", role="DUGC"),
            "DMPC",
            range_start,
            range_end,
            30,
        )
    assert error.value.code == "YOGESH_SCHEDULER_UNAVAILABLE"
    assert error.value.status_code == 503
    assert connection.closed


def test_meeting_options_pass_persisted_conflicts_to_the_real_scheduler(
    monkeypatch,
):
    _enable_local_integration(monkeypatch)
    calls = []
    start = datetime(2035, 1, 2, 9, tzinfo=timezone.utc)
    end = datetime(2035, 1, 2, 10, tzinfo=timezone.utc)
    monkeypatch.setattr(
        integration,
        "_post_json",
        lambda url, payload: calls.append((url, payload))
        or {
            "status": "COMPLETED",
            "programme": "MTECH",
            "candidate_slots": [
                {
                    "start": "2035-01-02T09:00:00+00:00",
                    "end": "2035-01-02T09:30:00+00:00",
                    "candidate": True,
                }
            ],
        },
    )

    result = integration.get_meeting_options(
        "MTECH",
        start,
        end,
        30,
        [{"start": start, "end": end}],
    )

    assert calls[0][0] == (
        "http://127.0.0.1:8003/integration/meeting-options"
    )
    assert calls[0][1]["reserved_slots"] == [
        {
            "start": "2035-01-02T09:00:00+00:00",
            "end": "2035-01-02T10:00:00+00:00",
        }
    ]
    assert result["candidate_slots"][0]["candidate"] is True


def test_meeting_options_reject_naive_reserved_time(monkeypatch):
    _enable_local_integration(monkeypatch)
    start = datetime(2035, 1, 2, 9, tzinfo=timezone.utc)
    end = datetime(2035, 1, 2, 10, tzinfo=timezone.utc)

    with pytest.raises(integration.YogeshIntegrationError, match="timestamps"):
        integration.get_meeting_options(
            "MTECH",
            start,
            end,
            30,
            [{"start": start.replace(tzinfo=None), "end": end}],
        )

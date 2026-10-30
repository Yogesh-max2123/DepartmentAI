import ipaddress
import json
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.database.connection import get_connection, get_database_settings
from backend.main import app
from backend.services.auth_service import hash_password


pytestmark = pytest.mark.skipif(
    os.getenv("DEPARTMENTAI_DATABASE_ENV") != "test",
    reason="Set DEPARTMENTAI_DATABASE_ENV=test for isolated governance integration.",
)


def _assert_test_profile():
    settings = get_database_settings()
    assert settings.environment == "test"
    assert settings.database == "departmentai_test"
    assert ipaddress.ip_address(settings.host).is_loopback


def _next_half_hour():
    value = datetime.now(timezone.utc) + timedelta(days=2)
    minute = 30 if value.minute < 30 else 60
    return value.replace(minute=0, second=0, microsecond=0) + timedelta(
        minutes=minute
    )


def test_authenticated_governance_meeting_and_minutes_lifecycle(
    tmp_path,
    monkeypatch,
):
    _assert_test_profile()
    suffix = uuid4().hex
    accounts = [
        {
            "username": f"gov-organizer-{suffix}",
            "password": f"synthetic-{suffix}",
            "committee": "DDPC",
        },
        {
            "username": f"gov-member-{suffix}",
            "password": f"synthetic-{suffix}",
            "committee": "DDPC",
        },
        {
            "username": f"gov-other-committee-{suffix}",
            "password": f"synthetic-{suffix}",
            "committee": "DMPC",
        },
    ]
    user_ids = []
    tokens = {}
    original_ddpc_memberships = []

    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT membership.user_id, membership.assigned_at
                    FROM committee_memberships AS membership
                    JOIN auth_users AS account ON account.id = membership.user_id
                    WHERE membership.committee_type = 'DDPC'
                      AND account.is_active = TRUE;
                    """
                )
                original_ddpc_memberships = cursor.fetchall()
                if original_ddpc_memberships:
                    original_member_ids = [
                        membership[0]
                        for membership in original_ddpc_memberships
                    ]
                    cursor.execute(
                        """
                        DELETE FROM committee_memberships
                        WHERE committee_type = 'DDPC'
                          AND user_id = ANY(%s);
                        """,
                        (original_member_ids,),
                    )
                for account in accounts:
                    cursor.execute(
                        """
                        INSERT INTO auth_users (
                            username, password_hash, role, subject_identifier
                        )
                        VALUES (%s, %s, 'DUGC', %s)
                        RETURNING id;
                        """,
                        (
                            account["username"],
                            hash_password(account["password"]),
                            f"synthetic-governance-{suffix}",
                        ),
                    )
                    user_id = cursor.fetchone()[0]
                    user_ids.append(user_id)
                    cursor.execute(
                        """
                        INSERT INTO committee_memberships (user_id, committee_type)
                        VALUES (%s, %s);
                        """,
                        (user_id, account["committee"]),
                    )

        with TestClient(app) as client:
            for index, account in enumerate(accounts):
                response = client.post(
                    "/auth/login",
                    json={
                        "username": account["username"],
                        "password": account["password"],
                    },
                )
                assert response.status_code == 200, response.text
                tokens[index] = {
                    "Authorization": f"Bearer {response.json()['access_token']}"
                }

            registry_file = tmp_path / "governance-test-policy.json"
            registry_file.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "registry_version": f"synthetic-{suffix}",
                        "committee_policies": [],
                    }
                ),
                encoding="utf-8",
            )
            monkeypatch.setenv(
                "DEPARTMENTAI_GOVERNANCE_WORKFLOW_CONFIG",
                str(registry_file),
            )

            start = _next_half_hour()
            end = start + timedelta(hours=2)
            availability = {
                "committee_type": "DDPC",
                "available_from": start.isoformat(),
                "available_until": end.isoformat(),
                "availability": "AVAILABLE",
            }
            for index in (0,):
                assert client.post(
                    "/governance/availability",
                    json=availability,
                    headers=tokens[index],
                ).status_code == 201

            meeting_request = {
                "committee_type": "DDPC",
                "title": "Synthetic committee meeting",
                "purpose": "Isolated governance workflow test.",
                "proposed_start": start.isoformat(),
                "proposed_end": end.isoformat(),
                "duration_minutes": 60,
                "agenda": [
                    {
                        "title": "Synthetic progress review",
                        "description": "Test-only agenda item.",
                        "application_ids": [],
                    }
                ],
            }
            headers = {
                **tokens[0],
                "Idempotency-Key": f"governance-{suffix}",
            }
            created = client.post(
                "/governance/meetings",
                json=meeting_request,
                headers=headers,
            )
            assert created.status_code == 201, created.text
            meeting_id = created.json()["id"]
            retried = client.post(
                "/governance/meetings",
                json=meeting_request,
                headers=headers,
            )
            assert retried.status_code == 201
            assert retried.json()["id"] == meeting_id
            listed = client.get(
                "/governance/meetings",
                params={"committee_type": "DDPC"},
                headers=tokens[0],
            )
            assert listed.status_code == 200, listed.text
            assert any(item["id"] == meeting_id for item in listed.json())

            assert client.get(
                f"/governance/meetings/{meeting_id}",
                headers=tokens[2],
            ).status_code == 404
            candidates = client.get(
                "/governance/meetings/slots",
                params={
                    "committee_type": "DDPC",
                    "range_start": start.isoformat(),
                    "range_end": end.isoformat(),
                    "duration_minutes": 60,
                },
                headers=tokens[0],
            )
            assert candidates.status_code == 200, candidates.text
            incomplete = candidates.json()
            assert incomplete["status"] == "INCOMPLETE_AVAILABILITY"
            assert not any(
                item["candidate"] for item in incomplete["candidate_slots"]
            )
            assert accounts[1]["username"] in {
                member["username"] for member in incomplete["missing_members"]
            }

            assert client.post(
                "/governance/availability",
                json=availability,
                headers=tokens[1],
            ).status_code == 201
            candidates = client.get(
                "/governance/meetings/slots",
                params={
                    "committee_type": "DDPC",
                    "range_start": start.isoformat(),
                    "range_end": end.isoformat(),
                    "duration_minutes": 60,
                },
                headers=tokens[0],
            )
            assert candidates.status_code == 200, candidates.text
            complete = candidates.json()
            assert complete["status"] == "COMPLETED"
            slot = next(
                item for item in complete["candidate_slots"]
                if item["candidate"]
            )
            selected = client.patch(
                f"/governance/meetings/{meeting_id}/slot",
                json={"proposed_slot_start": slot["start"]},
                headers=tokens[0],
            )
            assert selected.status_code == 200, selected.text
            premature_record = client.post(
                f"/governance/meetings/{meeting_id}/records",
                json={
                    "agenda_item_index": 0,
                    "record_type": "NOTE",
                    "content": "A proposal must not accept meeting records.",
                },
                headers=tokens[0],
            )
            assert premature_record.status_code == 409
            reselected = client.patch(
                f"/governance/meetings/{meeting_id}/slot",
                json={"proposed_slot_start": slot["start"]},
                headers=tokens[0],
            )
            assert reselected.status_code == 200, reselected.text
            second = client.post(
                "/governance/meetings",
                json=meeting_request,
                headers={**tokens[0], "Idempotency-Key": f"overlap-{suffix}"},
            )
            assert second.status_code == 201, second.text
            overlap = client.patch(
                f"/governance/meetings/{second.json()['id']}/slot",
                json={"proposed_slot_start": slot["start"]},
                headers=tokens[0],
            )
            assert overlap.status_code == 409

            blocked_approval = client.post(
                f"/governance/meetings/{meeting_id}/approve",
                headers=tokens[0],
            )
            assert blocked_approval.status_code == 409
            registry_file.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "registry_version": f"synthetic-{suffix}",
                        "committee_policies": [
                            {
                                "committee_type": "DDPC",
                                "approval_status": "APPROVED",
                                "activation_scope": "TEST_ONLY",
                                "approval_evidence": "Synthetic integration-test policy.",
                                "minimum_confirmations": 1,
                                "meeting_approver_usernames": [
                                    accounts[0]["username"]
                                ],
                                "minutes_approver_usernames": [
                                    accounts[0]["username"]
                                ],
                                "index_finalized_minutes": False,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            approved = client.post(
                f"/governance/meetings/{meeting_id}/approve",
                headers=tokens[0],
            )
            assert approved.status_code == 200, approved.text
            confirmed = client.post(
                f"/governance/meetings/{meeting_id}/response",
                json={"response": "CONFIRMED"},
                headers=tokens[1],
            )
            assert confirmed.status_code == 200, confirmed.text
            assert confirmed.json()["status"] == "CONFIRMED"

            for record_type, content in (
                ("ATTENDANCE", "Synthetic member attended."),
                ("NOTE", "Progress information was presented."),
                ("OBSERVATION", "Evidence requires committee review."),
                ("DECISION", "Decision deferred pending additional evidence."),
            ):
                response = client.post(
                    f"/governance/meetings/{meeting_id}/records",
                    json={
                        "agenda_item_index": 0,
                        "record_type": record_type,
                        "content": content,
                    },
                    headers=tokens[0],
                )
                assert response.status_code == 201, response.text

            manual_draft = client.post(
                f"/governance/meetings/{meeting_id}/minutes",
                headers=tokens[0],
            )
            assert manual_draft.status_code == 201, manual_draft.text
            assert manual_draft.json()["generation_method"] == "HUMAN"
            version_id = manual_draft.json()["id"]

            revision = client.patch(
                f"/governance/meetings/{meeting_id}/minutes/{version_id}",
                json={"content": manual_draft.json()["content"]},
                headers=tokens[0],
            )
            assert revision.status_code == 200, revision.text
            revision_id = revision.json()["id"]
            assert revision.json()["version_number"] == 2
            submitted = client.post(
                f"/governance/minutes/{revision_id}/submit",
                headers=tokens[0],
            )
            assert submitted.status_code == 200, submitted.text
            comment = client.post(
                f"/governance/minutes/{revision_id}/comments",
                json={"comment": "Synthetic review comment."},
                headers=tokens[1],
            )
            assert comment.status_code == 201, comment.text
            finalized = client.post(
                f"/governance/minutes/{revision_id}/approve",
                headers=tokens[0],
            )
            assert finalized.status_code == 200, finalized.text
            assert finalized.json()["status"] == "FINALIZED"
            assert finalized.json()["indexing_status"] == "NOT_CONFIGURED"
            assert client.post(
                f"/governance/meetings/{meeting_id}/records",
                json={
                    "agenda_item_index": 0,
                    "record_type": "NOTE",
                    "content": "This late record must be rejected.",
                },
                headers=tokens[0],
            ).status_code == 409
            workspace = client.get(
                f"/governance/meetings/{meeting_id}/minutes",
                headers=tokens[0],
            )
            assert workspace.status_code == 200
            assert workspace.json()["latest_version"]["status"] == "FINALIZED"
            assert workspace.json()["comments"][0]["comment"] == (
                "Synthetic review comment."
            )
    finally:
        if user_ids:
            with get_connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        DELETE FROM governance_meetings
                        WHERE organizer_user_id = ANY(%s);
                        """,
                        (user_ids,),
                    )
                    cursor.execute(
                        "DELETE FROM meeting_member_availability WHERE user_id = ANY(%s);",
                        (user_ids,),
                    )
                    cursor.execute(
                        "DELETE FROM committee_memberships WHERE user_id = ANY(%s);",
                        (user_ids,),
                    )
                    cursor.execute(
                        "DELETE FROM auth_users WHERE id = ANY(%s);",
                        (user_ids,),
                    )
                    for user_id, assigned_at in original_ddpc_memberships:
                        cursor.execute(
                            """
                            INSERT INTO committee_memberships (
                                user_id, committee_type, assigned_at
                            )
                            VALUES (%s, 'DDPC', %s)
                            ON CONFLICT (user_id, committee_type) DO NOTHING;
                            """,
                            (user_id, assigned_at),
                        )

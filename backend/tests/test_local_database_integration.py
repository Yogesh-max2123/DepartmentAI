import ipaddress
import os
import uuid

import pytest
from fastapi.testclient import TestClient

from backend.database.connection import get_connection, get_database_settings
from backend.main import app
from backend.services import document_service
from backend.services.auth_service import hash_password


pytestmark = pytest.mark.skipif(
    os.getenv("DEPARTMENTAI_DATABASE_ENV") != "test",
    reason="Set DEPARTMENTAI_DATABASE_ENV=test to enable local DB integration.",
)

REQUIRED_TABLES = {
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
}


def _assert_isolated_test_database() -> None:
    settings = get_database_settings()
    assert settings.environment == "test"
    assert settings.database == "departmentai_test"
    assert ipaddress.ip_address(settings.host).is_loopback

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT tablename
                FROM pg_tables
                WHERE schemaname = 'public';
                """
            )
            tables = {row[0] for row in cursor.fetchall()}
    assert REQUIRED_TABLES <= tables


def test_local_student_official_dugc_database_workflow(tmp_path, monkeypatch):
    _assert_isolated_test_database()
    marker = f"SYNTHETIC-LOCAL-TEST-{uuid.uuid4().hex}"
    credentials = {}
    user_ids = {}
    monkeypatch.setattr(
        document_service,
        "BASE_DOCUMENTS_DIR",
        tmp_path / "application-documents",
    )

    try:
        with TestClient(app) as client:
            credentials = {
                "student": {
                    "username": f"test-student-{uuid.uuid4().hex}",
                    "password": "synthetic-student-password",
                    "role": "STUDENT",
                    "subject": marker,
                },
                "official": {
                    "username": f"test-official-{uuid.uuid4().hex}",
                    "password": "synthetic-official-password",
                    "role": "OFFICIAL",
                    "subject": f"OFFICIAL-{uuid.uuid4().hex}",
                },
                "dugc": {
                    "username": f"test-dugc-{uuid.uuid4().hex}",
                    "password": "synthetic-dugc-password",
                    "role": "DUGC",
                    "subject": f"DUGC-{uuid.uuid4().hex}",
                },
                "other_student": {
                    "username": f"test-other-student-{uuid.uuid4().hex}",
                    "password": "synthetic-other-student-password",
                    "role": "STUDENT",
                    "subject": f"OTHER-STUDENT-{uuid.uuid4().hex}",
                },
                "other_dugc": {
                    "username": f"test-other-dugc-{uuid.uuid4().hex}",
                    "password": "synthetic-other-dugc-password",
                    "role": "DUGC",
                    "subject": f"OTHER-DUGC-{uuid.uuid4().hex}",
                },
            }
            with get_connection() as connection:
                with connection.cursor() as cursor:
                    for name, account in credentials.items():
                        cursor.execute(
                            """
                            INSERT INTO auth_users (
                                username, password_hash, role, subject_identifier
                            )
                            VALUES (%s, %s, %s, %s)
                            RETURNING id;
                            """,
                            (
                                account["username"],
                                hash_password(account["password"]),
                                account["role"],
                                account["subject"],
                            ),
                        )
                        user_ids[name] = cursor.fetchone()[0]
                    cursor.execute(
                        """
                        INSERT INTO committee_memberships (user_id, committee_type)
                        VALUES (%s, 'DUGC');
                        """,
                        (user_ids["dugc"],),
                    )
                    cursor.execute(
                        """
                        INSERT INTO committee_memberships (user_id, committee_type)
                        VALUES (%s, 'DMPC');
                        """,
                        (user_ids["other_dugc"],),
                    )

            tokens = {}
            bad_login = client.post(
                "/auth/login",
                json={
                    "username": credentials["student"]["username"],
                    "password": "wrong-password",
                },
            )
            assert bad_login.status_code == 401
            for name, account in credentials.items():
                login = client.post(
                    "/auth/login",
                    json={
                        "username": account["username"],
                        "password": account["password"],
                    },
                )
                assert login.status_code == 200, login.text
                assert login.json()["user"]["role"] == account["role"]
                tokens[name] = {
                    "Authorization": f"Bearer {login.json()['access_token']}"
                }
            assert client.get(
                "/auth/me",
                headers=tokens["student"],
            ).json()["role"] == "STUDENT"
            assert client.get(
                "/applications",
                headers=tokens["other_student"],
            ).json()["items"] == []

            assert client.get("/applications").status_code == 401
            created = client.post(
                "/applications",
                json={
                    "application_type": "LOCAL_INTEGRATION_TEST",
                    "title": "Synthetic local integration record",
                    "description": "No institutional student data.",
                    "applicant_identifier": "ATTEMPTED-IDENTITY-SPOOF",
                },
                headers=tokens["student"],
            )
            assert created.status_code == 200, created.text
            application = created.json()
            application_id = application["id"]
            assert application["status"] == "DRAFT"
            assert application["application_number"].startswith("APP-")
            student_list = client.get(
                "/applications",
                headers=tokens["student"],
            )
            assert student_list.status_code == 200
            assert any(
                item["id"] == application_id
                for item in student_list.json()["items"]
            )

            official_queue = client.get(
                "/official/applications/unassigned",
                headers=tokens["official"],
            )
            assert official_queue.status_code == 200
            assert official_queue.json()["items"] == []
            assert client.get(
                "/official/applications/unassigned",
                headers=tokens["dugc"],
            ).status_code == 403
            assert client.get(
                f"/applications/{application_id}",
                headers=tokens["official"],
            ).status_code == 404

            submitted = client.post(
                f"/applications/{application_id}/submit",
                headers=tokens["student"],
            )
            assert submitted.status_code == 200, submitted.text
            assert submitted.json()["new_status"] == "SUBMITTED"
            assert client.post(
                f"/applications/{application_id}/submit",
                headers=tokens["student"],
            ).status_code == 409
            assert client.post(
                f"/applications/{application_id}/submit",
                headers=tokens["other_student"],
            ).status_code == 404
            assert client.post(
                f"/applications/{application_id}/claim",
                headers=tokens["other_student"],
            ).status_code == 403

            official_queue = client.get(
                "/official/applications/unassigned",
                headers=tokens["official"],
            )
            assert official_queue.status_code == 200
            assert any(
                item["id"] == application_id
                and item["status"] == "SUBMITTED"
                for item in official_queue.json()["items"]
            )
            claimed = client.post(
                f"/applications/{application_id}/claim",
                headers=tokens["official"],
            )
            assert claimed.status_code == 200, claimed.text
            assert claimed.json()["application_id"] == application_id
            assert client.post(
                f"/applications/{application_id}/claim",
                headers=tokens["official"],
            ).status_code == 409

            retrieved = client.get(
                f"/applications/{application_id}",
                headers=tokens["student"],
            )
            assert retrieved.status_code == 200
            assert retrieved.json()["applicant_identifier"] == marker
            assert retrieved.json()["status"] == "SUBMITTED"
            assert client.get(
                f"/applications/{application_id}",
                headers=tokens["other_student"],
            ).status_code == 404
            assert client.get(
                f"/applications/{application_id}",
                headers=tokens["other_dugc"],
            ).status_code == 404
            assert client.patch(
                f"/applications/{application_id}/status",
                json={"new_status": "SUBMITTED"},
                headers=tokens["student"],
            ).status_code == 403
            assert client.get(
                f"/applications/{application_id}",
                headers=tokens["official"],
            ).status_code == 200
            assert client.get(
                "/applications",
                headers=tokens["official"],
            ).json()["items"][0]["id"] == application_id

            ordinance = client.get(
                f"/applications/{application_id}/ordinance-retrieval",
                headers=tokens["student"],
            )
            assert ordinance.status_code == 200, ordinance.text
            assert ordinance.json()["results"] == []

            with get_connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO application_requirements (
                            application_id, requirement_description,
                            requirement_type
                        )
                        VALUES (%s, %s, %s);
                        """,
                        (
                            application_id,
                            "Synthetic requirement for isolated analysis tests.",
                            "SYNTHETIC_TEST",
                        ),
                    )

            import backend.services.eligibility_engine as eligibility_engine
            import backend.services.ai_analysis_service as ai_analysis_service

            monkeypatch.setattr(
                eligibility_engine,
                "generate_answer",
                lambda _question, _context: (
                    "RESULT: NOT_MET\n"
                    "CONFIDENCE: 0.9\n"
                    "EVIDENCE: Synthetic test evidence is insufficient."
                ),
            )
            eligibility = client.get(
                f"/applications/{application_id}/eligibility",
                headers=tokens["student"],
            )
            assert eligibility.status_code == 200, eligibility.text
            assert eligibility.json()["requirements_analyzed"] == 1
            assert eligibility.json()["results"][0]["result"] == "NOT_MET"

            deficiencies = client.get(
                f"/applications/{application_id}/deficiencies",
                headers=tokens["student"],
            )
            assert deficiencies.status_code == 200, deficiencies.text
            assert deficiencies.json()["deficiencies_detected"] == 1
            assert deficiencies.json()["deficiencies"][0]["severity"] == "HIGH"

            monkeypatch.setattr(
                ai_analysis_service,
                "generate_answer",
                lambda _question, _context: (
                    "Synthetic advisory analysis; not an official decision."
                ),
            )
            monkeypatch.setattr(
                ai_analysis_service,
                "semantic_search",
                lambda _query: [],
                raising=False,
            )
            ai_analysis = client.post(
                f"/applications/{application_id}/ai-analysis",
                headers=tokens["student"],
            )
            assert ai_analysis.status_code == 200, ai_analysis.text
            assert ai_analysis.json()["application_id"] == application_id
            assert ai_analysis.json()["requirements_analyzed"] == 1
            assert "Synthetic advisory analysis" in ai_analysis.json()["analysis"]

            history = client.get(
                f"/applications/{application_id}/status-history",
                headers=tokens["student"],
            )
            assert history.status_code == 200
            assert [item["new_status"] for item in history.json()["history"]] == [
                "DRAFT",
                "SUBMITTED",
            ]

            assert client.post(
                f"/applications/{application_id}/documents",
                files={"file": ("", b"empty name", "application/pdf")},
                headers=tokens["student"],
            ).status_code == 422
            oversized_document = client.post(
                f"/applications/{application_id}/documents",
                files={
                    "file": (
                        "oversized.pdf",
                        b"x" * (10 * 1024 * 1024 + 1),
                        "application/pdf",
                    )
                },
                headers=tokens["student"],
            )
            assert oversized_document.status_code == 413
            assert client.post(
                f"/applications/{application_id}/documents",
                files={"file": ("official.pdf", b"not allowed", "application/pdf")},
                headers=tokens["official"],
            ).status_code == 403

            uploaded = client.post(
                f"/applications/{application_id}/documents",
                files={"file": ("synthetic-evidence.pdf", b"%PDF-1.4\nsynthetic\n")},
                data={"document_type": "SYNTHETIC_TEST"},
                headers=tokens["student"],
            )
            assert uploaded.status_code == 200, uploaded.text
            document = uploaded.json()
            assert document["application_id"] == application_id
            assert document["file_name"] == "synthetic-evidence.pdf"
            assert document["file_size"] == len(b"%PDF-1.4\nsynthetic\n")
            assert "file_path" not in document

            downloaded = client.get(
                f"/applications/{application_id}/documents/{document['id']}/download",
                headers=tokens["student"],
            )
            assert downloaded.status_code == 200
            assert downloaded.content == b"%PDF-1.4\nsynthetic\n"

            documents = client.get(
                f"/applications/{application_id}/documents",
                headers=tokens["student"],
            )
            assert documents.status_code == 200
            assert documents.json()["documents"][0]["id"] == document["id"]
            assert "file_path" not in documents.json()["documents"][0]
            assert client.get(
                f"/applications/{application_id}/documents/{document['id']}/download",
                headers=tokens["other_student"],
            ).status_code == 404

            for status in (
                "DOCUMENT_VALIDATION",
                "PROCESSING",
                "UNDER_REVIEW",
                "COMMITTEE_REVIEW",
            ):
                changed = client.patch(
                    f"/applications/{application_id}/status",
                    json={
                        "new_status": status,
                        "reason": "Isolated local integration test.",
                    },
                    headers=tokens["official"],
                )
                assert changed.status_code == 200, changed.text
                assert changed.json()["new_status"] == status

            assigned = client.post(
                f"/applications/{application_id}/committee",
                json={"committee_type": "DUGC"},
                headers=tokens["official"],
            )
            assert assigned.status_code == 200, assigned.text
            review_id = assigned.json()["id"]
            assert assigned.json()["review_status"] == "PENDING"

            dugc_queue = client.get(
                "/applications",
                headers=tokens["dugc"],
            )
            assert dugc_queue.status_code == 200
            assert any(
                item["id"] == application_id
                for item in dugc_queue.json()["items"]
            )
            reviews = client.get(
                f"/applications/{application_id}/committee-reviews",
                headers=tokens["dugc"],
            )
            assert reviews.status_code == 200
            assert reviews.json()["reviews"][0]["id"] == review_id
            assert client.get(
                f"/applications/{application_id}/committee-reviews",
                headers=tokens["other_dugc"],
            ).status_code == 404
            assert client.patch(
                f"/committee-reviews/{review_id}/decision",
                json={
                    "decision": "APPROVED",
                    "decision_reason": "Unauthorized synthetic reviewer.",
                },
                headers=tokens["other_dugc"],
            ).status_code == 404

            decision = client.patch(
                f"/committee-reviews/{review_id}/decision",
                json={
                    "decision": "APPROVED",
                    "decision_reason": "Synthetic test review complete.",
                },
                headers=tokens["dugc"],
            )
            assert decision.status_code == 200, decision.text
            assert decision.json()["application_status"] == "APPROVED"
            assert decision.json()["review"]["review_status"] == "COMPLETED"
            student_reviews = client.get(
                f"/applications/{application_id}/committee-reviews",
                headers=tokens["student"],
            ).json()["reviews"]
            assert "decided_by" not in student_reviews[0]
            student_history = client.get(
                f"/applications/{application_id}/status-history",
                headers=tokens["student"],
            ).json()["history"]
            assert all("changed_by" not in item for item in student_history)
            assert client.get(
                f"/applications/{application_id}/audit-logs",
                headers=tokens["official"],
            ).status_code == 403

            final_application = client.get(
                f"/applications/{application_id}",
                headers=tokens["student"],
            )
            assert final_application.status_code == 200
            assert final_application.json()["status"] == "APPROVED"

            final_history = client.get(
                f"/applications/{application_id}/status-history",
                headers=tokens["student"],
            )
            assert final_history.status_code == 200
            assert final_history.json()["history"][-1]["new_status"] == "APPROVED"
            logout = client.post("/auth/logout", headers=tokens["student"])
            assert logout.status_code == 204
            assert client.get(
                "/auth/me",
                headers=tokens["student"],
            ).status_code == 401
    finally:
        settings = get_database_settings()
        if (
            settings.environment != "test"
            or settings.database != "departmentai_test"
            or not ipaddress.ip_address(settings.host).is_loopback
        ):
            raise RuntimeError(
                "Refusing integration-test cleanup outside the isolated test DB."
            )
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM applications WHERE applicant_identifier = %s",
                    (marker,),
                )
                cursor.execute(
                    "DELETE FROM auth_users WHERE username = ANY(%s)",
                    ([account["username"] for account in credentials.values()],),
                )
        for path in (tmp_path / "application-documents").glob("*"):
            if path.is_dir():
                for child in path.iterdir():
                    child.unlink()
                path.rmdir()
            else:
                path.unlink()

import ipaddress
import json
import os
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api import routes as api_routes
from backend.api.auth_routes import get_programme_identity_provider
from backend.database.connection import get_connection, get_database_settings
from backend.main import app
from backend.services import document_service
from backend.services.auth_service import hash_password
from backend.services import application_readiness_service
from backend.services.application_policy_registry import DEFAULT_POLICY_REGISTRY
from backend.services.programme_identity import ProgrammeIdentity


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
    "governance_meetings",
    "meeting_member_availability",
    "meeting_confirmations",
    "meeting_application_links",
    "meeting_records",
    "meeting_minutes_versions",
    "meeting_minutes_comments",
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


@pytest.fixture
def synthetic_readiness_environment(tmp_path, monkeypatch):
    _assert_isolated_test_database()
    registry = json.loads(
        DEFAULT_POLICY_REGISTRY.read_text(encoding="utf-8")
    )
    ug_source = next(
        source
        for source in registry["sources"]
        if source["source_id"] == "UG_ORDINANCE_2023"
    )
    registry["registry_version"] = "synthetic-test-only-v1"
    registry["application_types"] = [
        {
            "application_type_id": "SYNTHETIC_UG_NO_DOCUMENTS",
            "display_title": "Synthetic no-document test request",
            "programme": "UG",
            "approval_status": "APPROVED",
            "activation_scope": "TEST_ONLY",
            "approval_evidence": "Synthetic test-only configuration.",
            "source_ids": ["UG_ORDINANCE_2023"],
            "required_documents": [],
            "eligibility_rules": [],
            "processing_capabilities": ["pdf_text"],
        }
    ]
    registry_path = tmp_path / "synthetic-application-policies.json"
    registry_path.write_text(json.dumps(registry), encoding="utf-8")
    monkeypatch.setenv(
        "DEPARTMENTAI_APPLICATION_POLICY_CONFIG",
        str(registry_path),
    )

    class SyntheticTestIdentityProvider:
        def resolve(self, subject_identifier):
            return ProgrammeIdentity(
                status="VERIFIED",
                programme="UG",
                subject_identifier=subject_identifier,
                source_id="synthetic-test-student-record",
                source_version="synthetic-test-v1",
            )

    provider = SyntheticTestIdentityProvider()
    monkeypatch.setitem(
        app.dependency_overrides,
        get_programme_identity_provider,
        lambda: provider,
    )

    chunk_asset = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "documents"
            / "ug"
            / "processed"
            / "ug_ordinance_chunks.json"
        ).read_text(encoding="utf-8")
    )["chunks"][0]
    embedding_asset = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "documents"
            / "ug"
            / "processed"
            / "ug_ordinance_embeddings.json"
        ).read_text(encoding="utf-8")
    )["chunks"][0]
    assert chunk_asset["chunk_id"] == embedding_asset["chunk_id"]
    inserted_document = inserted_section = inserted_chunk = None
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id
                FROM knowledge_chunks
                WHERE metadata->>'chunk_id' = %s
                  AND metadata->>'source_file' = %s
                LIMIT 1;
                """,
                (chunk_asset["chunk_id"], chunk_asset["source_file"]),
            )
            existing_chunk = cursor.fetchone()
            if existing_chunk is None:
                cursor.execute(
                    """
                    SELECT id FROM documents WHERE file_name = %s;
                    """,
                    (chunk_asset["source_file"],),
                )
                document = cursor.fetchone()
                if document is None:
                    cursor.execute(
                        """
                        INSERT INTO documents (file_name)
                        VALUES (%s)
                        RETURNING id;
                        """,
                        (chunk_asset["source_file"],),
                    )
                    document_id = cursor.fetchone()[0]
                    inserted_document = document_id
                else:
                    document_id = document[0]
                cursor.execute(
                    """
                    SELECT id
                    FROM sections
                    WHERE document_id = %s
                      AND section_number = %s
                      AND title = %s
                    LIMIT 1;
                    """,
                    (
                        document_id,
                        chunk_asset["section"],
                        chunk_asset["section_title"],
                    ),
                )
                section = cursor.fetchone()
                if section is None:
                    cursor.execute(
                        """
                        INSERT INTO sections (
                            document_id, section_number, title
                        )
                        VALUES (%s, %s, %s)
                        RETURNING id;
                        """,
                        (
                            document_id,
                            chunk_asset["section"],
                            chunk_asset["section_title"],
                        ),
                    )
                    section_id = cursor.fetchone()[0]
                    inserted_section = section_id
                else:
                    section_id = section[0]
                vector = "[" + ",".join(
                    str(float(value))
                    for value in embedding_asset["embedding"]
                ) + "]"
                cursor.execute(
                    """
                    INSERT INTO knowledge_chunks (
                        document_id, section_id, chunk_index, chunk_type,
                        clause_number, chunk_text, page_start, page_end,
                        metadata, embedding
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector)
                    RETURNING id;
                    """,
                    (
                        document_id,
                        section_id,
                        chunk_asset["chunk_index"],
                        chunk_asset["content_type"],
                        chunk_asset["clause"],
                        chunk_asset["text"],
                        chunk_asset["page_start"],
                        chunk_asset["page_end"],
                        json.dumps(
                            {
                                "chunk_id": chunk_asset["chunk_id"],
                                "source_file": chunk_asset["source_file"],
                                "source_id": ug_source["source_id"],
                                "source_version": ug_source["source_version"],
                                "source_sha256": ug_source["source_sha256"],
                                "approval_status": "APPROVED",
                                "programme": "UG",
                                "source_type": "ORDINANCE",
                                "embedding_model": (
                                    "sentence-transformers/"
                                    "paraphrase-multilingual-MiniLM-L12-v2"
                                ),
                                "embedding_dimension": 384,
                                "source_file": chunk_asset["source_file"],
                                "clause_title": chunk_asset["clause_title"],
                            }
                        ),
                        vector,
                    ),
                )
                inserted_chunk = cursor.fetchone()[0]

    yield {
        "provider": provider,
        "ug_source": ug_source,
        "chunk_asset": chunk_asset,
    }

    with get_connection() as connection:
        with connection.cursor() as cursor:
            if inserted_chunk is not None:
                cursor.execute(
                    "DELETE FROM knowledge_chunks WHERE id = %s;",
                    (inserted_chunk,),
                )
            if inserted_section is not None:
                cursor.execute(
                    """
                    DELETE FROM sections
                    WHERE id = %s
                      AND NOT EXISTS (
                          SELECT 1 FROM knowledge_chunks
                          WHERE section_id = %s
                      );
                    """,
                    (inserted_section, inserted_section),
                )
            if inserted_document is not None:
                cursor.execute(
                    """
                    DELETE FROM documents
                    WHERE id = %s
                      AND NOT EXISTS (
                          SELECT 1 FROM sections WHERE document_id = %s
                      )
                      AND NOT EXISTS (
                          SELECT 1 FROM knowledge_chunks WHERE document_id = %s
                      );
                    """,
                    (
                        inserted_document,
                        inserted_document,
                        inserted_document,
                    ),
                )


@pytest.fixture
def isolated_committee_memberships():
    _assert_isolated_test_database()
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT user_id, committee_type, assigned_at
                FROM committee_memberships;
                """
            )
            previous_memberships = cursor.fetchall()
            cursor.execute("DELETE FROM committee_memberships;")

    try:
        yield
    finally:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                for user_id, committee_type, assigned_at in previous_memberships:
                    cursor.execute(
                        """
                        INSERT INTO committee_memberships (
                            user_id, committee_type, assigned_at
                        )
                        VALUES (%s, %s, %s)
                        ON CONFLICT (user_id, committee_type) DO NOTHING;
                        """,
                        (user_id, committee_type, assigned_at),
                    )


def test_local_student_official_dugc_database_workflow(
    tmp_path,
    monkeypatch,
    synthetic_readiness_environment,
    isolated_committee_memberships,
):
    _assert_isolated_test_database()
    ug_source = synthetic_readiness_environment["ug_source"]
    chunk_asset = synthetic_readiness_environment["chunk_asset"]
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
                "inactive_student": {
                    "username": f"test-inactive-student-{uuid.uuid4().hex}",
                    "password": "synthetic-inactive-student-password",
                    "role": "STUDENT",
                    "subject": f"INACTIVE-STUDENT-{uuid.uuid4().hex}",
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
                        UPDATE auth_users SET is_active = FALSE WHERE id = %s;
                        """,
                        (user_ids["inactive_student"],),
                    )
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
                if name == "inactive_student":
                    assert login.status_code == 401
                    continue
                assert login.status_code == 200, login.text
                assert login.json()["user"]["role"] == account["role"]
                if account["role"] == "STUDENT":
                    assert login.json()["user"]["programme_identity_status"] == (
                        "VERIFIED"
                    )
                    assert login.json()["user"]["verified_programme"] == "UG"
                tokens[name] = {
                    "Authorization": f"Bearer {login.json()['access_token']}"
                }
            monkeypatch.setattr(
                api_routes,
                "answer_question",
                lambda _question, _history, programme: (
                    f"Scoped to {programme}.",
                    [
                        {
                            "source_file": {
                                "UG": "UG Ordinance.pdf",
                                "MTECH": "Ordinances for Masters Programme 2023.pdf",
                                "PHD": "Ordinances_for_Doctoral_Programm2023.pdf",
                            }[programme],
                            "section_number": "1",
                            "page_start": 1,
                        }
                    ],
                ),
            )
            programme_answer = client.post(
                "/ask",
                json={
                    "question": "What does the ordinance say about research?",
                    "programme": "MTECH",
                },
                headers=tokens["student"],
            )
            assert programme_answer.status_code == 200, programme_answer.text
            assert programme_answer.json()["answer"] == "Scoped to MTECH."
            assert programme_answer.json()["sources"][0]["source"] == (
                "Ordinances for Masters Programme 2023.pdf"
            )
            assert client.post(
                "/ask",
                json={
                    "question": "What are the PG Diploma rules?",
                    "programme": "PGD",
                },
                headers=tokens["student"],
            ).status_code == 422
            student_identity = client.get(
                "/auth/me",
                headers=tokens["student"],
            ).json()
            assert student_identity["role"] == "STUDENT"
            assert student_identity["programme_identity_status"] == (
                "VERIFIED"
            )
            assert student_identity["verified_programme"] == "UG"
            assert client.get(
                "/auth/me?programme=PHD",
                headers=tokens["student"],
            ).json()["verified_programme"] == "UG"
            assert client.patch(
                "/auth/me",
                json={"programme": "PHD"},
                headers=tokens["student"],
            ).status_code == 405
            official_identity = client.get(
                "/auth/me",
                headers=tokens["official"],
            ).json()
            assert official_identity["programme_identity_status"] is None
            assert official_identity["verified_programme"] is None
            assert client.get(
                "/applications",
                headers=tokens["other_student"],
            ).json()["items"] == []

            assert client.get("/applications").status_code == 401
            spoofed_create = client.post(
                "/applications",
                json={
                    "application_type": "LOCAL_INTEGRATION_TEST",
                    "title": "Synthetic local integration record",
                    "description": "No institutional student data.",
                    "applicant_identifier": "ATTEMPTED-IDENTITY-SPOOF",
                    "programme": "PHD",
                    "committee_type": "DDPC",
                },
                headers=tokens["student"],
            )
            assert spoofed_create.status_code == 422
            created = client.post(
                "/applications?programme=PHD&committee_type=DDPC",
                json={
                    "application_type": "LOCAL_INTEGRATION_TEST",
                    "title": "Synthetic local integration record",
                    "description": "No institutional student data.",
                },
                headers=tokens["student"],
            )
            assert created.status_code == 200, created.text
            application = created.json()
            application_id = application["id"]
            assert application["status"] == "DRAFT"
            assert application["application_number"].startswith("APP-")
            spoofed_edit = client.patch(
                f"/applications/{application_id}",
                json={
                    "application_type": "Spoofed programme",
                    "title": None,
                    "description": None,
                    "programme": "PHD",
                    "committee_type": "DDPC",
                },
                headers=tokens["student"],
            )
            assert spoofed_edit.status_code == 422
            blank_type = client.post(
                "/applications",
                json={"application_type": "   "},
                headers=tokens["student"],
            )
            assert blank_type.status_code == 400
            oversized_title = client.post(
                "/applications",
                json={
                    "application_type": "Valid synthetic request",
                    "title": "x" * 201,
                },
                headers=tokens["student"],
            )
            assert oversized_title.status_code == 422

            updated_draft = client.patch(
                f"/applications/{application_id}",
                json={
                    "application_type": "Updated synthetic request",
                    "title": None,
                    "description": "Revised synthetic details.",
                },
                headers=tokens["student"],
            )
            assert updated_draft.status_code == 200, updated_draft.text
            assert updated_draft.json()["status"] == "DRAFT"
            assert updated_draft.json()["application_type"] == (
                "Updated synthetic request"
            )
            assert updated_draft.json()["title"] is None
            assert updated_draft.json()["description"] == (
                "Revised synthetic details."
            )
            assert client.patch(
                f"/applications/{application_id}",
                json={
                    "application_type": "Unauthorized edit",
                    "title": None,
                    "description": None,
                },
                headers=tokens["other_student"],
            ).status_code == 404
            assert client.patch(
                f"/applications/{application_id}",
                json={
                    "application_type": "Unauthorized edit",
                    "title": None,
                    "description": None,
                },
                headers=tokens["official"],
            ).status_code == 403
            persisted_draft = client.get(
                f"/applications/{application_id}",
                headers=tokens["student"],
            )
            assert persisted_draft.status_code == 200
            assert persisted_draft.json()["applicant_identifier"] == marker
            assert persisted_draft.json()["status"] == "DRAFT"
            assert persisted_draft.json()["application_type"] == (
                "Updated synthetic request"
            )
            with get_connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT actor_type, actor_id, action
                        FROM audit_logs
                        WHERE application_id = %s
                          AND action = 'APPLICATION_UPDATED';
                        """,
                        (application_id,),
                    )
                    update_audit = cursor.fetchone()
            assert update_audit == (
                "STUDENT",
                credentials["student"]["username"],
                "APPLICATION_UPDATED",
            )
            oversized_edit = client.patch(
                f"/applications/{application_id}",
                json={
                    "application_type": "Valid synthetic request",
                    "title": None,
                    "description": "x" * 10001,
                },
                headers=tokens["student"],
            )
            assert oversized_edit.status_code == 422

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

            with get_connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE applications
                        SET application_type = '   '
                        WHERE id = %s;
                        """,
                        (application_id,),
                    )
            invalid_field_submission = client.post(
                f"/applications/{application_id}/submit",
                headers=tokens["student"],
            )
            assert invalid_field_submission.status_code == 400
            assert client.get(
                f"/applications/{application_id}",
                headers=tokens["student"],
            ).json()["status"] == "DRAFT"
            readiness_pending = client.get(
                f"/applications/{application_id}/readiness",
                headers=tokens["student"],
            )
            assert readiness_pending.status_code == 200
            assert readiness_pending.json()["readiness_status"] == (
                "ANALYSIS_PENDING"
            )
            unresolved = client.post(
                f"/applications/{application_id}/readiness/analyze",
                headers=tokens["student"],
            )
            assert unresolved.status_code == 200, unresolved.text
            assert unresolved.json()["readiness_status"] == "RULES_UNRESOLVED"
            assert unresolved.json()["required_documents"] is None
            assert unresolved.json()["deficiency_count"] is None
            repeated_unresolved = client.post(
                f"/applications/{application_id}/readiness/analyze",
                headers=tokens["student"],
            )
            assert repeated_unresolved.json()["analysis_id"] == (
                unresolved.json()["analysis_id"]
            )
            with get_connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE applications
                        SET application_type = %s
                        WHERE id = %s;
                        """,
                        ("Updated synthetic request", application_id),
                    )

            unresolved = client.post(
                f"/applications/{application_id}/readiness/analyze",
                headers=tokens["student"],
            )
            assert unresolved.json()["readiness_status"] == "RULES_UNRESOLVED"
            blocked_submission = client.post(
                f"/applications/{application_id}/submit",
                headers=tokens["student"],
            )
            assert blocked_submission.status_code == 409
            assert blocked_submission.json()["detail"]["code"] == (
                "RULES_UNRESOLVED"
            )

            uploaded = client.post(
                f"/applications/{application_id}/documents",
                files={
                    "file": (
                        "..\\synthetic-evidence.pdf",
                        b"%PDF-1.4\nsynthetic\n",
                    )
                },
                data={"document_type": "SYNTHETIC_TEST"},
                headers=tokens["student"],
            )
            assert uploaded.status_code == 200, uploaded.text
            document = uploaded.json()
            assert document["application_id"] == application_id
            assert document["file_name"] == "synthetic-evidence.pdf"
            assert document["file_size"] == len(b"%PDF-1.4\nsynthetic\n")
            assert "file_path" not in document
            duplicate_name_upload = client.post(
                f"/applications/{application_id}/documents",
                files={
                    "file": (
                        "synthetic-evidence.pdf",
                        b"%PDF-1.4\nsecond file\n",
                    )
                },
                headers=tokens["student"],
            )
            assert duplicate_name_upload.status_code == 200
            assert duplicate_name_upload.json()["file_name"] == (
                "synthetic-evidence.pdf"
            )
            versioned_upload = client.post(
                f"/applications/{application_id}/documents",
                files={
                    "file": (
                        "versioned-evidence.pdf",
                        b"%PDF-1.4\nversioned test file\n",
                    )
                },
                headers=tokens["student"],
            )
            assert versioned_upload.status_code == 200
            document_application_id = application_id

            stale_readiness = client.get(
                f"/applications/{application_id}/readiness",
                headers=tokens["student"],
            )
            assert stale_readiness.status_code == 200
            assert stale_readiness.json()["is_stale"] is True
            invalid_document_analysis = client.post(
                f"/applications/{application_id}/readiness/analyze",
                headers=tokens["student"],
            )
            assert invalid_document_analysis.status_code == 200
            assert invalid_document_analysis.json()["readiness_status"] == (
                "ANALYSIS_UNAVAILABLE"
            )
            assert invalid_document_analysis.json()["required_documents"] is None
            assert invalid_document_analysis.json()["deficiency_count"] is None
            blocked_submission = client.post(
                f"/applications/{application_id}/submit",
                headers=tokens["student"],
            )
            assert blocked_submission.status_code == 409
            assert blocked_submission.json()["detail"]["code"] == (
                "ANALYSIS_UNAVAILABLE"
            )
            with get_connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT file_path
                        FROM application_documents
                        WHERE id = %s;
                        """,
                        (versioned_upload.json()["id"],),
                    )
                    document_path = Path(cursor.fetchone()[0])
            document_path.write_bytes(
                document_path.read_bytes() + b"\nchanged after analysis"
            )
            stale_after_file_change = client.get(
                f"/applications/{application_id}/readiness",
                headers=tokens["student"],
            )
            assert stale_after_file_change.json()["is_stale"] is True
            blocked_submission = client.post(
                f"/applications/{application_id}/submit",
                headers=tokens["student"],
            )
            assert blocked_submission.status_code == 409
            assert blocked_submission.json()["detail"]["code"] == (
                "ANALYSIS_PENDING"
            )
            ready_application = client.post(
                "/applications",
                json={
                    "application_type": "SYNTHETIC_UG_NO_DOCUMENTS",
                    "title": "Synthetic test-only readiness workflow",
                },
                headers=tokens["student"],
            )
            assert ready_application.status_code == 200, ready_application.text
            application_id = ready_application.json()["id"]
            readiness = client.post(
                f"/applications/{application_id}/readiness/analyze",
                headers=tokens["student"],
            )
            assert readiness.status_code == 200, readiness.text
            assert readiness.json()["readiness_status"] == "READY"
            assert readiness.json()["deficiencies"] == []
            assert readiness.json()["deficiency_count"] == 0
            assert readiness.json()["programme_identity"]["status"] == (
                "VERIFIED"
            )
            assert readiness.json()["policy"]["status"] == "RESOLVED"
            assert readiness.json()["policy"]["activation_scope"] == "TEST_ONLY"
            assert client.get("/knowledge/sources").status_code == 401
            assert client.post(
                "/ask",
                json={"question": "Synthetic authentication check"},
            ).status_code == 401
            source_inventory = client.get(
                "/knowledge/sources",
                headers=tokens["student"],
            )
            assert source_inventory.status_code == 200, source_inventory.text
            ug_inventory = next(
                source
                for source in source_inventory.json()["sources"]
                if source["source_id"] == "UG_ORDINANCE_2023"
            )
            assert ug_inventory["expected_chunk_count"] == 246
            assert ug_inventory["chunk_count"] > 0
            assert ug_inventory["status"] in {
                "INDEXED",
                "STALE_OR_UNVERIFIED",
            }
            chunk_query = chunk_asset["text"][:2000]
            assert client.post(
                "/knowledge/search",
                json={"query": chunk_query, "programme": "UG"},
            ).status_code == 401
            knowledge_search = client.post(
                "/knowledge/search",
                json={
                    "query": chunk_query,
                    "application_id": application_id,
                },
                headers=tokens["student"],
            )
            assert knowledge_search.status_code == 200, knowledge_search.text
            assert knowledge_search.json()["status"] == "COMPLETED"
            verified_result = next(
                result
                for result in knowledge_search.json()["results"]
                if result["source_id"] == "UG_ORDINANCE_2023"
            )
            assert verified_result["source_metadata_status"] == "VERIFIED"
            assert verified_result["applicability"] == "POLICY_SCOPED"
            assert verified_result["chunk_id"] == chunk_asset["chunk_id"]
            assert str(verified_result["section_number"]) == str(
                chunk_asset["section"]
            )
            assert verified_result["source_version"] == (
                ug_source["source_version"]
            )
            assert verified_result["source_sha256"] == (
                ug_source["source_sha256"]
            )
            assert client.post(
                "/knowledge/search",
                json={
                    "query": chunk_query,
                    "application_id": application_id,
                    "programme": "PHD",
                },
                headers=tokens["student"],
            ).status_code == 409
            assert client.post(
                "/knowledge/search",
                json={
                    "query": chunk_query,
                    "application_id": application_id,
                },
                headers=tokens["other_student"],
            ).status_code == 404
            analysis_id = readiness.json()["analysis_id"]
            with get_connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT COUNT(*)
                        FROM ai_analyses
                        WHERE application_id = %s
                          AND analysis_type = 'APPLICATION_READINESS';
                        """,
                        (application_id,),
                    )
                    analysis_count_before_read = cursor.fetchone()[0]
            analysis = client.get(
                f"/applications/{application_id}/analysis",
                headers=tokens["student"],
            )
            assert analysis.status_code == 200, analysis.text
            assert analysis.json()["formal_decision"] is False
            assert analysis.json()["freshness_status"] == "CURRENT"
            assert analysis.json()["readiness"]["analysis_id"] == analysis_id
            assert analysis.json()["eligibility_freshness"] == "NOT_TRACKED"
            with get_connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT COUNT(*)
                        FROM ai_analyses
                        WHERE application_id = %s
                          AND analysis_type = 'APPLICATION_READINESS';
                        """,
                        (application_id,),
                    )
                    assert cursor.fetchone()[0] == analysis_count_before_read
            assert client.get(
                f"/applications/{application_id}/analysis",
                headers=tokens["other_student"],
            ).status_code == 404
            submitted = client.post(
                f"/applications/{application_id}/submit",
                headers=tokens["student"],
            )
            assert submitted.status_code == 200, submitted.text
            assert submitted.json()["new_status"] == "SUBMITTED"
            late_upload = client.post(
                f"/applications/{application_id}/documents",
                files={
                    "file": (
                        "late-evidence.pdf",
                        b"%PDF-1.4\nlate upload\n",
                    )
                },
                headers=tokens["student"],
            )
            assert late_upload.status_code == 409, late_upload.text
            assert client.patch(
                f"/applications/{application_id}",
                json={
                    "application_type": "Post-submission edit",
                    "title": None,
                    "description": None,
                },
                headers=tokens["student"],
            ).status_code == 409
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
            legacy_processing = client.post(
                f"/applications/{application_id}/process",
                headers=tokens["official"],
            )
            assert legacy_processing.status_code == 409
            assert legacy_processing.json()["detail"]["code"] == (
                "UNIFIED_PROCESSING_NOT_AVAILABLE"
            )

            retrieved = client.get(
                f"/applications/{application_id}",
                headers=tokens["student"],
            )
            assert retrieved.status_code == 200
            assert retrieved.json()["applicant_identifier"] == marker
            assert retrieved.json()["status"] == "SUBMITTED"
            cross_student_details = client.get(
                f"/applications/{application_id}",
                headers=tokens["other_student"],
            )
            assert cross_student_details.status_code == 404, (
                cross_student_details.text
            )
            assert client.get(
                f"/applications/{application_id}",
                headers=tokens["other_dugc"],
            ).status_code == 404
            assert client.patch(
                f"/applications/{application_id}/status",
                json={"new_status": "SUBMITTED"},
                headers=tokens["student"],
            ).status_code == 403
            assert client.patch(
                f"/applications/{application_id}/status",
                json={"new_status": "APPROVED"},
                headers=tokens["official"],
            ).status_code == 400
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
            assert ordinance.json()["policy_source_ids"] == [
                "UG_ORDINANCE_2023"
            ]
            assert all(
                result["source_file"] == "UG Ordinance.pdf"
                for result in ordinance.json()["results"]
            )

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

            saved_eligibility = client.get(
                f"/applications/{application_id}/eligibility/results",
                headers=tokens["official"],
            )
            assert saved_eligibility.status_code == 200
            assert saved_eligibility.json()["analysis_status"] == (
                "NOT_GENERATED"
            )
            assert saved_eligibility.json()["results"] == []
            assert client.get(
                f"/applications/{application_id}/eligibility/results",
                headers=tokens["other_student"],
            ).status_code == 404

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
            saved_eligibility = client.get(
                f"/applications/{application_id}/eligibility/results",
                headers=tokens["official"],
            )
            assert saved_eligibility.status_code == 200
            assert saved_eligibility.json()["analysis_status"] == "AVAILABLE"
            assert saved_eligibility.json()["advisory"] is True
            assert saved_eligibility.json()["results"][0]["result"] == "NOT_MET"

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

            downloaded = client.get(
                f"/applications/{document_application_id}/documents/"
                f"{document['id']}/download",
                headers=tokens["student"],
            )
            assert downloaded.status_code == 200
            assert downloaded.content == b"%PDF-1.4\nsynthetic\n"

            documents = client.get(
                f"/applications/{document_application_id}/documents",
                headers=tokens["student"],
            )
            assert documents.status_code == 200
            assert len(documents.json()["documents"]) == 3
            assert any(
                item["id"] == document["id"]
                for item in documents.json()["documents"]
            )
            assert "file_path" not in documents.json()["documents"][0]
            duplicate_name_download = client.get(
                f"/applications/{document_application_id}/documents/"
                f"{duplicate_name_upload.json()['id']}/download",
                headers=tokens["student"],
            )
            assert duplicate_name_download.content == b"%PDF-1.4\nsecond file\n"
            assert downloaded.content == b"%PDF-1.4\nsynthetic\n"
            assert client.get(
                f"/applications/{document_application_id}/documents/"
                f"{document['id']}/download",
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

            unavailable_committee = client.post(
                f"/applications/{application_id}/committee",
                json={"committee_type": "DDPC"},
                headers=tokens["official"],
            )
            assert unavailable_committee.status_code == 400
            assert "No members are configured" in (
                unavailable_committee.json()["detail"]
            )
            assert client.post(
                f"/applications/{application_id}/committee",
                json={"committee_type": "DUGC"},
                headers=tokens["student"],
            ).status_code == 403
            spoofed_committee = client.post(
                f"/applications/{application_id}/committee",
                json={"committee_type": "DUGC", "committee_id": 123},
                headers=tokens["official"],
            )
            assert spoofed_committee.status_code == 422
            assigned = client.post(
                f"/applications/{application_id}/committee",
                json={"committee_type": "DUGC"},
                headers=tokens["official"],
            )
            assert assigned.status_code == 200, assigned.text
            review_id = assigned.json()["id"]
            assert assigned.json()["review_status"] == "PENDING"
            with get_connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT actor_type, actor_id, action, details
                        FROM audit_logs
                        WHERE application_id = %s
                          AND action = 'COMMITTEE_ASSIGNED';
                        """,
                        (application_id,),
                    )
                    assignment_audit = cursor.fetchone()
            assert assignment_audit[:3] == (
                "OFFICIAL",
                credentials["official"]["username"],
                "COMMITTEE_ASSIGNED",
            )
            assert assignment_audit[3]["committee_type"] == "DUGC"

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
            assert client.get(
                f"/applications/{application_id}",
                headers=tokens["other_dugc"],
            ).status_code == 404
            assert client.get(
                f"/applications/{application_id}/documents",
                headers=tokens["other_dugc"],
            ).status_code == 404
            assert client.get(
                f"/applications/{application_id}/documents/"
                f"{document['id']}/download",
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
            with get_connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT actor_type, actor_id, details
                        FROM audit_logs
                        WHERE application_id = %s
                          AND action = 'COMMITTEE_DECISION_RECORDED';
                        """,
                        (application_id,),
                    )
                    decision_audit = cursor.fetchone()
            assert decision_audit[:2] == (
                "COMMITTEE",
                credentials["dugc"]["username"],
            )
            assert decision_audit[2]["review_id"] == review_id
            assert decision_audit[2]["decision"] == "APPROVED"
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


def test_student_document_upload_is_draft_only(
    tmp_path,
    monkeypatch,
    synthetic_readiness_environment,
):
    _assert_isolated_test_database()
    marker = f"SYNTHETIC-DRAFT-UPLOAD-{uuid.uuid4().hex}"
    username = f"draft-upload-{uuid.uuid4().hex}"
    password = "synthetic-draft-upload-password"
    monkeypatch.setattr(
        document_service,
        "BASE_DOCUMENTS_DIR",
        tmp_path / "application-documents",
    )

    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO auth_users (
                        username, password_hash, role, subject_identifier
                    )
                    VALUES (%s, %s, 'STUDENT', %s);
                    """,
                    (username, hash_password(password), marker),
                )

        with TestClient(app) as client:
            login = client.post(
                "/auth/login",
                json={"username": username, "password": password},
            )
            assert login.status_code == 200, login.text
            token = {
                "Authorization": f"Bearer {login.json()['access_token']}"
            }
            created = client.post(
                "/applications",
                json={
                    "application_type": "SYNTHETIC_UG_NO_DOCUMENTS",
                    "title": "Synthetic upload lifecycle policy test",
                },
                headers=token,
            )
            assert created.status_code == 200, created.text
            application_id = created.json()["id"]

            readiness = client.post(
                f"/applications/{application_id}/readiness/analyze",
                headers=token,
            )
            assert readiness.status_code == 200, readiness.text
            assert readiness.json()["readiness_status"] == "READY"
            submitted = client.post(
                f"/applications/{application_id}/submit",
                headers=token,
            )
            assert submitted.status_code == 200, submitted.text

            rejected_upload = client.post(
                f"/applications/{application_id}/documents",
                files={
                    "file": (
                        "late-upload.pdf",
                        b"%PDF-1.4\nnot accepted after submission",
                        "application/pdf",
                    )
                },
                headers=token,
            )
            assert rejected_upload.status_code == 409
            assert "only be uploaded while" in rejected_upload.json()["detail"]

            documents = client.get(
                f"/applications/{application_id}/documents",
                headers=token,
            )
            assert documents.status_code == 200
            assert documents.json()["documents"] == []
    finally:
        _assert_isolated_test_database()
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM applications WHERE applicant_identifier = %s",
                    (marker,),
                )
                cursor.execute(
                    "DELETE FROM auth_users WHERE username = %s",
                    (username,),
                )
        storage_directory = tmp_path / "application-documents"
        if storage_directory.exists():
            for application_directory in storage_directory.iterdir():
                if application_directory.is_dir():
                    for stored_file in application_directory.iterdir():
                        stored_file.unlink()
                    application_directory.rmdir()
            storage_directory.rmdir()

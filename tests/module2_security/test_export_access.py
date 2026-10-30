import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.api import auth_routes
from backend.main import app
from backend.services.auth_service import AuthenticatedUser
from module2.database import connection as module2_connection


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.query = None
        self.parameters = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, parameters=None):
        self.query = query
        self.parameters = parameters

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, cursor):
        self.fake_cursor = cursor
        self.closed = False

    def cursor(self):
        return self.fake_cursor

    def close(self):
        self.closed = True


@pytest.fixture
def test_client(monkeypatch):
    user = AuthenticatedUser(
        id=902,
        username="module2-synthetic-exporter",
        role="OFFICIAL",
        subject_identifier="synthetic-module2-exporter",
    )
    monkeypatch.setenv("DEPARTMENTAI_DATABASE_ENV", "test")
    app.dependency_overrides.clear()
    app.dependency_overrides[auth_routes.get_current_user] = lambda: user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def _configure_grant(tmp_path, monkeypatch, permissions):
    path = tmp_path / "module2-permissions.json"
    path.write_text(
        json.dumps(
            {
                "users": {
                    "902": {
                        "permissions": permissions,
                        "departments": ["Synthetic Department"],
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("DEPARTMENTAI_MODULE2_PERMISSION_POLICY", str(path))


def test_authenticated_account_without_export_permission_gets_403(
    test_client, monkeypatch
):
    monkeypatch.delenv("DEPARTMENTAI_MODULE2_PERMISSION_POLICY", raising=False)
    response = test_client.get("/module2/export/datasets")
    assert response.status_code == 403


def test_dataset_discovery_uses_only_the_principal_allowlist(
    test_client, monkeypatch, tmp_path
):
    _configure_grant(
        tmp_path,
        monkeypatch,
        ["module2.export.faculty_profiles"],
    )
    response = test_client.get("/module2/export/datasets")
    assert response.status_code == 200
    body = response.json()
    assert [dataset["name"] for dataset in body["datasets"]] == [
        "faculty_profiles"
    ]
    assert "phone" not in body["datasets"][0]["columns"]
    assert "email" not in body["datasets"][0]["columns"]
    assert "student_name" not in body["datasets"][0]["columns"]
    assert body["max_rows"] == 10_000


@pytest.mark.parametrize(
    "url",
    [
        "/module2/export/m2_faculties/download?format=csv",
        "/module2/export/faculty_profiles/download?format=csv&columns=phone",
        "/module2/export/faculty_profiles/download?format=csv&columns=email",
        "/module2/export/faculty_profiles/download?format=csv&limit=0",
        "/module2/export/faculty_profiles/download?format=csv&limit=10001",
        "/module2/export/faculty_profiles/download?format=html",
    ],
)
def test_unapproved_or_malformed_export_is_rejected_without_database_access(
    test_client, monkeypatch, tmp_path, url
):
    _configure_grant(
        tmp_path,
        monkeypatch,
        ["module2.export.faculty_profiles"],
    )
    called = False

    def forbidden_connect(**_kwargs):
        nonlocal called
        called = True
        raise AssertionError("rejected export reached the database")

    monkeypatch.setenv("DEPARTMENTAI_MODULE2_DATABASE_ENV", "test")
    monkeypatch.setattr(module2_connection.psycopg, "connect", forbidden_connect)
    response = test_client.get(url)
    assert response.status_code in {404, 422}
    assert not called
    assert not response.headers.get("content-disposition")


def test_dataset_permission_is_independent_and_denial_reads_no_records(
    test_client, monkeypatch, tmp_path
):
    _configure_grant(
        tmp_path,
        monkeypatch,
        ["module2.export.faculty_profiles"],
    )
    called = False

    def forbidden_connect(**_kwargs):
        nonlocal called
        called = True
        raise AssertionError("unauthorized export reached the database")

    monkeypatch.setenv("DEPARTMENTAI_MODULE2_DATABASE_ENV", "test")
    monkeypatch.setattr(module2_connection.psycopg, "connect", forbidden_connect)
    response = test_client.get(
        "/module2/export/publications/download?format=csv"
    )
    assert response.status_code == 403
    assert not called
    assert not response.headers.get("content-disposition")


def test_successful_export_uses_test_profile_scope_and_allowed_columns(
    test_client, monkeypatch, tmp_path
):
    _configure_grant(
        tmp_path,
        monkeypatch,
        ["module2.export.faculty_profiles"],
    )
    profile_file = tmp_path / ".env.module2.test"
    profile_file.write_text(
        "DB_HOST=127.0.0.1\n"
        "DB_PORT=5432\n"
        "DB_NAME=departmentai_module2_test\n"
        "DB_USER=module2_test_user\n"
        "DB_PASSWORD=synthetic-test-password\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module2_connection, "PROJECT_ROOT", tmp_path)
    monkeypatch.setenv("DEPARTMENTAI_MODULE2_DATABASE_ENV", "test")
    cursor = FakeCursor([(55, "Synthetic Faculty")])
    connection = FakeConnection(cursor)
    connect_args = {}

    def test_database_connect(**kwargs):
        connect_args.update(kwargs)
        return connection

    monkeypatch.setattr(
        module2_connection.psycopg,
        "connect",
        test_database_connect,
    )
    response = test_client.get(
        "/module2/export/faculty_profiles/download"
        "?format=csv&limit=10&columns=id&columns=full_name"
    )

    assert response.status_code == 200
    assert response.headers["content-disposition"].endswith(
        'filename="faculty_profiles.csv"'
    )
    assert response.headers["x-export-row-count"] == "1"
    assert "Synthetic Faculty" in response.content.decode("utf-8-sig")
    assert "departmentai_module2_test" == connect_args["dbname"]
    assert connect_args["host"] == "127.0.0.1"
    assert cursor.parameters == (["Synthetic Department"], 11)
    assert "Synthetic Department" not in response.content.decode("utf-8-sig")
    assert connection.closed


def test_chatbot_permission_is_not_exposed_in_standalone_server(
    monkeypatch, tmp_path
):
    path = tmp_path / "unsupported-chat-permission.json"
    path.write_text(
        json.dumps(
            {
                "users": {
                    "902": {
                        "permissions": ["module2.faculty.read"],
                        "departments": ["Synthetic Department"],
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    user = AuthenticatedUser(
        id=902,
        username="module2-synthetic-exporter",
        role="OFFICIAL",
        subject_identifier="synthetic-module2-exporter",
    )
    from module2.chatbot_ui.server import app as chatbot_app

    chatbot_app.dependency_overrides.clear()
    chatbot_app.dependency_overrides[auth_routes.get_current_user] = lambda: user
    monkeypatch.setenv("DEPARTMENTAI_DATABASE_ENV", "test")
    monkeypatch.setenv("DEPARTMENTAI_MODULE2_PERMISSION_POLICY", str(path))
    with TestClient(chatbot_app) as standalone_client:
        response = standalone_client.post(
            "/api/chat",
            json={"question": "How many faculty records are present?"},
        )
    chatbot_app.dependency_overrides.clear()
    assert response.status_code == 403

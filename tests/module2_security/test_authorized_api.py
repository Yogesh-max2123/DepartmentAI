import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.api import auth_routes
from backend.main import app
from backend.services.auth_service import AuthenticatedUser
from module2 import api as module2_api
from module2.database.connection import Module2DatabaseConfigurationError


class FakeCursor:
    def __init__(self, names=(), rows=()):
        self.description = [SimpleNamespace(name=name) for name in names]
        self.rows = list(rows)
        self.query = None
        self.parameters = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, parameters=None):
        self.query = str(query)
        self.parameters = parameters

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.rows[0] if self.rows else None


class FakeConnection:
    def __init__(self, cursor):
        self.fake_cursor = cursor
        self.closed = False

    def cursor(self):
        return self.fake_cursor

    def close(self):
        self.closed = True


@pytest.fixture
def test_user():
    return AuthenticatedUser(
        id=701,
        username="module2-synthetic-reviewer",
        role="OFFICIAL",
        subject_identifier="synthetic-module2-reviewer",
    )


@pytest.fixture
def client(monkeypatch, test_user):
    monkeypatch.setenv("DEPARTMENTAI_DATABASE_ENV", "test")
    app.dependency_overrides.clear()
    app.dependency_overrides[auth_routes.get_current_user] = lambda: test_user
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _configure_grant(tmp_path, monkeypatch, permissions, departments=None):
    path = tmp_path / "module2-permissions.json"
    path.write_text(
        json.dumps(
            {
                "users": {
                    "701": {
                        "permissions": permissions,
                        "departments": departments or ["Synthetic Department"],
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("DEPARTMENTAI_MODULE2_PERMISSION_POLICY", str(path))
    return path


def test_unauthenticated_module2_routes_require_a_bearer_session(monkeypatch):
    monkeypatch.setenv("DEPARTMENTAI_DATABASE_ENV", "test")
    app.dependency_overrides.clear()
    with TestClient(app) as test_client:
        responses = [
            test_client.get("/module2/capabilities"),
            test_client.get("/module2/faculty"),
        ]
    app.dependency_overrides.clear()
    assert [response.status_code for response in responses] == [401, 401]


def test_authenticated_account_without_a_module2_grant_is_denied(
    client, monkeypatch
):
    monkeypatch.delenv("DEPARTMENTAI_MODULE2_PERMISSION_POLICY", raising=False)
    response = client.get("/module2/faculty")
    assert response.status_code == 403
    assert response.json()["detail"] == (
        "No Module II access is configured for this account."
    )


def test_capabilities_return_only_the_current_grants_without_database_access(
    client, monkeypatch, tmp_path
):
    _configure_grant(
        tmp_path,
        monkeypatch,
        [
            "module2.research.read",
            "module2.faculty.read",
        ],
        ["Synthetic Department"],
    )

    def database_access_must_not_run():
        raise Module2DatabaseConfigurationError("No profile is configured.")

    monkeypatch.setattr(module2_api, "get_database_settings", database_access_must_not_run)

    response = client.get("/module2/capabilities")

    assert response.status_code == 200
    assert response.json() == {
        "permissions": ["module2.faculty.read", "module2.research.read"],
        "departments": ["Synthetic Department"],
        "database_profile_configured": False,
    }


def test_capabilities_report_configured_database_profile_without_connecting(
    client, monkeypatch, tmp_path
):
    _configure_grant(
        tmp_path,
        monkeypatch,
        ["module2.faculty.read"],
        ["Synthetic Department"],
    )
    monkeypatch.setattr(module2_api, "get_database_settings", lambda: object())

    response = client.get("/module2/capabilities")

    assert response.status_code == 200
    assert response.json()["database_profile_configured"] is True


def test_capabilities_require_an_authenticated_module2_grant(
    client, monkeypatch
):
    monkeypatch.delenv("DEPARTMENTAI_MODULE2_PERMISSION_POLICY", raising=False)

    response = client.get("/module2/capabilities")

    assert response.status_code == 403


def test_explicit_user_grant_scopes_faculty_query_and_fields(
    client, monkeypatch, tmp_path
):
    _configure_grant(
        tmp_path,
        monkeypatch,
        ["module2.faculty.read"],
        ["Synthetic Department"],
    )
    cursor = FakeCursor(
        names=[
            "id",
            "full_name",
            "designation",
            "department",
            "qualification",
            "area_of_interest",
            "profile_url",
            "source_url",
            "source_name",
            "verification_status",
            "source_last_fetched_at",
        ],
        rows=[
            (
                17,
                "Synthetic Faculty",
                "Professor",
                "Synthetic Department",
                "Ph.D.",
                "Robotics",
                "https://example.invalid/profile",
                "https://example.invalid/source",
                "Synthetic source",
                "VERIFIED",
                None,
            )
        ],
    )
    connection = FakeConnection(cursor)
    monkeypatch.setattr(module2_api, "get_connection", lambda: connection)

    response = client.get(
        "/module2/faculty?query=Robotics&limit=10&offset=0"
    )

    assert response.status_code == 200
    assert response.json()["items"][0]["id"] == 17
    assert "phone" not in response.json()["items"][0]
    assert "email" not in response.json()["items"][0]
    assert "department = ANY" in cursor.query
    assert cursor.parameters == [
        ["Synthetic Department"],
        "%Robotics%",
        "%Robotics%",
        10,
        0,
    ]
    assert connection.closed


def test_department_parameter_cannot_broaden_faculty_scope(
    client, monkeypatch, tmp_path
):
    _configure_grant(
        tmp_path,
        monkeypatch,
        ["module2.faculty.read"],
        ["Synthetic Department"],
    )
    called = False

    def forbidden_connection():
        nonlocal called
        called = True
        raise AssertionError("out-of-scope request reached data access")

    monkeypatch.setattr(module2_api, "get_connection", forbidden_connection)
    response = client.get("/module2/faculty?department=Other%20Department")
    assert response.status_code == 404
    assert not called


def test_faculty_detail_hides_out_of_scope_ids(
    client, monkeypatch, tmp_path
):
    _configure_grant(
        tmp_path,
        monkeypatch,
        ["module2.faculty.read"],
        ["Synthetic Department"],
    )
    cursor = FakeCursor(names=["id"], rows=[])
    connection = FakeConnection(cursor)
    monkeypatch.setattr(module2_api, "get_connection", lambda: connection)
    response = client.get("/module2/faculty/88")
    assert response.status_code == 404
    assert "department = ANY" in cursor.query
    assert cursor.parameters == (88, ["Synthetic Department"])
    assert connection.closed


def test_research_reads_are_department_scoped_and_query_values_parameterized(
    client, monkeypatch, tmp_path
):
    _configure_grant(
        tmp_path,
        monkeypatch,
        ["module2.research.read"],
        ["Synthetic Department"],
    )
    cursor = FakeCursor(names=["id", "title"], rows=[(9, "Synthetic paper")])
    connection = FakeConnection(cursor)
    monkeypatch.setattr(module2_api, "get_connection", lambda: connection)
    response = client.get(
        "/module2/research/records/publications"
        "?query=paper&year_from=2020&year_to=2024&limit=20"
    )

    assert response.status_code == 200
    assert response.json()["items"] == [{"id": 9, "title": "Synthetic paper"}]
    assert "f.department = ANY(%s)" in cursor.query
    assert cursor.parameters == [
        ["Synthetic Department"],
        "%paper%",
        "%paper%",
        2020,
        2024,
        20,
        0,
    ]
    assert connection.closed


def test_invalid_research_type_and_year_range_are_rejected_before_query(
    client, monkeypatch, tmp_path
):
    _configure_grant(
        tmp_path,
        monkeypatch,
        ["module2.research.read"],
    )
    called = False

    def forbidden_connection():
        nonlocal called
        called = True
        raise AssertionError("invalid request reached data access")

    monkeypatch.setattr(module2_api, "get_connection", forbidden_connection)
    unsupported = client.get("/module2/research/records/supervision")
    invalid_years = client.get(
        "/module2/research/records/publications?year_from=2025&year_to=2020"
    )
    assert unsupported.status_code == 404
    assert invalid_years.status_code == 422
    assert not called


def test_statistics_need_an_independent_permission(
    client, monkeypatch, tmp_path
):
    _configure_grant(
        tmp_path,
        monkeypatch,
        ["module2.research.read"],
    )
    called = False

    def forbidden_connection():
        nonlocal called
        called = True
        raise AssertionError("unauthorized statistics reached data access")

    monkeypatch.setattr(module2_api, "get_connection", forbidden_connection)
    response = client.get("/module2/research/statistics")
    assert response.status_code == 403
    assert not called


def test_statistics_return_counts_only_for_granted_departments(
    client, monkeypatch, tmp_path
):
    _configure_grant(
        tmp_path,
        monkeypatch,
        ["module2.research.statistics.read"],
        ["Synthetic Department"],
    )
    cursor = FakeCursor(rows=[(5, 2, 1)])
    connection = FakeConnection(cursor)
    monkeypatch.setattr(module2_api, "get_connection", lambda: connection)

    response = client.get("/module2/research/statistics")

    assert response.status_code == 200
    assert response.json()["counts"] == {
        "publications": 5,
        "projects": 2,
        "achievements": 1,
    }
    assert cursor.parameters == (
        ["Synthetic Department"],
        ["Synthetic Department"],
        ["Synthetic Department"],
    )
    assert connection.closed


def test_malformed_permission_policy_fails_closed(client, monkeypatch, tmp_path):
    path = tmp_path / "invalid-permissions.json"
    path.write_text(
        json.dumps(
            {
                "users": {
                    "701": {
                        "permissions": ["module2.faculty.chat"],
                        "departments": ["Synthetic Department"],
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("DEPARTMENTAI_MODULE2_PERMISSION_POLICY", str(path))
    response = client.get("/module2/faculty")
    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Module II permission configuration is unavailable."
    )


def test_permission_policy_rejects_wildcard_department_scope(
    client, monkeypatch, tmp_path
):
    _configure_grant(
        tmp_path,
        monkeypatch,
        ["module2.faculty.read"],
        ["*"],
    )
    response = client.get("/module2/faculty")
    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Module II permission configuration is unavailable."
    )

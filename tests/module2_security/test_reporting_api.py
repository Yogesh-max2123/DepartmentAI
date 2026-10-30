import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.api import auth_routes
from backend.main import app
from backend.services.auth_service import AuthenticatedUser
from module2 import report_routes
from module2.reporting import REPORT_PERMISSION


class ReportCursor:
    def __init__(self, names=(), rows=()):
        self.description = [SimpleNamespace(name=name) for name in names]
        self.rows = list(rows)
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, parameters=None):
        self.calls.append((str(query), parameters))

    def fetchall(self):
        return self.rows


class ReportConnection:
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
        id=905,
        username="module2-synthetic-report-user",
        role="OFFICIAL",
        subject_identifier="synthetic-report-user",
    )


@pytest.fixture
def client(monkeypatch, test_user):
    app.dependency_overrides.clear()
    app.dependency_overrides[auth_routes.get_current_user] = lambda: test_user
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _configure_grant(tmp_path, monkeypatch, permissions, departments=None):
    path = tmp_path / "module2-report-permissions.json"
    path.write_text(
        json.dumps(
            {
                "users": {
                    "905": {
                        "permissions": permissions,
                        "departments": departments or ["Synthetic Department"],
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("DEPARTMENTAI_MODULE2_PERMISSION_POLICY", str(path))


def _install_database(monkeypatch, cursor):
    connection = ReportConnection(cursor)
    monkeypatch.setattr(report_routes, "get_connection", lambda: connection)
    return connection


def test_report_catalogue_requires_a_new_explicit_permission(
    client, monkeypatch, tmp_path
):
    _configure_grant(
        tmp_path,
        monkeypatch,
        ["module2.export.faculty_profiles"],
    )

    response = client.get("/module2/reports/templates")

    assert response.status_code == 403


def test_report_catalogue_requires_authentication(monkeypatch):
    app.dependency_overrides.clear()
    def unauthenticated_user():
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    app.dependency_overrides[auth_routes.get_current_user] = unauthenticated_user
    with TestClient(app) as unauthenticated_client:
        response = unauthenticated_client.get("/module2/reports/templates")
    app.dependency_overrides.clear()

    assert response.status_code == 401


def test_preview_is_scoped_uses_only_allowed_template_and_returns_summary(
    client, monkeypatch, tmp_path
):
    _configure_grant(
        tmp_path,
        monkeypatch,
        [REPORT_PERMISSION],
        ["Synthetic Department"],
    )
    cursor = ReportCursor(
        names=[
            "record_id",
            "title",
            "publication_type",
            "publication_year",
        ],
        rows=[(21, "Synthetic paper", "Journal", 2024)],
    )
    connection = _install_database(monkeypatch, cursor)

    response = client.post(
        "/module2/reports/preview",
        json={
            "template_id": "publications_summary",
            "year_from": 2020,
            "year_to": 2025,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["record_count"] == 1
    assert body["template_id"] == "publications_summary"
    assert body["status"] == "DRAFT_NOT_OFFICIAL"
    assert body["scope"]["departments"] == ["Synthetic Department"]
    assert body["filters"] == {"year_from": 2020, "year_to": 2025}
    assert body["preview_rows"] == [
        {
            "record_id": "21",
            "title": "Synthetic paper",
            "publication_type": "Journal",
            "journal_or_conference": "",
            "publisher": "",
            "publication_date": "",
            "publication_year": "2024",
            "doi": "",
            "authors": "",
            "faculty_names": "",
            "departments": "",
            "source_url": "",
        }
    ]
    query, parameters = cursor.calls[-1]
    assert "f.department = ANY(%s)" in query
    assert parameters == (
        ["Synthetic Department"],
        2020,
        2025,
        2_001,
    )
    assert connection.closed


@pytest.mark.parametrize(
    "payload",
    [
        {"template_id": "patents"},
        {"template_id": "faculty_directory", "year_from": 2020},
        {"template_id": "publications_summary", "year_from": 2025, "year_to": 2020},
        {
            "template_id": "faculty_directory",
            "department": "Other Department",
        },
        {"template_id": "faculty_directory", "columns": ["phone"]},
    ],
)
def test_invalid_or_client_scope_request_is_rejected_without_database_access(
    client, monkeypatch, tmp_path, payload
):
    _configure_grant(tmp_path, monkeypatch, [REPORT_PERMISSION])
    called = False

    def forbidden_connection():
        nonlocal called
        called = True
        raise AssertionError("invalid report request reached database")

    monkeypatch.setattr(report_routes, "get_connection", forbidden_connection)

    response = client.post("/module2/reports/preview", json=payload)

    assert response.status_code == 422
    assert not called


def test_report_generation_returns_download_only_after_server_render(
    client, monkeypatch, tmp_path
):
    _configure_grant(
        tmp_path,
        monkeypatch,
        [REPORT_PERMISSION],
        ["Synthetic Department"],
    )
    columns = [
        "record_id",
        "full_name",
        "designation",
        "department",
        "qualification",
        "area_of_interest",
        "verification_status",
        "profile_url",
        "source_name",
        "source_url",
    ]
    cursor = ReportCursor(
        names=columns,
        rows=[
            (
                41,
                "Synthetic Faculty",
                "Professor",
                "Synthetic Department",
                "Ph.D.",
                "Robotics",
                "VERIFIED",
                "https://example.invalid/profile",
                "Synthetic source",
                "https://example.invalid/source",
            )
        ],
    )
    connection = _install_database(monkeypatch, cursor)

    response = client.post(
        "/module2/reports/generate",
        json={"template_id": "faculty_directory", "format": "docx"},
    )

    assert response.status_code == 200
    assert response.content.startswith(b"PK")
    assert response.headers["x-report-status"] == "DRAFT_NOT_OFFICIAL"
    assert response.headers["x-report-record-count"] == "1"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["content-disposition"].endswith(".docx\"")
    assert connection.closed


def test_existing_export_permission_does_not_authorize_report_generation(
    client, monkeypatch, tmp_path
):
    _configure_grant(
        tmp_path,
        monkeypatch,
        ["module2.export.faculty_profiles"],
    )
    called = False

    def forbidden_connection():
        nonlocal called
        called = True
        raise AssertionError("missing report permission reached database")

    monkeypatch.setattr(report_routes, "get_connection", forbidden_connection)

    response = client.post(
        "/module2/reports/generate",
        json={"template_id": "faculty_directory", "format": "docx"},
    )

    assert response.status_code == 403
    assert not called


def test_generation_handles_unavailable_optional_format_before_query(
    client, monkeypatch, tmp_path
):
    _configure_grant(tmp_path, monkeypatch, [REPORT_PERMISSION])
    monkeypatch.setattr(report_routes, "available_report_formats", lambda: ([], {"docx": "missing"}))
    called = False

    def forbidden_connection():
        nonlocal called
        called = True
        raise AssertionError("unavailable format reached database")

    monkeypatch.setattr(report_routes, "get_connection", forbidden_connection)

    response = client.post(
        "/module2/reports/generate",
        json={"template_id": "faculty_directory", "format": "docx"},
    )

    assert response.status_code == 503
    assert not called

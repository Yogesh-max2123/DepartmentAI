import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.api import auth_routes
from backend.main import app
from backend.services.auth_service import AuthenticatedUser
from module2 import api as module2_api
from module2.authorization import (
    Module2AccessGrant,
    authorize_module2_permission,
)
from module2.data_quality import QUALITY_CATEGORIES, QUALITY_SCAN_LIMIT


class QualityCursor:
    def __init__(self, rows_by_category):
        self.rows_by_category = rows_by_category
        self.description = []
        self.rows = []
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, parameters):
        self.calls.append((query, parameters))
        category = next(
            name
            for name in QUALITY_CATEGORIES
            if f"FROM public.m2_{'faculties' if name == 'faculty' else name}" in query
        )
        columns, self.rows = self.rows_by_category.get(category, ([], []))
        self.description = [SimpleNamespace(name=name) for name in columns]

    def fetchall(self):
        return self.rows


class QualityConnection:
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


def test_data_quality_requires_authentication_and_explicit_permission(
    client, monkeypatch, tmp_path
):
    _configure_grant(
        tmp_path,
        monkeypatch,
        ["module2.research.read"],
    )
    current_override = app.dependency_overrides.pop(auth_routes.get_current_user)
    try:
        with TestClient(app) as unauthenticated_client:
            unauthenticated = unauthenticated_client.get("/module2/data-quality/issues")
    finally:
        app.dependency_overrides[auth_routes.get_current_user] = current_override
    denied = client.get("/module2/data-quality/issues")

    assert unauthenticated.status_code == 401
    assert denied.status_code == 403


def test_data_quality_scans_only_granted_scope_and_returns_persisted_findings(
    client, monkeypatch, tmp_path
):
    _configure_grant(
        tmp_path,
        monkeypatch,
        ["module2.data_quality.read"],
    )
    rows_by_category = {
        "faculty": (
            [
                "id",
                "full_name",
                "department",
                "profile_url",
                "source_name",
                "source_url",
            ],
            [
                (
                    1,
                    "Synthetic Faculty",
                    "Synthetic Department",
                    "https://example.invalid/1",
                    "Test source",
                    None,
                )
            ],
        ),
        "publications": (
            [
                "id",
                "title",
                "publication_type",
                "publication_date",
                "publication_year",
                "source_url",
            ],
            [(2, "Synthetic paper", "Journal", "2024-02-01", 2023, None)],
        ),
        "projects": (
            ["id", "title", "funding_agency", "start_date", "end_date", "source_url"],
            [(3, "Synthetic project", "Test funder", "2025-01-01", "2024-12-31", None)],
        ),
        "achievements": (
            [
                "id",
                "category",
                "title",
                "start_date",
                "end_date",
                "event_date",
                "year",
                "source_url",
            ],
            [(4, "Award", None, None, None, None, None, None)],
        ),
    }
    cursor = QualityCursor(rows_by_category)
    connection = QualityConnection(cursor)
    monkeypatch.setattr(module2_api, "get_connection", lambda: connection)

    response = client.get(
        "/module2/data-quality/issues?department=Other%20Department&limit=10"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["records_scanned"] == 4
    assert body["summary"]["total_issues"] == 2
    assert {(issue["category"], issue["issue_type"]) for issue in body["issues"]} == {
        ("publications", "publication_year_mismatch"),
        ("projects", "date_range_inconsistent"),
    }
    assert all(
        parameters == (["Synthetic Department"], QUALITY_SCAN_LIMIT + 1)
        for _, parameters in cursor.calls
    )
    assert all("= ANY(%s)" in query for query, _ in cursor.calls)
    assert all(
        not any(token in query.upper() for token in ("UPDATE ", "DELETE ", "INSERT "))
        for query, _ in cursor.calls
    )
    assert connection.closed


def test_category_filter_and_invalid_category_are_enforced_server_side(
    client, monkeypatch, tmp_path
):
    _configure_grant(
        tmp_path,
        monkeypatch,
        ["module2.data_quality.read"],
    )
    cursor = QualityCursor(
        {
            "projects": (
                [
                    "id",
                    "title",
                    "funding_agency",
                    "start_date",
                    "end_date",
                    "source_url",
                ],
                [],
            )
        }
    )
    connection = QualityConnection(cursor)
    monkeypatch.setattr(module2_api, "get_connection", lambda: connection)

    unsupported = client.get("/module2/data-quality/issues?category=supervision")
    filtered = client.get("/module2/data-quality/issues?category=projects")

    assert unsupported.status_code == 422
    assert filtered.status_code == 200
    assert filtered.json()["summary"]["record_counts"] == {"projects": 0}
    assert len(cursor.calls) == 1
    assert "m2_projects" in cursor.calls[0][0]


def test_data_quality_rejects_an_incomplete_scan_instead_of_returning_partial_counts(
    client, monkeypatch, tmp_path
):
    _configure_grant(
        tmp_path,
        monkeypatch,
        ["module2.data_quality.read"],
    )
    columns = [
        "id",
        "full_name",
        "department",
        "profile_url",
        "source_name",
        "source_url",
    ]
    rows = [
        (
            index,
            "Synthetic Faculty",
            "Synthetic Department",
            f"https://example.invalid/{index}",
            "Test source",
            None,
        )
        for index in range(QUALITY_SCAN_LIMIT + 1)
    ]
    cursor = QualityCursor({"faculty": (columns, rows)})
    monkeypatch.setattr(
        module2_api,
        "get_connection",
        lambda: QualityConnection(cursor),
    )

    response = client.get("/module2/data-quality/issues?category=faculty")

    assert response.status_code == 503
    assert "bounded data-quality review scan limit" in response.json()["detail"]


def test_review_write_actions_are_not_exposed(client, monkeypatch, tmp_path):
    _configure_grant(
        tmp_path,
        monkeypatch,
        ["module2.data_quality.read"],
    )

    response = client.post(
        "/module2/data-quality/issues",
        json={
            "action": "reviewed",
            "user_id": 702,
            "department": "Other Department",
        },
    )

    assert response.status_code == 405


def test_chat_permission_remains_unsupported():
    grant = Module2AccessGrant(
        user_id=701,
        permissions=frozenset({"module2.faculty.chat"}),
        departments=("Synthetic Department",),
    )

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as error:
        authorize_module2_permission(grant, "module2.faculty.chat")

    assert error.value.status_code == 403

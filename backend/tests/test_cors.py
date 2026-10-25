import pytest
from fastapi.testclient import TestClient

from backend.main import LOCAL_CORS_ORIGINS, app, get_cors_origins


@pytest.mark.parametrize("origin", LOCAL_CORS_ORIGINS)
def test_openapi_allows_explicit_local_origins(origin):
    with TestClient(app) as client:
        response = client.get(
            "/openapi.json",
            headers={"Origin": origin},
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert "access-control-allow-credentials" not in response.headers


def test_openapi_rejects_unconfigured_local_port():
    with TestClient(app) as client:
        response = client.options(
            "/openapi.json",
            headers={
                "Origin": "http://127.0.0.1:5502",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_configured_origins_replace_local_defaults(monkeypatch):
    monkeypatch.setenv(
        "CORS_ALLOWED_ORIGINS",
        "https://department.example.edu, https://api.example.edu/",
    )

    assert get_cors_origins() == [
        "https://department.example.edu",
        "https://api.example.edu",
    ]


@pytest.mark.parametrize(
    "value",
    [
        "*",
        "https://department.example.edu/path",
        "https://user:password@department.example.edu",
        "ftp://department.example.edu",
    ],
)
def test_configured_origins_reject_unsafe_values(monkeypatch, value):
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", value)

    with pytest.raises(ValueError, match="CORS_ALLOWED_ORIGINS"):
        get_cors_origins()

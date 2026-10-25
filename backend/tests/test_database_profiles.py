from fastapi.testclient import TestClient

import backend.database.connection as database_connection
import backend.api.auth_routes as auth_routes
import backend.services.auth_service as auth_service
from backend.database.connection import DatabaseSettings
from backend.main import app


def test_default_database_profile_remains_institutional(monkeypatch):
    monkeypatch.delenv("DEPARTMENTAI_DATABASE_ENV", raising=False)
    monkeypatch.setenv("DB_HOST", "10.219.45.43")
    monkeypatch.setenv("DB_PORT", "5432")
    monkeypatch.setenv("DB_NAME", "departmentai")
    monkeypatch.setenv("DB_USER", "institutional_user")
    monkeypatch.setenv("DB_PASSWORD", "not-a-real-password")

    settings = database_connection.get_database_settings()

    assert settings.environment == "institutional"
    assert settings.host == "10.219.45.43"
    assert settings.database == "departmentai"
    assert "not-a-real-password" not in repr(settings)


def test_development_profile_uses_only_its_local_file(tmp_path, monkeypatch):
    (tmp_path / ".env.development").write_text(
        "\n".join(
            [
                "DB_HOST=127.0.0.1",
                "DB_PORT=5432",
                "DB_NAME=departmentai_dev",
                "DB_USER=departmentai_local",
                "DB_PASSWORD=local-test-password",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(database_connection, "PROJECT_ROOT", tmp_path)
    monkeypatch.setenv("DEPARTMENTAI_DATABASE_ENV", "development")
    monkeypatch.setenv("DB_HOST", "10.219.45.43")
    monkeypatch.setenv("DB_NAME", "departmentai")

    settings = database_connection.get_database_settings()

    assert settings.environment == "development"
    assert settings.host == "127.0.0.1"
    assert settings.database == "departmentai_dev"


def test_development_profile_rejects_non_loopback_and_wrong_database(
    tmp_path, monkeypatch
):
    profile = tmp_path / ".env.development"
    profile.write_text(
        "DB_HOST=10.219.45.43\n"
        "DB_PORT=5432\n"
        "DB_NAME=departmentai_dev\n"
        "DB_USER=departmentai_local\n"
        "DB_PASSWORD=local-test-password\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(database_connection, "PROJECT_ROOT", tmp_path)
    monkeypatch.setenv("DEPARTMENTAI_DATABASE_ENV", "development")

    try:
        database_connection.get_database_settings()
    except ValueError as error:
        assert "loopback" in str(error)
    else:
        raise AssertionError("Development mode accepted a non-local host.")

    profile.write_text(
        "DB_HOST=127.0.0.1\n"
        "DB_PORT=5432\n"
        "DB_NAME=departmentai\n"
        "DB_USER=departmentai_local\n"
        "DB_PASSWORD=local-test-password\n",
        encoding="utf-8",
    )
    try:
        database_connection.get_database_settings()
    except ValueError as error:
        assert "departmentai_dev" in str(error)
    else:
        raise AssertionError("Development mode accepted a non-development DB.")


def test_development_mode_never_falls_back_to_institutional_env(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(database_connection, "PROJECT_ROOT", tmp_path)
    monkeypatch.setenv("DEPARTMENTAI_DATABASE_ENV", "development")
    monkeypatch.setenv("DB_HOST", "10.219.45.43")
    monkeypatch.setenv("DB_NAME", "departmentai")

    try:
        database_connection.get_database_settings()
    except RuntimeError as error:
        assert ".env.development" in str(error)
        assert "institutional settings are not used" in str(error)
    else:
        raise AssertionError("Development mode silently used institutional config.")


def test_unavailable_database_returns_safe_authentication_error(monkeypatch):
    monkeypatch.setenv("DEPARTMENTAI_DATABASE_ENV", "development")
    monkeypatch.setattr(
        database_connection,
        "get_database_settings",
        lambda: DatabaseSettings(
            environment="development",
            host="127.0.0.1",
            port=5432,
            database="departmentai_dev",
            user="departmentai_local",
            password="not-a-real-password",
        ),
    )
    monkeypatch.setattr(
        auth_service,
        "get_database_settings",
        lambda: database_connection.DatabaseSettings(
            environment="development",
            host="127.0.0.1",
            port=5432,
            database="departmentai_dev",
            user="departmentai_local",
            password="test-only-placeholder",
        ),
    )

    def unavailable_database(**_kwargs):
        raise database_connection.psycopg.OperationalError(
            "simulated local PostgreSQL unavailable"
        )

    monkeypatch.setattr(
        database_connection.psycopg, "connect", unavailable_database
    )
    with TestClient(app) as client:
        response = client.post(
            "/auth/login",
            json={"username": "synthetic", "password": "synthetic-password"},
        )

    assert response.status_code == 503
    assert response.json()["detail"] == "Authentication service is temporarily unavailable."
    assert "simulated local PostgreSQL unavailable" not in response.text


def test_institutional_profile_disables_local_password_authentication(monkeypatch):
    monkeypatch.setattr(
        auth_service,
        "get_database_settings",
        lambda: DatabaseSettings(
            environment="institutional",
            host="10.219.45.43",
            port=5432,
            database="departmentai",
            user="institutional_user",
            password="test-only-placeholder",
        ),
    )

    with TestClient(app) as client:
        response = client.post(
            "/auth/login",
            json={"username": "synthetic", "password": "synthetic-password"},
        )

    assert response.status_code == 503
    assert "identity provider" in response.json()["detail"]


def test_readiness_fails_without_exposing_database_error(monkeypatch):
    def unavailable_database():
        raise database_connection.psycopg.OperationalError(
            "simulated local PostgreSQL unavailable"
        )

    monkeypatch.setattr(auth_routes, "get_connection", unavailable_database)
    with TestClient(app) as client:
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["detail"] == "Database readiness check failed."
    assert "simulated local PostgreSQL unavailable" not in response.text

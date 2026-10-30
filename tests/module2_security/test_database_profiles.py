import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from module2.database import connection as module2_connection


def _write_profile(root: Path, name: str, **overrides: str) -> None:
    values = {
        "DB_HOST": "127.0.0.1",
        "DB_PORT": "5432",
        "DB_NAME": {
            "test": "departmentai_module2_test",
            "development": "departmentai_module2_dev",
            "production": "departmentai_prod",
        }[name],
        "DB_USER": "module2_test_user",
        "DB_PASSWORD": "synthetic-only-password",
    }
    values.update(overrides)
    (root / f".env.module2.{name}").write_text(
        "".join(f"{key}={value}\n" for key, value in values.items()),
        encoding="utf-8",
    )


def test_module2_test_profile_uses_only_its_dedicated_loopback_database(
    tmp_path, monkeypatch
):
    _write_profile(tmp_path, "test")
    monkeypatch.setattr(module2_connection, "PROJECT_ROOT", tmp_path)
    monkeypatch.setenv("DEPARTMENTAI_MODULE2_DATABASE_ENV", "test")
    monkeypatch.setenv("DEPARTMENTAI_DATABASE_ENV", "development")
    monkeypatch.setenv("DB_NAME", "departmentai")

    settings = module2_connection.get_database_settings()

    assert settings.environment == "test"
    assert settings.host == "127.0.0.1"
    assert settings.database == "departmentai_module2_test"
    assert "synthetic-only-password" not in repr(settings)


def test_missing_or_unselected_module2_profile_never_falls_back(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(module2_connection, "PROJECT_ROOT", tmp_path)
    monkeypatch.delenv("DEPARTMENTAI_MODULE2_DATABASE_ENV", raising=False)
    monkeypatch.setenv("DEPARTMENTAI_DATABASE_ENV", "test")
    monkeypatch.setenv("DB_HOST", "127.0.0.1")
    monkeypatch.setenv("DB_NAME", "departmentai_test")
    with pytest.raises(module2_connection.Module2DatabaseConfigurationError):
        module2_connection.get_database_settings()

    monkeypatch.setenv("DEPARTMENTAI_MODULE2_DATABASE_ENV", "test")
    with pytest.raises(
        module2_connection.Module2DatabaseConfigurationError,
        match=".env.module2.test",
    ):
        module2_connection.get_database_settings()


@pytest.mark.parametrize(
    "overrides",
    [
        {"DB_HOST": "192.0.2.10"},
        {"DB_HOST": "127.0.0.1", "DB_NAME": "departmentai"},
        {"DB_HOST": "127.0.0.1", "DB_NAME": "departmentai_test"},
        {"DB_PORT": "70000"},
    ],
)
def test_module2_test_profile_rejects_non_isolated_targets(
    tmp_path, monkeypatch, overrides
):
    _write_profile(tmp_path, "test", **overrides)
    monkeypatch.setattr(module2_connection, "PROJECT_ROOT", tmp_path)
    monkeypatch.setenv("DEPARTMENTAI_MODULE2_DATABASE_ENV", "test")

    with pytest.raises(module2_connection.Module2DatabaseConfigurationError):
        module2_connection.get_database_settings()


def test_development_and_production_require_their_own_explicit_profile_files(
    tmp_path, monkeypatch
):
    _write_profile(tmp_path, "development")
    monkeypatch.setattr(module2_connection, "PROJECT_ROOT", tmp_path)
    monkeypatch.setenv("DEPARTMENTAI_DATABASE_ENV", "test")
    monkeypatch.setenv("DEPARTMENTAI_MODULE2_DATABASE_ENV", "development")
    development = module2_connection.get_database_settings()
    assert development.database == "departmentai_module2_dev"
    assert development.environment == "development"

    _write_profile(tmp_path, "production")
    monkeypatch.setenv("DEPARTMENTAI_MODULE2_DATABASE_ENV", "production")
    production = module2_connection.get_database_settings()
    assert production.database == "departmentai_prod"
    assert production.environment == "production"


def test_get_connection_passes_only_resolved_test_settings(monkeypatch, tmp_path):
    _write_profile(tmp_path, "test")
    monkeypatch.setattr(module2_connection, "PROJECT_ROOT", tmp_path)
    monkeypatch.setenv("DEPARTMENTAI_MODULE2_DATABASE_ENV", "test")
    captured = {}
    connection = object()

    def connect(**kwargs):
        captured.update(kwargs)
        return connection

    monkeypatch.setattr(module2_connection.psycopg, "connect", connect)

    assert module2_connection.get_connection() is connection
    assert captured["dbname"] == "departmentai_module2_test"
    assert captured["host"] == "127.0.0.1"


def test_all_module2_postgres_connections_use_the_profile_resolver():
    module2_root = Path(__file__).resolve().parents[2] / "module2"
    direct_connections = []
    for path in module2_root.rglob("*.py"):
        if path.name == "connection.py" and path.parent.name == "database":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "connect"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "psycopg"
            ):
                direct_connections.append((path, node.lineno))
    assert direct_connections == []

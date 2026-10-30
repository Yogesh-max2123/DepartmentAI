import ipaddress
import os
from dataclasses import dataclass, field
from pathlib import Path

import psycopg
from dotenv import dotenv_values


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODULE2_DATABASE_PROFILE_ENV = "DEPARTMENTAI_MODULE2_DATABASE_ENV"
PROFILE_DATABASES = {
    "development": "departmentai_module2_dev",
    "test": "departmentai_module2_test",
}
CONNECTION_TIMEOUT_SECONDS = 5


class Module2DatabaseConfigurationError(RuntimeError):
    """Raised when Module II has no safe, explicitly selected database."""


@dataclass(frozen=True)
class Module2DatabaseSettings:
    environment: str
    host: str
    port: int
    database: str
    user: str
    password: str = field(repr=False)

    def connection_kwargs(self) -> dict[str, str | int]:
        return {
            "host": self.host,
            "port": self.port,
            "dbname": self.database,
            "user": self.user,
            "password": self.password,
            "connect_timeout": CONNECTION_TIMEOUT_SECONDS,
        }


def _is_loopback(host: str) -> bool:
    normalized_host = host.strip().lower()
    if normalized_host == "localhost":
        return True
    try:
        return ipaddress.ip_address(normalized_host).is_loopback
    except ValueError:
        return False


def get_database_settings() -> Module2DatabaseSettings:
    """Load one explicit Module II profile without Module I or global fallback."""
    profile = os.getenv(MODULE2_DATABASE_PROFILE_ENV, "").strip().lower()
    if profile not in {"development", "test", "production"}:
        raise Module2DatabaseConfigurationError(
            f"Set {MODULE2_DATABASE_PROFILE_ENV} to development, test, or "
            "production before using Module II."
        )

    config_path = PROJECT_ROOT / f".env.module2.{profile}"
    if not config_path.is_file():
        raise Module2DatabaseConfigurationError(
            f"Module II {profile} profile requires "
            f"{config_path.name}; no other database profile is used."
        )

    values = dotenv_values(config_path)
    required_keys = ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER")
    missing_keys = [key for key in required_keys if not values.get(key)]
    password = values.get("DB_PASSWORD") or values.get(
        "DEPARTMENTAI_DB_PASSWORD"
    )
    if not password:
        missing_keys.append("DB_PASSWORD")
    if missing_keys:
        raise Module2DatabaseConfigurationError(
            f"Module II {profile} profile is missing: "
            + ", ".join(missing_keys)
        )

    host = str(values["DB_HOST"]).strip()
    database = str(values["DB_NAME"]).strip()
    user = str(values["DB_USER"]).strip()
    if not host or not database or not user or not str(password):
        raise Module2DatabaseConfigurationError(
            "Module II database host, name, user, and password must be non-empty."
        )
    if profile in PROFILE_DATABASES:
        if not _is_loopback(host):
            raise Module2DatabaseConfigurationError(
                f"Module II {profile} profile permits only a loopback host."
            )
        expected_database = PROFILE_DATABASES[profile]
        if database != expected_database:
            raise Module2DatabaseConfigurationError(
                f"Module II {profile} profile requires database "
                f"{expected_database!r}."
            )

    try:
        port = int(str(values["DB_PORT"]))
    except (TypeError, ValueError) as error:
        raise Module2DatabaseConfigurationError(
            "Module II DB_PORT must be an integer from 1 to 65535."
        ) from error
    if not 1 <= port <= 65535:
        raise Module2DatabaseConfigurationError(
            "Module II DB_PORT must be an integer from 1 to 65535."
        )

    return Module2DatabaseSettings(
        environment=profile,
        host=host,
        port=port,
        database=database,
        user=user,
        password=str(password),
    )


def get_connection():
    """Open Module II's selected, validated database connection."""
    return psycopg.connect(
        **get_database_settings().connection_kwargs(),
    )

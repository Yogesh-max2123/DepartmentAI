import ipaddress
import os
from dataclasses import dataclass, field
from pathlib import Path

import psycopg
from dotenv import dotenv_values, load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_ENVIRONMENT_VARIABLE = "DEPARTMENTAI_DATABASE_ENV"
LOCAL_DATABASES = {
    "development": "departmentai_dev",
    "test": "departmentai_test",
}
CONNECTION_TIMEOUT_SECONDS = 5


@dataclass(frozen=True)
class DatabaseSettings:
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


def get_database_settings() -> DatabaseSettings:
    """Resolve the explicitly selected database profile without fallback."""
    environment = os.getenv(
        DATABASE_ENVIRONMENT_VARIABLE, "institutional"
    ).strip().lower()

    if environment == "institutional":
        load_dotenv(PROJECT_ROOT / ".env", override=False)
        values = os.environ
    elif environment in LOCAL_DATABASES:
        config_path = PROJECT_ROOT / f".env.{environment}"
        if not config_path.is_file():
            raise RuntimeError(
                f"Explicit {environment} database mode requires "
                f"{config_path.name}; institutional settings are not used."
            )
        values = dotenv_values(config_path)
    else:
        raise ValueError(
            f"Unsupported {DATABASE_ENVIRONMENT_VARIABLE} value. "
            "Choose institutional, development, or test."
        )

    required_keys = ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER")
    missing_keys = [key for key in required_keys if not values.get(key)]
    password = values.get("DB_PASSWORD") or values.get(
        "DEPARTMENTAI_DB_PASSWORD"
    )
    if not password:
        missing_keys.append("DB_PASSWORD")
    if missing_keys:
        raise RuntimeError(
            "Database configuration is incomplete; missing: "
            + ", ".join(missing_keys)
        )

    host = str(values["DB_HOST"]).strip()
    database = str(values["DB_NAME"]).strip()
    if environment in LOCAL_DATABASES:
        if not _is_loopback(host):
            raise ValueError(
                f"{environment} database mode only permits a loopback host."
            )
        expected_database = LOCAL_DATABASES[environment]
        if database != expected_database:
            raise ValueError(
                f"{environment} database mode requires database "
                f"{expected_database!r}."
            )

    try:
        port = int(str(values["DB_PORT"]))
    except ValueError as error:
        raise ValueError("DB_PORT must be an integer from 1 to 65535.") from error
    if not 1 <= port <= 65535:
        raise ValueError("DB_PORT must be an integer from 1 to 65535.")

    return DatabaseSettings(
        environment=environment,
        host=host,
        port=port,
        database=database,
        user=str(values["DB_USER"]).strip(),
        password=str(password),
    )


def get_connection() -> psycopg.Connection:
    """Connect only to the database selected by the explicit environment."""
    return psycopg.connect(**get_database_settings().connection_kwargs())
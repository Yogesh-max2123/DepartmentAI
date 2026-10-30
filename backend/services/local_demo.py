import ipaddress
import os
from dataclasses import dataclass

from backend.database.connection import (
    LOCAL_DATABASES,
    get_database_settings,
)
from backend.services.programme_identity import ProgrammeIdentity


LOCAL_DEMO_ENVIRONMENT_VARIABLE = "DEPARTMENTAI_LOCAL_DEMO"
LOCAL_DEMO_STUDENT_IDENTIFIER = "DEMO-MTECH-0001"
LOCAL_DEMO_IDENTITY_SOURCE = "LOCAL_SYNTHETIC_DEMO"
LOCAL_DEMO_SOURCE_ID = "LOCAL_DEMO_MTECH_RULES"
LOCAL_DEMO_SOURCE_FILE = "local-demo-mtech-rules.txt"
LOCAL_DEMO_ACCOUNTS = (
    ("demo.student", "STUDENT", LOCAL_DEMO_STUDENT_IDENTIFIER),
    ("demo.official", "OFFICIAL", "DEMO-OFFICIAL-0001"),
    ("demo.dugc", "DUGC", "DEMO-DUGC-0001"),
    ("demo.dugc.member", "DUGC", "DEMO-DUGC-0002"),
)


def local_demo_enabled() -> bool:
    if os.environ.get(LOCAL_DEMO_ENVIRONMENT_VARIABLE) != "1":
        return False

    settings = get_database_settings()
    if (
        settings.environment != "test"
        or settings.database != LOCAL_DATABASES["test"]
    ):
        raise RuntimeError(
            "The local demo requires the explicit isolated test database."
        )
    try:
        host_is_loopback = ipaddress.ip_address(settings.host).is_loopback
    except ValueError:
        host_is_loopback = settings.host.strip().lower() == "localhost"
    if not host_is_loopback:
        raise RuntimeError(
            "The local demo requires a loopback test database host."
        )
    return True


@dataclass(frozen=True)
class LocalDemoProgrammeIdentityProvider:
    def resolve(self, subject_identifier: str) -> ProgrammeIdentity:
        if subject_identifier != LOCAL_DEMO_STUDENT_IDENTIFIER:
            return ProgrammeIdentity(
                status="NOT_CONFIGURED",
                subject_identifier=subject_identifier,
            )
        return ProgrammeIdentity(
            status="VERIFIED",
            programme="MTECH",
            subject_identifier=subject_identifier,
            source_id=LOCAL_DEMO_IDENTITY_SOURCE,
            source_version="LOCAL-DEMO-1",
        )

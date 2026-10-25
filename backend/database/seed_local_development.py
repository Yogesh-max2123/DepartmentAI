from datetime import datetime
import os

from backend.database.connection import LOCAL_DATABASES, get_connection, get_database_settings
from backend.services.auth_service import hash_password


SYNTHETIC_APPLICANT = "SYNTHETIC-DEPARTMENTAI-DEV-STUDENT"
SYNTHETIC_APPLICATION_TYPE = "LOCAL_DEVELOPMENT_FIXTURE"
SYNTHETIC_COMMITTEE = "DUGC"


def _required_password(environment_name: str) -> str:
    value = os.getenv(environment_name)
    if not value:
        raise RuntimeError(
            f"Set {environment_name} in the current shell; seed passwords "
            "are never generated or printed automatically."
        )
    return value


def _ensure_user(cursor, username: str, role: str, subject: str, password: str) -> int:
    cursor.execute(
        """
        INSERT INTO auth_users (username, password_hash, role, subject_identifier)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (username) DO NOTHING
        RETURNING id, role, subject_identifier;
        """,
        (username, hash_password(password), role, subject),
    )
    row = cursor.fetchone()
    if row is None:
        cursor.execute(
            """
            SELECT id, role, subject_identifier
            FROM auth_users WHERE username = %s;
            """,
            (username,),
        )
        row = cursor.fetchone()
    if row is None or row[1] != role or row[2] != subject:
        raise RuntimeError(
            f"Existing development account {username!r} has unexpected "
            "role or identity; refusing to modify it."
        )
    return row[0]


def seed_local_development() -> tuple[int, int]:
    settings = get_database_settings()
    if (
        settings.environment != "development"
        or settings.database != LOCAL_DATABASES["development"]
    ):
        raise RuntimeError(
            "Synthetic fixture seeding is restricted to the explicit "
            "development database profile."
        )

    passwords = {
        "synthetic.student": _required_password(
            "DEPARTMENTAI_SEED_STUDENT_PASSWORD"
        ),
        "synthetic.official": _required_password(
            "DEPARTMENTAI_SEED_OFFICIAL_PASSWORD"
        ),
        "synthetic.dugc": _required_password(
            "DEPARTMENTAI_SEED_DUGC_PASSWORD"
        ),
    }
    connection = get_connection()
    try:
        with connection:
            with connection.cursor() as cursor:
                student_id = _ensure_user(
                    cursor,
                    "synthetic.student",
                    "STUDENT",
                    SYNTHETIC_APPLICANT,
                    passwords["synthetic.student"],
                )
                official_id = _ensure_user(
                    cursor,
                    "synthetic.official",
                    "OFFICIAL",
                    "SYNTHETIC-DEPARTMENTAI-DEV-OFFICIAL",
                    passwords["synthetic.official"],
                )
                dugc_id = _ensure_user(
                    cursor,
                    "synthetic.dugc",
                    "DUGC",
                    "SYNTHETIC-DEPARTMENTAI-DEV-DUGC",
                    passwords["synthetic.dugc"],
                )

                cursor.execute(
                    """
                    INSERT INTO committee_memberships (user_id, committee_type)
                    VALUES (%s, %s)
                    ON CONFLICT (user_id, committee_type) DO NOTHING;
                    """,
                    (dugc_id, SYNTHETIC_COMMITTEE),
                )
                cursor.execute(
                    """
                    SELECT id FROM applications
                    WHERE applicant_identifier = %s
                      AND application_type = %s
                      AND status NOT IN ('APPROVED', 'REJECTED', 'CLOSED')
                    ORDER BY id;
                    """,
                    (SYNTHETIC_APPLICANT, SYNTHETIC_APPLICATION_TYPE),
                )
                applications = cursor.fetchall()
                if len(applications) > 1:
                    raise RuntimeError(
                        "Multiple active synthetic development applications "
                        "exist; refusing to seed ambiguous records."
                    )

                if applications:
                    application_id = applications[0][0]
                else:
                    cursor.execute(
                        "SELECT nextval(pg_get_serial_sequence('applications', 'id'));"
                    )
                    application_id = cursor.fetchone()[0]
                    application_number = (
                        f"APP-{datetime.now().year}-{application_id:05d}"
                    )
                    cursor.execute(
                        """
                        INSERT INTO applications (
                            id, application_number, applicant_identifier,
                            application_type, title, description, status
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, 'DRAFT');
                        """,
                        (
                            application_id,
                            application_number,
                            SYNTHETIC_APPLICANT,
                            SYNTHETIC_APPLICATION_TYPE,
                            "Synthetic local development application",
                            "Development fixture; not an institutional record.",
                        ),
                    )
                    cursor.execute(
                        """
                        INSERT INTO application_status_history (
                            application_id, old_status, new_status,
                            changed_by, reason
                        )
                        VALUES (%s, NULL, 'DRAFT', 'SYSTEM',
                                'Synthetic local development fixture created.');
                        """,
                        (application_id,),
                    )
                cursor.execute(
                    """
                    INSERT INTO official_application_assignments
                        (application_id, user_id)
                    VALUES (%s, %s)
                    ON CONFLICT (application_id, user_id) DO NOTHING;
                    """,
                    (application_id, official_id),
                )
        return application_id, student_id
    finally:
        connection.close()


if __name__ == "__main__":
    seeded_application_id, _student_id = seed_local_development()
    print(
        "Synthetic development accounts and fixture are ready; "
        f"application id: {seeded_application_id}. "
        "No passwords were printed."
    )

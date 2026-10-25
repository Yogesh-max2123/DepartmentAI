from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import secrets

import bcrypt

from backend.database.connection import get_connection, get_database_settings


SESSION_LIFETIME = timedelta(minutes=30)
PASSWORD_MIN_BYTES = 12
PASSWORD_MAX_BYTES = 72
_DUMMY_PASSWORD_HASH = bcrypt.hashpw(
    b"departmentai-invalid-account-password",
    bcrypt.gensalt(rounds=12),
)


@dataclass(frozen=True)
class AuthenticatedUser:
    id: int
    username: str
    role: str
    subject_identifier: str


def require_development_authentication() -> None:
    settings = get_database_settings()
    if settings.environment not in {"development", "test"}:
        raise RuntimeError(
            "Local password authentication is available only in explicit "
            "development or test mode. Configure an institutional identity "
            "provider before enabling production sign-in."
        )


def hash_password(password: str) -> str:
    encoded_password = password.encode("utf-8")
    if not PASSWORD_MIN_BYTES <= len(encoded_password) <= PASSWORD_MAX_BYTES:
        raise ValueError(
            "Password must be between 12 and 72 UTF-8 bytes."
        )
    return bcrypt.hashpw(encoded_password, bcrypt.gensalt(rounds=12)).decode(
        "ascii"
    )


def verify_password(password: str, password_hash: str) -> bool:
    encoded_password = password.encode("utf-8")
    if not PASSWORD_MIN_BYTES <= len(encoded_password) <= PASSWORD_MAX_BYTES:
        return False
    try:
        return bcrypt.checkpw(
            encoded_password,
            password_hash.encode("ascii"),
        )
    except (ValueError, TypeError):
        return False


def authenticate_user(username: str, password: str) -> tuple[str, AuthenticatedUser] | None:
    require_development_authentication()
    normalized_username = username.strip().lower()
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, username, password_hash, role, subject_identifier
                FROM auth_users
                WHERE username = %s AND is_active = TRUE;
                """,
                (normalized_username,),
            )
            row = cursor.fetchone()

        candidate_hash = row[2].encode("ascii") if row else _DUMMY_PASSWORD_HASH
        try:
            password_matches = bcrypt.checkpw(
                password.encode("utf-8"),
                candidate_hash,
            )
        except (ValueError, TypeError):
            password_matches = False
        if row is None or not password_matches:
            return None

        token = secrets.token_urlsafe(48)
        token_hash = hashlib.sha256(token.encode("ascii")).hexdigest()
        expires_at = datetime.now(timezone.utc) + SESSION_LIFETIME
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO auth_sessions (token_hash, user_id, expires_at)
                VALUES (%s, %s, %s);
                """,
                (token_hash, row[0], expires_at),
            )
        connection.commit()
        return token, AuthenticatedUser(
            id=row[0],
            username=row[1],
            role=row[3],
            subject_identifier=row[4],
        )
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def resolve_session(token: str) -> AuthenticatedUser | None:
    try:
        token_hash = hashlib.sha256(token.encode("ascii")).hexdigest()
    except UnicodeEncodeError:
        return None
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT u.id, u.username, u.role, u.subject_identifier
                FROM auth_sessions s
                JOIN auth_users u ON u.id = s.user_id
                WHERE s.token_hash = %s
                  AND s.revoked_at IS NULL
                  AND s.expires_at > CURRENT_TIMESTAMP
                  AND u.is_active = TRUE;
                """,
                (token_hash,),
            )
            row = cursor.fetchone()
        if row is None:
            return None
        return AuthenticatedUser(
            id=row[0],
            username=row[1],
            role=row[2],
            subject_identifier=row[3],
        )
    finally:
        connection.close()


def revoke_session(token: str) -> None:
    token_hash = hashlib.sha256(token.encode("ascii")).hexdigest()
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE auth_sessions
                SET revoked_at = CURRENT_TIMESTAMP
                WHERE token_hash = %s AND revoked_at IS NULL;
                """,
                (token_hash,),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_application_access(user: AuthenticatedUser, application_id: int) -> bool:
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            if user.role == "STUDENT":
                cursor.execute(
                    """
                    SELECT 1 FROM applications
                    WHERE id = %s AND applicant_identifier = %s;
                    """,
                    (application_id, user.subject_identifier),
                )
            elif user.role == "OFFICIAL":
                cursor.execute(
                    """
                    SELECT 1
                    FROM official_application_assignments
                    WHERE application_id = %s AND user_id = %s;
                    """,
                    (application_id, user.id),
                )
            elif user.role == "DUGC":
                cursor.execute(
                    """
                    SELECT 1
                    FROM committee_reviews r
                    JOIN committee_memberships m
                      ON m.committee_type = r.committee_type
                    WHERE r.application_id = %s AND m.user_id = %s
                    LIMIT 1;
                    """,
                    (application_id, user.id),
                )
            else:
                return False
            return cursor.fetchone() is not None
    finally:
        connection.close()


def is_committee_member(
    user: AuthenticatedUser,
    committee_type: str,
) -> bool:
    if user.role != "DUGC":
        return False
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT 1 FROM committee_memberships
                WHERE user_id = %s AND committee_type = %s;
                """,
                (user.id, committee_type),
            )
            return cursor.fetchone() is not None
    finally:
        connection.close()


def get_review_access(user: AuthenticatedUser, review_id: int) -> int | None:
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT r.application_id
                FROM committee_reviews r
                JOIN committee_memberships m
                  ON m.committee_type = r.committee_type
                WHERE r.id = %s AND m.user_id = %s AND %s = 'DUGC';
                """,
                (review_id, user.id, user.role),
            )
            row = cursor.fetchone()
        return row[0] if row else None
    finally:
        connection.close()


def list_applications_for_user(
    user: AuthenticatedUser,
    limit: int,
    offset: int,
) -> list[dict]:
    if user.role == "STUDENT":
        query = """
            SELECT id, application_number, application_type, title,
                   description, status, submitted_at, created_at, updated_at
            FROM applications
            WHERE applicant_identifier = %s
            ORDER BY created_at DESC, id DESC
            LIMIT %s OFFSET %s;
        """
        parameters = (user.subject_identifier, limit, offset)
    elif user.role == "OFFICIAL":
        query = """
            SELECT a.id, a.application_number, a.application_type, a.title,
                   a.description, a.status, a.submitted_at, a.created_at,
                   a.updated_at
            FROM applications a
            JOIN official_application_assignments x
              ON x.application_id = a.id
            WHERE x.user_id = %s
            ORDER BY a.created_at DESC, a.id DESC
            LIMIT %s OFFSET %s;
        """
        parameters = (user.id, limit, offset)
    elif user.role == "DUGC":
        query = """
            SELECT DISTINCT a.id, a.application_number, a.application_type,
                   a.title, a.description, a.status, a.submitted_at,
                   a.created_at, a.updated_at
            FROM applications a
            JOIN committee_reviews r ON r.application_id = a.id
            JOIN committee_memberships m
              ON m.committee_type = r.committee_type
            WHERE m.user_id = %s
            ORDER BY a.created_at DESC, a.id DESC
            LIMIT %s OFFSET %s;
        """
        parameters = (user.id, limit, offset)
    else:
        return []

    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(query, parameters)
            rows = cursor.fetchall()
        return [
            {
                "id": row[0],
                "application_number": row[1],
                "application_type": row[2],
                "title": row[3],
                "description": row[4],
                "status": row[5],
                "submitted_at": row[6],
                "created_at": row[7],
                "updated_at": row[8],
            }
            for row in rows
        ]
    finally:
        connection.close()

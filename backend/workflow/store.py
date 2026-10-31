from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SQLITE_PATH = PROJECT_ROOT / "data" / "workflow.db"

STATUSES = (
    "DRAFT",
    "DOCS_VERIFIED",
    "OFFICIAL_REVIEW",
    "MEETING_PROPOSED",
    "MEETING_SCHEDULED",
    "MINUTES_GENERATED",
    "RESOLVED",
)

ALLOWED_TRANSITIONS = {
    "DRAFT": {"DOCS_VERIFIED", "OFFICIAL_REVIEW"},
    "DOCS_VERIFIED": {"OFFICIAL_REVIEW"},
    "OFFICIAL_REVIEW": {"MEETING_PROPOSED"},
    "MEETING_PROPOSED": {"MEETING_SCHEDULED", "OFFICIAL_REVIEW"},
    "MEETING_SCHEDULED": {"MINUTES_GENERATED"},
    "MINUTES_GENERATED": {"RESOLVED"},
    "RESOLVED": set(),
}

APPLICATION_TYPES = (
    "comprehensive_exam",
    "thesis_extension",
    "supervisor_allocation",
    "supervisor_change",
    "semester_leave",
    "thesis_submission",
    "dissertation_extension",
    "conversion_full_part",
    "slow_pace",
    "make_up_exam",
    "back_paper",
    "minor_honours",
    "general",
)

_DIALECT = None
_PG_CONN = None


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _json_dump(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def _json_load(value):
    if value is None or value == "":
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return value


def _row_to_user(row: dict) -> dict:
    return dict(row)


def _row_to_application(row: dict) -> dict:
    data = dict(row)
    data["verification_result"] = _json_load(data.get("verification_result"))
    data["missing_documents"] = _json_load(data.get("missing_documents")) or []
    data["proposed_slots"] = _json_load(data.get("proposed_slots")) or []
    data["approved_slot"] = _json_load(data.get("approved_slot"))
    data["member_availability"] = _json_load(data.get("member_availability")) or []
    return data


def _try_postgres():
    password = os.getenv("DEPARTMENTAI_DB_PASSWORD")
    if not password:
        return None
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor

        conn = psycopg2.connect(
            dbname=os.getenv("DEPARTMENTAI_DB_NAME", "departmentai"),
            user=os.getenv("DEPARTMENTAI_DB_USER", "postgres"),
            password=password,
            host=os.getenv("DEPARTMENTAI_DB_HOST", "localhost"),
            port=int(os.getenv("DEPARTMENTAI_DB_PORT", "5432")),
        )
        conn.autocommit = False
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT 1")
        return conn
    except Exception:
        return None


def _sqlite_conn():
    SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(SQLITE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _adapt_sql(sql: str) -> str:
    if _DIALECT == "sqlite":
        return sql.replace("%s", "?")
    return sql


@contextmanager
def get_cursor():
    global _PG_CONN
    if _DIALECT is None:
        init_workflow_db()
    if _DIALECT == "postgres":
        from psycopg2.extras import RealDictCursor

        if _PG_CONN is None or _PG_CONN.closed:
            _PG_CONN = _try_postgres()
            if _PG_CONN is None:
                raise RuntimeError("PostgreSQL connection lost.")
        cur = _PG_CONN.cursor(cursor_factory=RealDictCursor)
        try:
            yield cur
            _PG_CONN.commit()
        except Exception:
            _PG_CONN.rollback()
            raise
        finally:
            cur.close()
    else:
        conn = _sqlite_conn()
        cur = conn.cursor()
        try:
            yield cur
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()


def _fetchone(cur) -> dict | None:
    row = cur.fetchone()
    if row is None:
        return None
    return dict(row)


def _fetchall(cur) -> list[dict]:
    return [dict(row) for row in cur.fetchall()]


PG_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    role VARCHAR(32) NOT NULL,
    roll_number VARCHAR(64),
    department VARCHAR(128),
    programme VARCHAR(128),
    phone VARCHAR(32),
    photo_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS applications (
    id SERIAL PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES users(id),
    title VARCHAR(512) NOT NULL,
    description TEXT NOT NULL,
    application_type VARCHAR(128) NOT NULL DEFAULT 'general',
    status VARCHAR(32) NOT NULL DEFAULT 'DRAFT',
    verification_result TEXT,
    missing_documents TEXT,
    draft_resolution TEXT,
    proposal_id VARCHAR(64),
    proposed_slots TEXT,
    approved_slot TEXT,
    minutes_text TEXT,
    final_summary TEXT,
    official_id INTEGER REFERENCES users(id),
    committee_id INTEGER REFERENCES users(id),
    member_availability TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS application_documents (
    id SERIAL PRIMARY KEY,
    application_id INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    filename VARCHAR(512) NOT NULL,
    stored_path VARCHAR(1024) NOT NULL,
    content_type VARCHAR(128),
    extracted_text TEXT,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS status_history (
    id SERIAL PRIMARY KEY,
    application_id INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    from_status VARCHAR(32),
    to_status VARCHAR(32) NOT NULL,
    note TEXT,
    actor_id INTEGER REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    role VARCHAR(32) NOT NULL,
    roll_number VARCHAR(64),
    department VARCHAR(128),
    programme VARCHAR(128),
    phone VARCHAR(32),
    photo_url TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES users(id),
    title VARCHAR(512) NOT NULL,
    description TEXT NOT NULL,
    application_type VARCHAR(128) NOT NULL DEFAULT 'general',
    status VARCHAR(32) NOT NULL DEFAULT 'DRAFT',
    verification_result TEXT,
    missing_documents TEXT,
    draft_resolution TEXT,
    proposal_id VARCHAR(64),
    proposed_slots TEXT,
    approved_slot TEXT,
    minutes_text TEXT,
    final_summary TEXT,
    official_id INTEGER REFERENCES users(id),
    committee_id INTEGER REFERENCES users(id),
    member_availability TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS application_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    filename VARCHAR(512) NOT NULL,
    stored_path VARCHAR(1024) NOT NULL,
    content_type VARCHAR(128),
    extracted_text TEXT,
    uploaded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS status_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    from_status VARCHAR(32),
    to_status VARCHAR(32) NOT NULL,
    note TEXT,
    actor_id INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL
);
"""


def _seed_users():
    from backend.workflow.auth import hash_password

    seeds = [
        {
            "email": "student@mnnit.ac.in",
            "password": "student123",
            "full_name": "Ananya Sharma",
            "role": "STUDENT",
            "roll_number": "2023RCS01",
            "department": "Computer Science and Engineering",
            "programme": "Ph.D.",
            "phone": "9876543210",
        },
        {
            "email": "mtech.student@mnnit.ac.in",
            "password": "student123",
            "full_name": "Rohit Verma",
            "role": "STUDENT",
            "roll_number": "2024MCS12",
            "department": "Computer Science and Engineering",
            "programme": "M.Tech.",
            "phone": "9876543213",
        },
        {
            "email": "ug.student@mnnit.ac.in",
            "password": "student123",
            "full_name": "Priya Nair",
            "role": "STUDENT",
            "roll_number": "2023BCS45",
            "department": "Computer Science and Engineering",
            "programme": "B.Tech.",
            "phone": "9876543214",
        },
        {
            "email": "official@mnnit.ac.in",
            "password": "official123",
            "full_name": "Rajesh Kumar",
            "role": "OFFICIAL",
            "roll_number": None,
            "department": "Computer Science and Engineering",
            "programme": None,
            "phone": "9876543211",
        },
        {
            "email": "committee@mnnit.ac.in",
            "password": "committee123",
            "full_name": "Prof. Meera Joshi",
            "role": "COMMITTEE_DDPC",
            "roll_number": None,
            "department": "Computer Science and Engineering",
            "programme": None,
            "phone": "9876543212",
        },
    ]
    now = _now()
    with get_cursor() as cur:
        for item in seeds:
            cur.execute(
                _adapt_sql("SELECT id FROM users WHERE lower(email) = lower(%s)"),
                (item["email"],),
            )
            if _fetchone(cur):
                continue
            cur.execute(
                _adapt_sql(
                    """
                    INSERT INTO users (
                        email, password_hash, full_name, role, roll_number,
                        department, programme, phone, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                ),
                (
                    item["email"],
                    hash_password(item["password"]),
                    item["full_name"],
                    item["role"],
                    item["roll_number"],
                    item["department"],
                    item["programme"],
                    item["phone"],
                    now,
                ),
            )


def _ensure_optional_columns():
    with get_cursor() as cur:
        if _DIALECT == "postgres":
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS photo_url TEXT")
            cur.execute("ALTER TABLE applications ADD COLUMN IF NOT EXISTS member_availability TEXT")
        else:
            cur.execute("PRAGMA table_info(users)")
            user_cols = {row["name"] for row in _fetchall(cur)}
            if "photo_url" not in user_cols:
                cur.execute("ALTER TABLE users ADD COLUMN photo_url TEXT")
            cur.execute("PRAGMA table_info(applications)")
            app_cols = {row["name"] for row in _fetchall(cur)}
            if "member_availability" not in app_cols:
                cur.execute("ALTER TABLE applications ADD COLUMN member_availability TEXT")


def init_workflow_db() -> str:
    global _DIALECT, _PG_CONN
    pg = _try_postgres()
    if pg is not None:
        _DIALECT = "postgres"
        _PG_CONN = pg
        with get_cursor() as cur:
            for statement in [chunk.strip() for chunk in PG_SCHEMA.split(";") if chunk.strip()]:
                cur.execute(statement)
        _ensure_optional_columns()
        _seed_users()
        return "postgres"
    _DIALECT = "sqlite"
    SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(SQLITE_PATH)
    try:
        conn.executescript(SQLITE_SCHEMA)
        conn.commit()
    finally:
        conn.close()
    _ensure_optional_columns()
    _seed_users()
    return "sqlite"


def dialect() -> str:
    if _DIALECT is None:
        init_workflow_db()
    return _DIALECT or "unknown"


def get_user_by_email(email: str) -> dict | None:
    with get_cursor() as cur:
        cur.execute(
            _adapt_sql("SELECT * FROM users WHERE lower(email) = lower(%s)"),
            (email.strip(),),
        )
        row = _fetchone(cur)
        return _row_to_user(row) if row else None


def get_user_by_id(user_id: int) -> dict | None:
    with get_cursor() as cur:
        cur.execute(_adapt_sql("SELECT * FROM users WHERE id = %s"), (user_id,))
        row = _fetchone(cur)
        return _row_to_user(row) if row else None


def update_user(user_id: int, **fields) -> dict | None:
    allowed = {"full_name", "phone", "department", "programme", "photo_url"}
    payload = {key: value for key, value in fields.items() if key in allowed and value is not None}
    if not payload:
        return get_user_by_id(user_id)
    assignments = []
    values = []
    for key, value in payload.items():
        assignments.append(f"{key} = %s")
        values.append(value)
    values.append(user_id)
    with get_cursor() as cur:
        cur.execute(
            _adapt_sql(f"UPDATE users SET {', '.join(assignments)} WHERE id = %s"),
            tuple(values),
        )
    return get_user_by_id(user_id)


def create_application(student_id: int, title: str, description: str, application_type: str) -> dict:
    if application_type not in APPLICATION_TYPES:
        application_type = "general"
    now = _now()
    with get_cursor() as cur:
        if _DIALECT == "postgres":
            cur.execute(
                """
                INSERT INTO applications (
                    student_id, title, description, application_type, status,
                    created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (student_id, title.strip(), description.strip(), application_type, "DRAFT", now, now),
            )
            app_id = _fetchone(cur)["id"]
        else:
            cur.execute(
                """
                INSERT INTO applications (
                    student_id, title, description, application_type, status,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (student_id, title.strip(), description.strip(), application_type, "DRAFT", now, now),
            )
            app_id = cur.lastrowid
        cur.execute(
            _adapt_sql(
                """
                INSERT INTO status_history (
                    application_id, from_status, to_status, note, actor_id, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s)
                """
            ),
            (app_id, None, "DRAFT", "Application created", student_id, now),
        )
    return get_application(app_id)


def get_application(app_id: int) -> dict | None:
    with get_cursor() as cur:
        cur.execute(_adapt_sql("SELECT * FROM applications WHERE id = %s"), (app_id,))
        row = _fetchone(cur)
        if not row:
            return None
        return _row_to_application(row)


def list_applications(user: dict) -> list[dict]:
    role = user["role"]
    with get_cursor() as cur:
        if role == "STUDENT":
            cur.execute(
                _adapt_sql(
                    """
                    SELECT a.*, u.full_name AS student_name, u.roll_number AS student_roll
                    FROM applications a
                    JOIN users u ON u.id = a.student_id
                    WHERE a.student_id = %s
                    ORDER BY a.updated_at DESC
                    """
                ),
                (user["id"],),
            )
        elif role == "OFFICIAL":
            cur.execute(
                _adapt_sql(
                    """
                    SELECT a.*, u.full_name AS student_name, u.roll_number AS student_roll
                    FROM applications a
                    JOIN users u ON u.id = a.student_id
                    ORDER BY a.updated_at DESC
                    """
                )
            )
        else:
            cur.execute(
                _adapt_sql(
                    """
                    SELECT a.*, u.full_name AS student_name, u.roll_number AS student_roll
                    FROM applications a
                    JOIN users u ON u.id = a.student_id
                    WHERE a.status IN ('MEETING_PROPOSED', 'MEETING_SCHEDULED', 'MINUTES_GENERATED', 'RESOLVED')
                    ORDER BY a.updated_at DESC
                    """
                )
            )
        return [_row_to_application(row) for row in _fetchall(cur)]


def list_documents(app_id: int) -> list[dict]:
    with get_cursor() as cur:
        cur.execute(
            _adapt_sql(
                """
                SELECT id, application_id, filename, stored_path, content_type,
                       uploaded_at,
                       CASE WHEN extracted_text IS NULL THEN 0 ELSE length(extracted_text) END AS text_length
                FROM application_documents
                WHERE application_id = %s
                ORDER BY id
                """
            ),
            (app_id,),
        )
        return _fetchall(cur)


def list_history(app_id: int) -> list[dict]:
    with get_cursor() as cur:
        cur.execute(
            _adapt_sql(
                """
                SELECT h.*, u.full_name AS actor_name, u.role AS actor_role
                FROM status_history h
                LEFT JOIN users u ON u.id = h.actor_id
                WHERE h.application_id = %s
                ORDER BY h.id
                """
            ),
            (app_id,),
        )
        return _fetchall(cur)


def add_document(app_id: int, filename: str, stored_path: str, content_type: str, extracted_text: str) -> dict:
    now = _now()
    with get_cursor() as cur:
        if _DIALECT == "postgres":
            cur.execute(
                """
                INSERT INTO application_documents (
                    application_id, filename, stored_path, content_type, extracted_text, uploaded_at
                ) VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (app_id, filename, stored_path, content_type, extracted_text, now),
            )
            doc_id = _fetchone(cur)["id"]
        else:
            cur.execute(
                """
                INSERT INTO application_documents (
                    application_id, filename, stored_path, content_type, extracted_text, uploaded_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (app_id, filename, stored_path, content_type, extracted_text, now),
            )
            doc_id = cur.lastrowid
        cur.execute(_adapt_sql("SELECT * FROM application_documents WHERE id = %s"), (doc_id,))
        return _fetchone(cur)


def combined_extracted_text(app_id: int) -> str:
    with get_cursor() as cur:
        cur.execute(
            _adapt_sql(
                "SELECT filename, extracted_text FROM application_documents WHERE application_id = %s ORDER BY id"
            ),
            (app_id,),
        )
        parts = []
        for row in _fetchall(cur):
            parts.append(f"--- {row['filename']} ---\n{row.get('extracted_text') or ''}")
        return "\n\n".join(parts)


def update_application(app_id: int, **fields) -> dict:
    if not fields:
        return get_application(app_id)
    json_fields = {
        "verification_result",
        "missing_documents",
        "proposed_slots",
        "approved_slot",
        "member_availability",
    }
    fields["updated_at"] = _now()
    assignments = []
    values = []
    for key, value in fields.items():
        assignments.append(f"{key} = %s")
        if key in json_fields:
            values.append(_json_dump(value))
        else:
            values.append(value)
    values.append(app_id)
    with get_cursor() as cur:
        cur.execute(
            _adapt_sql(f"UPDATE applications SET {', '.join(assignments)} WHERE id = %s"),
            tuple(values),
        )
    return get_application(app_id)


def set_status(app_id: int, to_status: str, actor_id: int | None, note: str = "") -> dict:
    if to_status not in STATUSES:
        raise ValueError(f"Unknown status: {to_status}")
    app = get_application(app_id)
    if app is None:
        raise KeyError(f"Unknown application: {app_id}")
    current = app["status"]
    if current == to_status:
        return app
    allowed = ALLOWED_TRANSITIONS.get(current, set())
    if to_status not in allowed:
        raise ValueError(f"Cannot move from {current} to {to_status}")
    now = _now()
    with get_cursor() as cur:
        cur.execute(
            _adapt_sql(
                "UPDATE applications SET status = %s, updated_at = %s WHERE id = %s"
            ),
            (to_status, now, app_id),
        )
        cur.execute(
            _adapt_sql(
                """
                INSERT INTO status_history (
                    application_id, from_status, to_status, note, actor_id, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s)
                """
            ),
            (app_id, current, to_status, note, actor_id, now),
        )
    return get_application(app_id)


def application_detail(app_id: int) -> dict | None:
    app = get_application(app_id)
    if app is None:
        return None
    student = get_user_by_id(app["student_id"])
    app["student"] = {
        "id": student["id"],
        "full_name": student["full_name"],
        "email": student["email"],
        "roll_number": student.get("roll_number"),
        "department": student.get("department"),
        "programme": student.get("programme"),
        "phone": student.get("phone"),
    } if student else None
    app["documents"] = list_documents(app_id)
    app["history"] = list_history(app_id)
    return app

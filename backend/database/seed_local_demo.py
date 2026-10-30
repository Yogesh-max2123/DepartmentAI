import hashlib
import ipaddress
import json
import os
from pathlib import Path
import secrets
import tempfile

from psycopg.types.json import Jsonb

from backend.academic_programmes import EMBEDDING_DIMENSION, EMBEDDING_MODEL
from backend.database.connection import (
    LOCAL_DATABASES,
    PROJECT_ROOT,
    get_connection,
    get_database_settings,
)
from backend.services.application_policy_registry import (
    load_application_policy_registry,
)
from backend.services.auth_service import hash_password, verify_password
from backend.services.governance_workflow_registry import (
    load_governance_workflow_registry,
)
from backend.services.local_demo import (
    LOCAL_DEMO_ACCOUNTS,
    LOCAL_DEMO_SOURCE_FILE,
    LOCAL_DEMO_SOURCE_ID,
    local_demo_enabled,
)


DEMO_DIRECTORY = PROJECT_ROOT / ".local-demo"
CREDENTIALS_FILE = DEMO_DIRECTORY / "credentials.json"
POLICY_FILE = DEMO_DIRECTORY / "application-policies-demo-v2.json"
WORKFLOW_FILE = DEMO_DIRECTORY / "governance-workflows.json"
SOURCE_DIRECTORY = DEMO_DIRECTORY / "sources"
SOURCE_PATH = SOURCE_DIRECTORY / LOCAL_DEMO_SOURCE_FILE
SOURCE_MANIFEST_PATH = SOURCE_DIRECTORY / "manifest.json"
DEMO_RULES = (
    "LOCAL SYNTHETIC M.TECH DEMONSTRATION RULES\n"
    "This file is synthetic local demonstration material. It is not an "
    "institutional ordinance, official policy, or academic requirement.\n\n"
    "Section DEMO-1: A synthetic demonstration request must include a "
    "synthetic application form classified as APPLICATION_FORM and a "
    "synthetic academic transcript classified as MARKSHEET. These two "
    "document checks exist only to demonstrate the application's "
    "document-extraction, classification, readiness, and submission "
    "pipeline. They do not determine actual student eligibility.\n"
)
DEMO_RULE_CHUNKS = (
    {
        "chunk_id": "local_demo_mtech_rule_application_form",
        "text": (
            "LOCAL SYNTHETIC DEMO ONLY. Section DEMO-1 requires a synthetic "
            "application form classified as APPLICATION_FORM for this "
            "demonstration request. This is not an institutional rule."
        ),
    },
    {
        "chunk_id": "local_demo_mtech_rule_marksheet",
        "text": (
            "LOCAL SYNTHETIC DEMO ONLY. Section DEMO-1 requires a synthetic "
            "academic transcript classified as MARKSHEET for this "
            "demonstration request. This is not an institutional rule."
        ),
    },
)

DEMO_ACCOUNTS = LOCAL_DEMO_ACCOUNTS
DEMO_MEMBERSHIPS = (
    ("demo.dugc", "DUGC"),
    ("demo.dugc.member", "DUGC"),
)


def _validate_profile(settings):
    if (
        settings.environment != "test"
        or settings.database != LOCAL_DATABASES["test"]
    ):
        raise RuntimeError(
            "Refusing to provision demo data outside departmentai_test."
        )
    try:
        host_is_loopback = ipaddress.ip_address(settings.host).is_loopback
    except ValueError:
        host_is_loopback = settings.host.strip().lower() == "localhost"
    if not host_is_loopback:
        raise RuntimeError("The isolated test database host must be loopback.")


def _build_policy_documents():
    base_path = (
        PROJECT_ROOT / "backend" / "config" / "application_policies.json"
    )
    application_registry = json.loads(base_path.read_text(encoding="utf-8"))
    application_registry["registry_version"] = "local-demo-1"
    source_digest = hashlib.sha256(DEMO_RULES.encode("utf-8")).hexdigest()
    application_registry["sources"].append(
        {
            "source_id": LOCAL_DEMO_SOURCE_ID,
            "programme": "MTECH",
            "source_file": LOCAL_DEMO_SOURCE_FILE,
            "source_version": "LOCAL-DEMO-1",
            "source_sha256": source_digest,
            "approval_status": "APPROVED",
            "approval_evidence": (
                "Synthetic local demonstration source only; "
                "not institutional approval."
            ),
            "activation_scope": "TEST_ONLY",
            "title": "Synthetic M.Tech demonstration rules (not official)",
        }
    )
    application_registry["application_types"] = [
        {
            "application_type_id": "LOCAL_DEMO_MTECH",
            "display_title": "Synthetic M.Tech demonstration request",
            "programme": "MTECH",
            "approval_status": "APPROVED",
            "approval_evidence": (
                "Synthetic local demonstration configuration only; "
                "not institutional approval."
            ),
            "activation_scope": "TEST_ONLY",
            "source_ids": [LOCAL_DEMO_SOURCE_ID],
            "required_documents": [
                {
                    "requirement_id": "demo-application-form",
                    "description": (
                        "Synthetic local demo application form"
                    ),
                    "document_type": "APPLICATION_FORM",
                    "condition": "ALWAYS",
                    "source_id": LOCAL_DEMO_SOURCE_ID,
                    "citation": (
                        "Synthetic local demo rule DEMO-1; not an "
                        "institutional ordinance."
                    ),
                    "section_numbers": ["DEMO-1"],
                    "evidence": (
                        "This demonstration-only rule requires an uploaded "
                        "application form classified by the document service."
                    ),
                },
                {
                    "requirement_id": "demo-academic-transcript",
                    "description": (
                        "Synthetic local demo academic transcript"
                    ),
                    "document_type": "MARKSHEET",
                    "condition": "ALWAYS",
                    "source_id": LOCAL_DEMO_SOURCE_ID,
                    "citation": (
                        "Synthetic local demo rule DEMO-1; not an "
                        "institutional ordinance."
                    ),
                    "section_numbers": ["DEMO-1"],
                    "evidence": (
                        "This demonstration-only rule requires an uploaded "
                        "transcript classified by the document service."
                    ),
                },
            ],
            "eligibility_rules": [],
            "processing_capabilities": [],
        }
    ]

    workflow_registry = {
        "schema_version": 1,
        "registry_version": "local-demo-1",
        "committee_policies": [
            {
                "committee_type": "DUGC",
                "approval_status": "APPROVED",
                "activation_scope": "TEST_ONLY",
                "approval_evidence": (
                    "Synthetic local demonstration configuration only; "
                    "not institutional approval."
                ),
                "minimum_confirmations": 2,
                "meeting_approver_usernames": ["demo.dugc"],
                "minutes_approver_usernames": ["demo.dugc"],
                "index_finalized_minutes": False,
            }
        ],
    }
    return application_registry, workflow_registry


def _write_demo_source_files():
    SOURCE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    if SOURCE_PATH.exists():
        existing = SOURCE_PATH.read_text(encoding="utf-8")
        if existing != DEMO_RULES:
            raise RuntimeError(
                "Refusing to overwrite an edited local demo source."
            )
    if SOURCE_PATH.read_bytes() != DEMO_RULES.encode("utf-8"):
        SOURCE_PATH.write_bytes(DEMO_RULES.encode("utf-8"))

    manifest = {
        "schema_version": 1,
        "source_id": LOCAL_DEMO_SOURCE_ID,
        "source_file": LOCAL_DEMO_SOURCE_FILE,
        "source_version": "LOCAL-DEMO-1",
        "programme": "MTECH",
        "sections": [{"number": "DEMO-1", "title": "Synthetic demo checks"}],
        "chunks": [
            {
                **chunk,
                "section": "DEMO-1",
                "section_title": "Synthetic demo checks",
            }
            for chunk in DEMO_RULE_CHUNKS
        ],
    }
    _write_private_json(SOURCE_MANIFEST_PATH, manifest)
    return manifest


def _index_demo_source(connection, manifest):
    import numpy as np
    from sentence_transformers import SentenceTransformer

    digest = hashlib.sha256(SOURCE_PATH.read_bytes()).hexdigest()
    expected_digest = hashlib.sha256(DEMO_RULES.encode("utf-8")).hexdigest()
    if digest != expected_digest:
        raise RuntimeError("The synthetic local demo source hash is invalid.")

    model = SentenceTransformer(EMBEDDING_MODEL, local_files_only=True)
    vectors = model.encode(
        [chunk["text"] for chunk in manifest["chunks"]],
        normalize_embeddings=True,
    )
    if len(vectors) != len(manifest["chunks"]) or any(
        len(vector) != EMBEDDING_DIMENSION for vector in vectors
    ):
        raise RuntimeError("The local demo source embedding shape is invalid.")

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT id FROM documents WHERE file_name = %s;",
            (LOCAL_DEMO_SOURCE_FILE,),
        )
        document = cursor.fetchone()
        if document is None:
            cursor.execute(
                "INSERT INTO documents (file_name) VALUES (%s) RETURNING id;",
                (LOCAL_DEMO_SOURCE_FILE,),
            )
            document_id = cursor.fetchone()[0]
        else:
            document_id = document[0]

        cursor.execute(
            """
            SELECT section_number, title
            FROM sections
            WHERE document_id = %s;
            """,
            (document_id,),
        )
        sections = cursor.fetchall()
        if sections and sections != [("DEMO-1", "Synthetic demo checks")]:
            raise RuntimeError(
                "The local demo source has unexpected indexed sections."
            )
        if not sections:
            cursor.execute(
                """
                INSERT INTO sections (document_id, section_number, title)
                VALUES (%s, 'DEMO-1', 'Synthetic demo checks')
                RETURNING id;
                """,
                (document_id,),
            )
            section_id = cursor.fetchone()[0]
        else:
            cursor.execute(
                "SELECT id FROM sections WHERE document_id=%s AND section_number='DEMO-1';",
                (document_id,),
            )
            section_id = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT metadata->>'chunk_id', metadata->>'source_sha256',
                   metadata->>'source_version', metadata->>'source_id',
                   metadata->>'source_file', metadata->>'embedding_model',
                   metadata->>'embedding_dimension'
            FROM knowledge_chunks
            WHERE document_id = %s;
            """,
            (document_id,),
        )
        existing_chunks = cursor.fetchall()
        expected_ids = {chunk["chunk_id"] for chunk in manifest["chunks"]}
        if existing_chunks:
            existing_ids = {row[0] for row in existing_chunks}
            valid_existing = (
                len(existing_chunks) == len(expected_ids)
                and existing_ids == expected_ids
                and all(
                    row[1] == digest
                    and row[2] == "LOCAL-DEMO-1"
                    and row[3] == LOCAL_DEMO_SOURCE_ID
                    and row[4] == LOCAL_DEMO_SOURCE_FILE
                    and row[5] == EMBEDDING_MODEL
                    and row[6] == str(EMBEDDING_DIMENSION)
                    for row in existing_chunks
                )
            )
            if not valid_existing:
                raise RuntimeError(
                    "The indexed local demo source conflicts with the "
                    "generated manifest; refusing to replace it."
                )
            return len(existing_chunks)

        for index, (chunk, vector) in enumerate(
            zip(manifest["chunks"], vectors, strict=True)
        ):
            metadata = {
                "chunk_id": chunk["chunk_id"],
                "programme": "MTECH",
                "source_id": LOCAL_DEMO_SOURCE_ID,
                "source_version": "LOCAL-DEMO-1",
                "source_sha256": digest,
                "approval_status": "APPROVED",
                "source_file": LOCAL_DEMO_SOURCE_FILE,
                "section_title": "Synthetic demo checks",
                "clause_title": "Synthetic local demo requirements",
                "embedding_model": EMBEDDING_MODEL,
                "embedding_dimension": EMBEDDING_DIMENSION,
                "activation_scope": "TEST_ONLY",
            }
            embedding = "[" + ",".join(
                str(float(value)) for value in np.asarray(vector).tolist()
            ) + "]"
            cursor.execute(
                """
                INSERT INTO knowledge_chunks (
                    document_id, section_id, chunk_index, chunk_type,
                    clause_number, chunk_text, page_start, page_end,
                    metadata, embedding
                )
                VALUES (%s, %s, %s, 'SYNTHETIC_DEMO_RULE', %s, %s,
                        NULL, NULL, %s, %s::vector);
                """,
                (
                    document_id,
                    section_id,
                    index,
                    "DEMO-1",
                    chunk["text"],
                    Jsonb(metadata),
                    embedding,
                ),
            )
    return len(manifest["chunks"])


def _write_private_json(path, document):
    content = json.dumps(document, indent=2, sort_keys=True) + "\n"
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if existing != content:
            raise RuntimeError(
                f"Refusing to overwrite an existing local demo file: {path.name}."
            )
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
        if os.name == "nt" and path == CREDENTIALS_FILE:
            print(
                "WARNING: Windows access permissions for local demo files "
                "inherit from the containing folder."
            )
        else:
            os.chmod(temporary_name, 0o600)
        os.replace(temporary_name, path)
        if os.name != "nt":
            os.chmod(path, 0o600)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def _load_or_create_credentials():
    if CREDENTIALS_FILE.exists():
        try:
            document = json.loads(
                CREDENTIALS_FILE.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError(
                "The local demo credential file is unreadable or invalid."
            ) from error
        if not isinstance(document, dict):
            raise RuntimeError("The local demo credential file is invalid.")
        accounts = document.get("accounts")
        if (
            not isinstance(accounts, list)
            or len(accounts) != len(DEMO_ACCOUNTS)
            or any(not isinstance(account, dict) for account in accounts)
        ):
            raise RuntimeError("The local demo credential file is invalid.")
        expected = {username for username, _, _ in DEMO_ACCOUNTS}
        supplied = {
            account.get("username"): account.get("password")
            for account in accounts
        }
        if (
            len(supplied) != len(accounts)
            or set(supplied) != expected
            or any(
                not isinstance(password, str)
                or not 12 <= len(password.encode("utf-8")) <= 72
                for password in supplied.values()
            )
        ):
            raise RuntimeError(
                "The local demo credential file does not match the demo accounts."
            )
        return supplied

    credentials = {
        username: secrets.token_urlsafe(24)
        for username, _, _ in DEMO_ACCOUNTS
    }
    _write_private_json(
        CREDENTIALS_FILE,
        {
            "notice": (
                "Synthetic local demo credentials. Do not reuse for real accounts."
            ),
            "accounts": [
                {"username": username, "password": credentials[username]}
                for username, _, _ in DEMO_ACCOUNTS
            ],
        },
    )
    return credentials


def _verify_runtime_target(connection):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT current_database(), inet_server_addr()::text,
                   to_regclass('public.auth_users'),
                   to_regclass('public.committee_memberships');
            """
        )
        database, server_address, auth_users, memberships = cursor.fetchone()
    if database != LOCAL_DATABASES["test"]:
        raise RuntimeError(
            "The live connection did not reach departmentai_test."
        )
    try:
        server_is_loopback = (
            ipaddress.ip_interface(server_address).ip.is_loopback
        )
    except (TypeError, ValueError):
        server_is_loopback = False
    if not server_is_loopback:
        raise RuntimeError(
            "The live test database connection did not use a loopback server."
        )
    if auth_users is None or memberships is None:
        raise RuntimeError(
            "The existing test database schema is missing required auth tables."
        )


def _ensure_accounts(connection, credentials):
    with connection.cursor() as cursor:
        usernames = [username for username, _, _ in DEMO_ACCOUNTS]
        cursor.execute(
            """
            SELECT username, password_hash, role, subject_identifier, is_active
            FROM auth_users
            WHERE username = ANY(%s)
            FOR UPDATE;
            """,
            (usernames,),
        )
        existing = {row[0]: row[1:] for row in cursor.fetchall()}

        for username, role, subject_identifier in DEMO_ACCOUNTS:
            current = existing.get(username)
            if current is None:
                cursor.execute(
                    """
                    INSERT INTO auth_users (
                        username, password_hash, role, subject_identifier
                    )
                    VALUES (%s, %s, %s, %s);
                    """,
                    (
                        username,
                        hash_password(credentials[username]),
                        role,
                        subject_identifier,
                    ),
                )
                continue
            password_hash, current_role, current_subject, is_active = current
            if (
                current_role != role
                or current_subject != subject_identifier
                or not is_active
                or not verify_password(
                    credentials[username],
                    password_hash,
                )
            ):
                raise RuntimeError(
                    f"Reserved synthetic demo account {username!r} "
                    "already exists with different credentials or attributes."
                )

        expected_memberships = {
            username: set()
            for username, _, _ in DEMO_ACCOUNTS
        }
        for username, committee_type in DEMO_MEMBERSHIPS:
            expected_memberships[username].add(committee_type)
        cursor.execute(
            """
            SELECT u.username, m.committee_type
            FROM auth_users u
            JOIN committee_memberships m ON m.user_id = u.id
            WHERE u.username = ANY(%s);
            """,
            (usernames,),
        )
        current_memberships = {username: set() for username in usernames}
        for username, committee_type in cursor.fetchall():
            current_memberships[username].add(committee_type)
        if any(
            not memberships.issubset(expected_memberships[username])
            for username, memberships in current_memberships.items()
        ):
            raise RuntimeError(
                "A reserved synthetic demo account has an unexpected "
                "committee membership."
            )

        for username, committee_type in DEMO_MEMBERSHIPS:
            cursor.execute(
                """
                INSERT INTO committee_memberships (user_id, committee_type)
                SELECT id, %s
                FROM auth_users
                WHERE username = %s
                  AND role = 'DUGC'
                  AND subject_identifier IN (
                      'DEMO-DUGC-0001',
                      'DEMO-DUGC-0002'
                  )
                ON CONFLICT (user_id, committee_type) DO NOTHING;
                """,
                (committee_type, username),
            )
            if cursor.rowcount != 1:
                cursor.execute(
                    """
                    SELECT 1
                    FROM auth_users u
                    JOIN committee_memberships m ON m.user_id = u.id
                    WHERE u.username = %s
                      AND u.role = 'DUGC'
                      AND u.subject_identifier IN (
                          'DEMO-DUGC-0001',
                          'DEMO-DUGC-0002'
                      )
                      AND m.committee_type = %s;
                    """,
                    (username, committee_type),
                )
                if cursor.fetchone() is None:
                    raise RuntimeError(
                        "Could not verify the synthetic committee membership."
                    )


def seed_local_demo():
    if not local_demo_enabled():
        raise RuntimeError(
            "Set DEPARTMENTAI_LOCAL_DEMO=1 to provision the local demo."
        )
    settings = get_database_settings()
    _validate_profile(settings)
    manifest = _write_demo_source_files()
    application_registry, workflow_registry = _build_policy_documents()

    application_path = _write_policy_file(
        POLICY_FILE,
        application_registry,
        load_application_policy_registry,
    )
    workflow_path = _write_policy_file(
        WORKFLOW_FILE,
        workflow_registry,
        load_governance_workflow_registry,
    )
    if application_path["status"] != "AVAILABLE":
        raise RuntimeError("The synthetic local application policy is invalid.")
    if workflow_path["status"] != "AVAILABLE":
        raise RuntimeError("The synthetic local governance policy is invalid.")

    credentials = _load_or_create_credentials()
    connection = get_connection()
    try:
        _verify_runtime_target(connection)
        indexed_chunk_count = _index_demo_source(connection, manifest)
        _ensure_accounts(connection, credentials)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    return len(DEMO_ACCOUNTS), indexed_chunk_count


def _write_policy_file(path, document, loader):
    _write_private_json(path, document)
    return loader(str(path))


def main():
    account_count, indexed_chunk_count = seed_local_demo()
    print(
        f"Provisioned or verified {account_count} synthetic local demo "
        f"accounts and {indexed_chunk_count} synthetic rule chunks in "
        "departmentai_test."
    )
    print("Credentials and TEST_ONLY policy files are under .local-demo/.")
    print(
        "Enable only for the local demo with "
        "DEPARTMENTAI_LOCAL_DEMO=1 and the generated policy paths."
    )


if __name__ == "__main__":
    main()

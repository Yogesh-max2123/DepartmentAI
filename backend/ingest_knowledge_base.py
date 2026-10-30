import hashlib
import json
import argparse
from pathlib import Path

import psycopg2
from psycopg2.extras import Json

from backend.academic_programmes import (
    EMBEDDING_DIMENSION,
    EMBEDDING_MODEL,
    PROGRAMME_CORPORA,
    get_programme_corpus,
    normalize_programme,
)
from backend.database.connection import LOCAL_DATABASES, get_database_settings
from backend.services.application_policy_registry import (
    load_application_policy_registry,
)

# ============================================================
# Configuration
# ============================================================
MAX_SOURCE_PDF_BYTES = 100 * 1024 * 1024


def validate_files(programme="UG"):
    """Resolve a supported source and verify all required assets exist."""
    corpus = get_programme_corpus(programme)
    if corpus["pdf"].stat().st_size > MAX_SOURCE_PDF_BYTES:
        raise ValueError("The registered ordinance PDF exceeds the 100 MiB limit.")
    for key in ("pdf", "chunks", "structure", "embeddings"):
        path = Path(corpus[key])
        if not path.is_file():
            raise FileNotFoundError(
                f"Required {normalize_programme(programme)} source asset "
                f"not found: {path}"
            )
    return corpus


def verify_registered_source(programme, source_file, pdf_path):
    registry = load_application_policy_registry()
    if registry["status"] in {"CONFLICT", "UNAVAILABLE"}:
        raise ValueError("The approved knowledge-source registry is unavailable.")
    sources = [
        source
        for source in registry["sources"]
        if source.get("programme") == programme
        and source.get("source_file") == source_file
        and source.get("approval_status") == "APPROVED"
    ]
    if len(sources) != 1:
        raise ValueError(
            "The selected source is not uniquely registered as approved."
        )
    digest = hashlib.sha256()
    with Path(pdf_path).open("rb") as source_stream:
        for block in iter(lambda: source_stream.read(1024 * 1024), b""):
            digest.update(block)
    source_sha256 = digest.hexdigest()
    if source_sha256 != sources[0]["source_sha256"].lower():
        raise ValueError(
            "The selected source PDF does not match the approved registry hash."
        )
    return sources[0]


def ensure_document_sections(cursor, source_file, structure_file):
    """Create missing source metadata without overwriting existing records."""
    structure_data = json.loads(structure_file.read_text(encoding="utf-8"))
    document = structure_data.get("document", {})
    if document.get("source_file") != source_file:
        raise ValueError(
            "The source filename in the chunk data does not match "
            "the document structure."
        )

    sections = structure_data.get("sections")
    if not isinstance(sections, list) or not sections:
        raise ValueError("The document structure contains no sections.")

    section_titles = {}
    for section in sections:
        number = str(section.get("number", "")).strip()
        title = str(section.get("title", "")).strip()
        if not number or not title or number in section_titles:
            raise ValueError("The document structure has invalid sections.")
        section_titles[number] = title

    cursor.execute(
        "SELECT id FROM documents WHERE file_name = %s;",
        (source_file,),
    )
    document_rows = cursor.fetchall()
    if len(document_rows) > 1:
        raise RuntimeError(
            f"Multiple document records exist for {source_file!r}."
        )
    if document_rows:
        document_id = document_rows[0][0]
    else:
        cursor.execute(
            """
            INSERT INTO documents (file_name)
            VALUES (%s)
            RETURNING id;
            """,
            (source_file,),
        )
        document_id = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT section_number, title
        FROM sections
        WHERE document_id = %s;
        """,
        (document_id,),
    )
    existing_sections = cursor.fetchall()
    existing_titles = {}
    for number, title in existing_sections:
        normalized_number = str(number)
        if normalized_number in existing_titles:
            raise RuntimeError(
                f"Duplicate section {normalized_number!r} exists "
                f"for {source_file!r}."
            )
        existing_titles[normalized_number] = title

    mismatched_sections = {
        number: title
        for number, title in existing_titles.items()
        if section_titles.get(number) != title
    }
    if mismatched_sections:
        raise RuntimeError(
            "Existing document sections differ from the source structure; "
            "no records were changed."
        )

    for number, title in section_titles.items():
        if number not in existing_titles:
            cursor.execute(
                """
                INSERT INTO sections (document_id, section_number, title)
                VALUES (%s, %s, %s);
                """,
                (document_id, number, title),
            )

    return document_id

# ============================================================
# Load JSON data
# ============================================================

def load_json_files(programme="UG"):
    """Load and validate one programme's ordinance chunks and vectors."""

    print("Loading knowledge-base files...")
    corpus = validate_files(programme)

    with open(corpus["chunks"], "r", encoding="utf-8") as file:
        chunks_data = json.load(file)

    with open(corpus["embeddings"], "r", encoding="utf-8") as file:
        embeddings_data = json.load(file)

    # --------------------------------------------------------
    # Validate top-level structure
    # --------------------------------------------------------

    required_chunk_keys = {"document", "chunks", "validation"}
    required_embedding_keys = {
        "document",
        "embedding_model",
        "embedding_dimension",
        "normalized",
        "total_chunks",
        "generated_at",
        "chunks",
    }

    missing_chunk_keys = required_chunk_keys - chunks_data.keys()

    if missing_chunk_keys:
        raise ValueError(
            f"Missing keys in chunks file: {missing_chunk_keys}"
        )

    missing_embedding_keys = (
        required_embedding_keys - embeddings_data.keys()
    )

    if missing_embedding_keys:
        raise ValueError(
            f"Missing keys in embeddings file: {missing_embedding_keys}"
        )

    chunks = chunks_data["chunks"]
    embedding_chunks = embeddings_data["chunks"]

    print(f"Chunks loaded: {len(chunks)}")
    print(f"Embeddings loaded: {len(embedding_chunks)}")

    if len(chunks) != len(embedding_chunks):
        raise ValueError(
            f"Chunk/embedding count mismatch: "
            f"{len(chunks)} chunks vs "
            f"{len(embedding_chunks)} embeddings."
        )

    # --------------------------------------------------------
    # Validate embedding metadata
    # --------------------------------------------------------

    embedding_dimension = embeddings_data["embedding_dimension"]

    if embedding_dimension != EMBEDDING_DIMENSION:
        raise ValueError(
            f"Expected embedding dimension {EMBEDDING_DIMENSION}, "
            f"but found {embedding_dimension}."
        )

    embedding_model = embeddings_data["embedding_model"]
    if embedding_model != EMBEDDING_MODEL:
        raise ValueError(
            f"Embedding model {embedding_model!r} does not match "
            f"the configured model {EMBEDDING_MODEL!r}."
        )

    source_file = chunks_data["document"].get("source_file")
    if (
        source_file != corpus["source_file"]
        or embeddings_data["document"].get("source_file") != source_file
        or any(
            item.get("source_file") != source_file
            for item in chunks
        )
    ):
        raise ValueError(
            "Ordinance chunk and embedding source metadata do not match "
            "the selected programme source."
        )
    if len(chunks) != embeddings_data["total_chunks"]:
        raise ValueError(
            "Embedding total_chunks metadata does not match the "
            "available vectors."
        )

    chunk_ids = [item.get("chunk_id") for item in chunks]
    embedding_ids = [item.get("chunk_id") for item in embedding_chunks]
    if (
        any(not item for item in chunk_ids)
        or len(set(chunk_ids)) != len(chunk_ids)
        or set(chunk_ids) != set(embedding_ids)
        or len(set(embedding_ids)) != len(embedding_ids)
    ):
        raise ValueError(
            "Ordinance chunks and embeddings must have matching, unique IDs."
        )

    print(f"Embedding model: {embedding_model}")
    print(f"Embedding dimension: {embedding_dimension}")
    print(f"Normalized: {embeddings_data['normalized']}")

    return (
        chunks,
        embedding_chunks,
        embedding_model,
        embedding_dimension,
    )


# ============================================================
# Database connection
# ============================================================

def connect_database():
    """Connect to the DepartmentAI PostgreSQL database."""

    settings = get_database_settings()
    if settings.environment not in LOCAL_DATABASES:
        raise RuntimeError(
            "Knowledge-base ingestion is restricted to an explicit "
            "loopback development or test database profile."
        )
    DB_NAME = settings.database
    DB_USER = settings.user
    DB_HOST = settings.host
    DB_PORT = settings.port
    DB_PASSWORD = settings.password

    if not DB_PASSWORD:
        raise RuntimeError(
            "DEPARTMENTAI_DB_PASSWORD environment variable is not set.\n"
            "Set it in PowerShell before running the ingestion script."
        )

    print("\nConnecting to PostgreSQL...")

    connection = psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
    )

    print("Database connection successful.")

    return connection


# ============================================================
# Build embedding lookup
# ============================================================

def build_embedding_lookup(embedding_chunks):
    """
    Build:

        chunk_id -> embedding vector

    This allows every chunk to be matched with its
    corresponding embedding.
    """

    embedding_lookup = {}

    for item in embedding_chunks:

        if "chunk_id" not in item:
            raise ValueError(
                "An embedding record is missing 'chunk_id'."
            )

        if "embedding" not in item:
            raise ValueError(
                f"Embedding missing for chunk {item['chunk_id']}."
            )

        chunk_id = item["chunk_id"]
        embedding = item["embedding"]

        if len(embedding) != EMBEDDING_DIMENSION:
            raise ValueError(
                f"Invalid embedding dimension for {chunk_id}: "
                f"{len(embedding)}"
            )

        if chunk_id in embedding_lookup:
            raise ValueError(
                f"Duplicate embedding found for chunk: {chunk_id}"
            )

        embedding_lookup[chunk_id] = embedding

    return embedding_lookup


# ============================================================
# Main ingestion
# ============================================================

def ingest_knowledge_base(programme="UG"):

    normalized_programme = normalize_programme(programme)
    corpus = validate_files(normalized_programme)
    print("Ingestion status: PROCESSING")

    print("========================================")
    print("DepartmentAI Knowledge Base Ingestion")
    print("========================================")

    # --------------------------------------------------------
    # 1. Validate files
    # --------------------------------------------------------

    # --------------------------------------------------------
    # 2. Load JSON files
    # --------------------------------------------------------

    (
        chunks,
        embedding_chunks,
        embedding_model,
        embedding_dimension,
    ) = load_json_files(normalized_programme)

    # --------------------------------------------------------
    # 3. Build embedding lookup
    # --------------------------------------------------------

    embedding_lookup = build_embedding_lookup(
        embedding_chunks
    )

    print(
        f"Embedding lookup created: "
        f"{len(embedding_lookup)} records"
    )

    # --------------------------------------------------------
    # 4. Connect to database
    # --------------------------------------------------------

    connection = connect_database()

    cursor = None

    try:
        cursor = connection.cursor()

        # ----------------------------------------------------
        # 5. Ensure the source document and sections are indexed
        # ----------------------------------------------------

        chunks_data = json.loads(
            Path(corpus["chunks"]).read_text(encoding="utf-8")
        )
        source_file = chunks_data["document"]["source_file"]
        registered_source = verify_registered_source(
            normalized_programme,
            source_file,
            corpus["pdf"],
        )
        source_sha256 = registered_source["source_sha256"].lower()
        source_version = registered_source["source_version"]
        source_id = registered_source["source_id"]
        cursor.execute(
            "SELECT id FROM documents WHERE file_name = %s;",
            (source_file,),
        )
        existing_document = cursor.fetchone()
        if existing_document is not None:
            existing_document_id = existing_document[0]
            cursor.execute(
                """
                SELECT
                    COUNT(*),
                    COUNT(DISTINCT metadata->>'chunk_id'),
                    COUNT(*) FILTER (
                        WHERE metadata->>'source_id' = %s
                          AND metadata->>'source_version' = %s
                          AND metadata->>'source_sha256' = %s
                          AND metadata->>'embedding_model' = %s
                          AND metadata->>'approval_status' = %s
                          AND metadata->>'programme' = %s
                          AND metadata->>'source_file' = %s
                          AND metadata->>'embedding_dimension' = %s
                    )
                FROM knowledge_chunks
                WHERE document_id = %s;
                """,
                (
                    source_id,
                    source_version,
                    source_sha256,
                    embedding_model,
                    registered_source["approval_status"],
                    normalized_programme,
                    source_file,
                    str(embedding_dimension),
                    existing_document_id,
                ),
            )
            indexed_count, unique_chunk_count, current_count = cursor.fetchone()
            cursor.execute(
                """
                SELECT metadata->>'chunk_id'
                FROM knowledge_chunks
                WHERE document_id = %s;
                """,
                (existing_document_id,),
            )
            existing_ids = {
                chunk_id for (chunk_id,) in cursor.fetchall() if chunk_id
            }
            expected_ids = {item["chunk_id"] for item in chunks}
            if (
                indexed_count == len(chunks)
                and unique_chunk_count == indexed_count
                and current_count == indexed_count
                and existing_ids == expected_ids
            ):
                connection.commit()
                print(
                    f"Knowledge-base ingestion unchanged: "
                    f"{normalized_programme} ({indexed_count} verified chunks)."
                )
                print("Ingestion status: INDEXED")
                return {
                    "status": "INDEXED",
                    "programme": normalized_programme,
                    "source_id": source_id,
                    "source_version": source_version,
                    "chunk_count": indexed_count,
                    "unchanged": True,
                }
            cursor.execute(
                "DELETE FROM documents WHERE id = %s;",
                (existing_document_id,),
            )

        document_id = ensure_document_sections(
            cursor,
            source_file,
            Path(corpus["structure"]),
        )

        print(f"Document ID: {document_id}")

        # ----------------------------------------------------
        # 6. Load section references
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT id, section_number
            FROM sections
            WHERE document_id = %s
            ORDER BY id;
            """,
            (document_id,),
        )

        section_rows = cursor.fetchall()

        section_lookup = {
            str(section_number): section_id
            for section_id, section_number in section_rows
        }

        print(f"Sections found: {len(section_lookup)}")

        structure_data = json.loads(
            Path(corpus["structure"]).read_text(encoding="utf-8")
        )
        expected_sections = {
            str(section["number"])
            for section in structure_data["sections"]
        }
        if set(section_lookup) != expected_sections:
            raise RuntimeError(
                "Indexed section numbers do not match the selected "
                "ordinance structure."
            )

        # ----------------------------------------------------
        # 7. Insert chunks
        # ----------------------------------------------------

        print("\nStarting ingestion...\n")

        inserted = 0

        for chunk in chunks:

            chunk_id = chunk["chunk_id"]

            # ------------------------------------------------
            # Match embedding
            # ------------------------------------------------

            if chunk_id not in embedding_lookup:
                raise ValueError(
                    f"No embedding found for chunk: {chunk_id}"
                )

            embedding = embedding_lookup[chunk_id]

            # ------------------------------------------------
            # Match section
            # ------------------------------------------------

            section_number = chunk.get("section")

            section_id = None

            if section_number is not None:
                section_id = section_lookup.get(str(section_number))

                if section_id is None:
                    raise ValueError(
                        f"No database section found for "
                        f"section {section_number} "
                        f"(chunk {chunk_id})."
                    )

            # ------------------------------------------------
            # Forms
            # ------------------------------------------------

            forms_referenced = chunk.get(
                "forms_referenced", []
            )

            form_id = (
                forms_referenced[0]
                if forms_referenced
                else None
            )

            # ------------------------------------------------
            # Metadata
            # ------------------------------------------------

            metadata = {
                "chunk_id": chunk_id,
                "programme": normalized_programme,
                "source_id": source_id,
                "source_version": source_version,
                "source_sha256": source_sha256,
                "approval_status": registered_source["approval_status"],
                "document": chunk.get("document"),
                "source_file": chunk.get("source_file"),
                "section_title": chunk.get("section_title"),
                "clause_title": chunk.get("clause_title"),
                "chunk_count": chunk.get("chunk_count"),
                "character_count": chunk.get("character_count"),
                "word_count": chunk.get("word_count"),
                "global_index": chunk.get("global_index"),
                "embedding_model": embedding_model,
                "embedding_dimension": embedding_dimension,
                "forms_referenced": forms_referenced,
            }

            # ------------------------------------------------
            # Convert embedding to pgvector format
            # ------------------------------------------------

            embedding_string = (
                "["
                + ",".join(str(value) for value in embedding)
                + "]"
            )

            # ------------------------------------------------
            # Insert record
            # ------------------------------------------------

            cursor.execute(
                """
                INSERT INTO knowledge_chunks (
                    document_id,
                    section_id,
                    chunk_index,
                    chunk_type,
                    clause_number,
                    chunk_text,
                    page_start,
                    page_end,
                    form_id,
                    metadata,
                    embedding
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s::vector
                );
                """,
                (
                    document_id,
                    section_id,
                    chunk.get("chunk_index"),
                    chunk.get("content_type"),
                    chunk.get("clause"),
                    chunk.get("text"),
                    chunk.get("page_start"),
                    chunk.get("page_end"),
                    form_id,
                    Json(metadata),
                    embedding_string,
                ),
            )

            inserted += 1

            if inserted % 25 == 0:
                print(
                    f"Inserted {inserted}/{len(chunks)} chunks..."
                )

        # ----------------------------------------------------
        # 9. Commit transaction
        # ----------------------------------------------------

        connection.commit()

        print("\n========================================")
        print("Knowledge-base ingestion successful!")
        print("========================================")
        print(f"Document ID:        {document_id}")
        print(f"Chunks inserted:    {inserted}")
        print(f"Embedding dimension:{embedding_dimension}")
        print(f"Embedding model:    {embedding_model}")
        print("========================================")
        print("Ingestion status: INDEXED")
        return {
            "status": "INDEXED",
            "programme": normalized_programme,
            "source_id": source_id,
            "source_version": source_version,
            "chunk_count": inserted,
            "unchanged": False,
        }

    except Exception:
        connection.rollback()

        print("\n========================================")
        print("ERROR: Ingestion failed.")
        print("========================================")
        print("All database changes have been rolled back.")
        print("Ingestion status: FAILED")

        raise

    finally:

        if cursor is not None:
            cursor.close()

        connection.close()

        print("Database connection closed.")


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Ingest one approved ordinance corpus into an explicit local "
            "development or test DB."
        )
    )
    parser.add_argument(
        "--programme",
        choices=tuple(PROGRAMME_CORPORA),
        default="UG",
        help="Programme corpus to ingest (default: UG).",
    )
    arguments = parser.parse_args()
    ingest_knowledge_base(arguments.programme)
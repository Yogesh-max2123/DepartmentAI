import json
import os
from pathlib import Path

import psycopg2
from psycopg2.extras import Json


# ============================================================
# Configuration
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

CHUNKS_FILE = (
    PROJECT_ROOT
    / "documents"
    / "ug"
    / "processed"
    / "ug_ordinance_chunks.json"
)

EMBEDDINGS_FILE = (
    PROJECT_ROOT
    / "documents"
    / "ug"
    / "processed"
    / "ug_ordinance_embeddings.json"
)

DB_NAME = "departmentai"
DB_USER = "postgres"
DB_HOST = "localhost"
DB_PORT = 5432

# PostgreSQL password is read from the environment.
DB_PASSWORD = os.getenv("DEPARTMENTAI_DB_PASSWORD")


# ============================================================
# File validation
# ============================================================

def validate_files():
    """Check that the required JSON files exist."""

    if not CHUNKS_FILE.exists():
        raise FileNotFoundError(
            f"Chunks file not found:\n{CHUNKS_FILE}"
        )

    if not EMBEDDINGS_FILE.exists():
        raise FileNotFoundError(
            f"Embeddings file not found:\n{EMBEDDINGS_FILE}"
        )


# ============================================================
# Load JSON data
# ============================================================

def load_json_files():
    """Load and validate the chunks and embeddings JSON files."""

    print("Loading knowledge-base files...")

    with open(CHUNKS_FILE, "r", encoding="utf-8") as file:
        chunks_data = json.load(file)

    with open(EMBEDDINGS_FILE, "r", encoding="utf-8") as file:
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

    # --------------------------------------------------------
    # Validate counts
    # --------------------------------------------------------

    if len(chunks) != 246:
        raise ValueError(
            f"Expected 246 chunks, but found {len(chunks)}."
        )

    if len(embedding_chunks) != 246:
        raise ValueError(
            f"Expected 246 embeddings, but found {len(embedding_chunks)}."
        )

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

    if embedding_dimension != 384:
        raise ValueError(
            f"Expected embedding dimension 384, "
            f"but found {embedding_dimension}."
        )

    embedding_model = embeddings_data["embedding_model"]

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

        if len(embedding) != 384:
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

def ingest_knowledge_base():

    print("========================================")
    print("DepartmentAI Knowledge Base Ingestion")
    print("========================================")

    # --------------------------------------------------------
    # 1. Validate files
    # --------------------------------------------------------

    validate_files()

    # --------------------------------------------------------
    # 2. Load JSON files
    # --------------------------------------------------------

    (
        chunks,
        embedding_chunks,
        embedding_model,
        embedding_dimension,
    ) = load_json_files()

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
        # 5. Find the UG Ordinance document
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT id
            FROM documents
            WHERE file_name = %s
            ORDER BY id
            LIMIT 1;
            """,
            ("UG Ordinance.pdf",),
        )

        document_row = cursor.fetchone()

        if document_row is None:
            raise RuntimeError(
                "UG Ordinance document was not found "
                "in the documents table."
            )

        document_id = document_row[0]

        print(f"Document ID: {document_id}")

        # ----------------------------------------------------
        # 6. Load sections
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

        if len(section_lookup) != 13:
            raise RuntimeError(
                f"Expected 13 sections, "
                f"but found {len(section_lookup)}."
            )

        # ----------------------------------------------------
        # 7. Prevent duplicate ingestion
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM knowledge_chunks
            WHERE document_id = %s;
            """,
            (document_id,),
        )

        existing_count = cursor.fetchone()[0]

        if existing_count > 0:
            raise RuntimeError(
                f"knowledge_chunks already contains "
                f"{existing_count} records for document "
                f"ID {document_id}.\n"
                "Ingestion stopped to prevent duplicates."
            )

        # ----------------------------------------------------
        # 8. Insert chunks
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

    except Exception:
        connection.rollback()

        print("\n========================================")
        print("ERROR: Ingestion failed.")
        print("========================================")
        print("All database changes have been rolled back.")

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
    ingest_knowledge_base()
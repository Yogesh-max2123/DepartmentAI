import argparse
import json
import os
import sys
from pathlib import Path

import psycopg2
from psycopg2.extras import Json, execute_batch
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# Configuration
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

CHUNKS_FILE = (
    PROJECT_ROOT
    / "documents"
    / "mtech"
    / "processed"
    / "mtech_ordinance_chunks.json"
)

EMBEDDINGS_FILE = (
    PROJECT_ROOT
    / "documents"
    / "mtech"
    / "processed"
    / "mtech_ordinance_embeddings.json"
)

SOURCE_FILE_NAME = "Ordinances for Masters Programme 2023.pdf"

# Database Configuration with environment fallbacks
DB_NAME = os.getenv("DEPARTMENTAI_DB_NAME", "departmentai")
DB_USER = os.getenv("DEPARTMENTAI_DB_USER", "postgres")
DB_HOST = os.getenv("DEPARTMENTAI_DB_HOST", "localhost")
DB_PORT = int(os.getenv("DEPARTMENTAI_DB_PORT", "5432"))
DB_PASSWORD = os.getenv("DEPARTMENTAI_DB_PASSWORD")


# ============================================================
# File validation
# ============================================================

def validate_files():
    """Check that the required JSON files exist."""
    if not CHUNKS_FILE.exists():
        raise FileNotFoundError(f"Chunks file not found:\n{CHUNKS_FILE}")

    if not EMBEDDINGS_FILE.exists():
        raise FileNotFoundError(f"Embeddings file not found:\n{EMBEDDINGS_FILE}")


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

    # Validate top-level keys
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
        raise ValueError(f"Missing keys in chunks file: {missing_chunk_keys}")

    missing_embedding_keys = required_embedding_keys - embeddings_data.keys()
    if missing_embedding_keys:
        raise ValueError(f"Missing keys in embeddings file: {missing_embedding_keys}")

    chunks = chunks_data["chunks"]
    embedding_chunks = embeddings_data["chunks"]

    print(f"Chunks loaded: {len(chunks)}")
    print(f"Embeddings loaded: {len(embedding_chunks)}")

    # Strict count integrity check between chunks and embeddings
    if len(chunks) == 0:
        raise ValueError("Chunks file contains 0 chunks.")

    if len(chunks) != len(embedding_chunks):
        raise ValueError(
            f"Chunk/embedding count mismatch: {len(chunks)} chunks vs {len(embedding_chunks)} embeddings."
        )

    # Validate embedding metadata
    embedding_dimension = embeddings_data["embedding_dimension"]
    if embedding_dimension != 384:
        raise ValueError(
            f"Expected embedding dimension 384, but found {embedding_dimension}."
        )

    embedding_model = embeddings_data["embedding_model"]

    print(f"Embedding model: {embedding_model}")
    print(f"Embedding dimension: {embedding_dimension}")
    print(f"Normalized: {embeddings_data.get('normalized', False)}")

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
            "Set it in your .env file or environment before running."
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
    """Build: chunk_id -> embedding vector mapping."""
    embedding_lookup = {}

    for item in embedding_chunks:
        chunk_id = item.get("chunk_id")
        embedding = item.get("embedding")

        if not chunk_id:
            raise ValueError("An embedding record is missing 'chunk_id'.")

        if embedding is None:
            raise ValueError(f"Embedding missing for chunk {chunk_id}.")

        if len(embedding) != 384:
            raise ValueError(
                f"Invalid embedding dimension for {chunk_id}: {len(embedding)}"
            )

        if chunk_id in embedding_lookup:
            raise ValueError(f"Duplicate embedding found for chunk: {chunk_id}")

        embedding_lookup[chunk_id] = embedding

    return embedding_lookup


# ============================================================
# Main ingestion
# ============================================================

def ingest_knowledge_base(replace_existing: bool = False):
    print("========================================")
    print("DepartmentAI Knowledge Base Ingestion")
    print("========================================")

    # 1. Validate files
    validate_files()

    # 2. Load JSON files
    (
        chunks,
        embedding_chunks,
        embedding_model,
        embedding_dimension,
    ) = load_json_files()

    # 3. Build embedding lookup
    embedding_lookup = build_embedding_lookup(embedding_chunks)
    print(f"Embedding lookup created: {len(embedding_lookup)} records")

    # 4. Connect to database
    connection = connect_database()
    cursor = None

    try:
        cursor = connection.cursor()

        # Pre-flight check: Verify pgvector extension
        cursor.execute(
            "SELECT extversion FROM pg_extension WHERE extname = 'vector';"
        )
        if not cursor.fetchone():
            raise RuntimeError(
                "The 'vector' extension is not enabled in this database. Run 'CREATE EXTENSION vector;' first."
            )

        # 5. Find the source document
        cursor.execute(
            """
            SELECT id
            FROM documents
            WHERE file_name = %s
            ORDER BY id
            LIMIT 1;
            """,
            (SOURCE_FILE_NAME,),
        )
        document_row = cursor.fetchone()

        if document_row is None:
            raise RuntimeError(
                f"Document '{SOURCE_FILE_NAME}' was not found in the 'documents' table. "
                "Please insert the document record before running ingestion."
            )

        document_id = document_row[0]
        print(f"Document ID: {document_id}")

        # 6. Load sections mapping
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
            str(sec_num): sec_id for sec_id, sec_num in section_rows
        }
        print(f"Sections mapped: {len(section_lookup)}")

        # 7. Check for existing chunks and handle replace
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
            if replace_existing:
                print(f"Replacing existing {existing_count} chunks for Document ID {document_id}...")
                cursor.execute(
                    "DELETE FROM knowledge_chunks WHERE document_id = %s;",
                    (document_id,),
                )
            else:
                raise RuntimeError(
                    f"'knowledge_chunks' already contains {existing_count} records for document ID {document_id}.\n"
                    "Ingestion stopped to prevent duplicates. Use '--replace' to overwrite."
                )

        # 8. Prepare batch records
        print("\nPreparing batch records for insertion...")
        records_to_insert = []

        for chunk in chunks:
            chunk_id = chunk["chunk_id"]

            if chunk_id not in embedding_lookup:
                raise ValueError(f"No embedding found for chunk: {chunk_id}")

            embedding = embedding_lookup[chunk_id]
            section_number = chunk.get("section")
            section_id = None

            if section_number is not None:
                section_id = section_lookup.get(str(section_number))
                if section_id is None:
                    raise ValueError(
                        f"No database section found for section {section_number} (chunk {chunk_id})."
                    )

            forms_referenced = chunk.get("forms_referenced", [])
            form_id = chunk.get("form_id")
            if form_id is None and forms_referenced:
                form_id = forms_referenced[0]

            metadata = {
                "chunk_id": chunk_id,
                "document": chunk.get("document"),
                "source_file": chunk.get("source_file"),
                "section_title": chunk.get("section_title"),
                "clause_title": chunk.get("clause_title"),
                "form_title": chunk.get("form_title"),
                "clause_references": chunk.get("clause_references"),
                "chunk_count": chunk.get("chunk_count"),
                "character_count": chunk.get("character_count"),
                "word_count": chunk.get("word_count"),
                "global_index": chunk.get("global_index"),
                "embedding_model": embedding_model,
                "embedding_dimension": embedding_dimension,
                "forms_referenced": forms_referenced,
            }

            embedding_string = "[" + ",".join(str(val) for val in embedding) + "]"

            records_to_insert.append(
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
                )
            )

        # 9. Batch Insertion via execute_batch
        insert_sql = """
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
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector);
        """

        print(f"Executing batch insert for {len(records_to_insert)} chunks...")
        execute_batch(cursor, insert_sql, records_to_insert, page_size=100)

        # 10. Automatically ensure Vector Index (HNSW) exists
        print("Ensuring HNSW vector index on 'knowledge_chunks'...")
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_embedding
            ON knowledge_chunks
            USING hnsw (embedding vector_cosine_ops);
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_doc_sec
            ON knowledge_chunks (document_id, section_id);
            """
        )

        connection.commit()

        print("\n========================================")
        print("Knowledge-base ingestion successful!")
        print("========================================")
        print(f"Document ID:         {document_id}")
        print(f"Chunks inserted:     {len(records_to_insert)}")
        print(f"Embedding dimension: {embedding_dimension}")
        print(f"Embedding model:     {embedding_model}")
        print("========================================")

    except Exception:
        if connection:
            connection.rollback()
        print("\n========================================")
        print("ERROR: Ingestion failed.")
        print("========================================")
        print("All database changes have been rolled back.")
        raise

    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()
        print("Database connection closed.")


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Ingest ordinance chunks and embeddings into PostgreSQL."
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Overwrite existing chunks for this document instead of halting.",
    )
    args = parser.parse_args()

    ingest_knowledge_base(replace_existing=args.replace)
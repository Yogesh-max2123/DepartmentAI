import os
from pathlib import Path

from backend.database.connection import get_connection


# Base directory for application documents
BASE_DOCUMENTS_DIR = Path("documents") / "applications"


# Allowed document types for the initial implementation
ALLOWED_EXTENSIONS = {
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
}


def upload_document(
    application_id,
    file_name,
    file_content,
    document_type=None,
    mime_type=None,
):
    """
    Store an application document and record its metadata.

    The physical file is stored on the local filesystem.
    The database stores only the document metadata and file path.
    """

    conn = get_connection()

    try:
        # --------------------------------------------------------
        # 1. Verify that the application exists
        # --------------------------------------------------------
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT application_number
                FROM applications
                WHERE id = %s;
                """,
                (application_id,),
            )

            application = cursor.fetchone()

            if application is None:
                raise ValueError(
                    f"Application with id {application_id} does not exist."
                )

            application_number = application[0]

        # --------------------------------------------------------
        # 2. Validate file extension
        # --------------------------------------------------------
        extension = Path(file_name).suffix.lower()

        if extension not in ALLOWED_EXTENSIONS:
            raise ValueError(
                f"Unsupported document type: {extension}. "
                f"Allowed types: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            )

        # --------------------------------------------------------
        # 3. Create application-specific directory
        # --------------------------------------------------------
        application_directory = (
            BASE_DOCUMENTS_DIR / application_number
        )

        application_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        # --------------------------------------------------------
        # 4. Prevent path traversal
        # --------------------------------------------------------
        safe_file_name = Path(file_name).name

        if not safe_file_name:
            raise ValueError("Invalid file name.")

        file_path = application_directory / safe_file_name

        # --------------------------------------------------------
        # 5. Store the physical file
        # --------------------------------------------------------
        with open(file_path, "wb") as file:
            file.write(file_content)

        file_size = os.path.getsize(file_path)

        # --------------------------------------------------------
        # 6. Store document metadata in database
        # --------------------------------------------------------
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO application_documents (
                    application_id,
                    file_name,
                    document_type,
                    file_path,
                    file_size,
                    mime_type,
                    upload_status
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING
                    id,
                    application_id,
                    file_name,
                    document_type,
                    file_path,
                    file_size,
                    mime_type,
                    upload_status,
                    uploaded_at;
                """,
                (
                    application_id,
                    safe_file_name,
                    document_type,
                    str(file_path),
                    file_size,
                    mime_type,
                    "UPLOADED",
                ),
            )

            document = cursor.fetchone()

        conn.commit()

        return {
            "id": document[0],
            "application_id": document[1],
            "file_name": document[2],
            "document_type": document[3],
            "file_path": document[4],
            "file_size": document[5],
            "mime_type": document[6],
            "upload_status": document[7],
            "uploaded_at": document[8],
        }

    except Exception:
        conn.rollback()

        # If database insertion fails after the file was created,
        # remove the physical file to avoid an orphaned document.
        if "file_path" in locals() and file_path.exists():
            file_path.unlink()

        raise

    finally:
        conn.close()


def get_application_documents(application_id):
    """
    Retrieve all documents belonging to an application.
    """

    conn = get_connection()

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    application_id,
                    file_name,
                    document_type,
                    file_path,
                    file_size,
                    mime_type,
                    upload_status,
                    uploaded_at
                FROM application_documents
                WHERE application_id = %s
                ORDER BY uploaded_at;
                """,
                (application_id,),
            )

            documents = cursor.fetchall()

            return [
                {
                    "id": document[0],
                    "application_id": document[1],
                    "file_name": document[2],
                    "document_type": document[3],
                    "file_path": document[4],
                    "file_size": document[5],
                    "mime_type": document[6],
                    "upload_status": document[7],
                    "uploaded_at": document[8],
                }
                for document in documents
            ]

    finally:
        conn.close()
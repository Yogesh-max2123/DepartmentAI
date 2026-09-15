from pathlib import Path

from backend.database.connection import get_connection


ALLOWED_EXTENSIONS = {
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
}


def validate_document(document_id):
    """
    Validate an uploaded application document.

    Checks:
    - Database record exists
    - Physical file exists
    - File is not empty
    - File extension is supported
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
                    file_path,
                    file_size,
                    mime_type
                FROM application_documents
                WHERE id = %s;
                """,
                (document_id,),
            )

            document = cursor.fetchone()

        if document is None:
            return {
                "valid": False,
                "document_id": document_id,
                "reason": "Document does not exist."
            }

        file_path = Path(document[3])
        file_size = document[4]
        extension = file_path.suffix.lower()

        if not file_path.exists():
            return {
                "valid": False,
                "document_id": document_id,
                "reason": "Physical file does not exist."
            }

        if file_size <= 0:
            return {
                "valid": False,
                "document_id": document_id,
                "reason": "Document file is empty."
            }

        if extension not in ALLOWED_EXTENSIONS:
            return {
                "valid": False,
                "document_id": document_id,
                "reason": f"Unsupported file extension: {extension}"
            }

        return {
            "valid": True,
            "document_id": document[0],
            "application_id": document[1],
            "file_name": document[2],
            "file_size": file_size,
            "mime_type": document[5],
            "reason": "Document passed basic validation."
        }

    finally:
        conn.close()
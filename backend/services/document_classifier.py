from backend.database.connection import get_connection


ALLOWED_DOCUMENT_TYPES = {
    "MARKSHEET",
    "IDENTITY_PROOF",
    "APPLICATION_FORM",
    "CERTIFICATE",
    "OTHER",
}


def classify_document(document_id):
    """
    Classify an uploaded application document.

    For the initial implementation, classification uses the
    document type provided during upload.
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
                    document_type
                FROM application_documents
                WHERE id = %s;
                """,
                (document_id,),
            )

            document = cursor.fetchone()

        if document is None:
            raise ValueError(
                f"Document with id {document_id} does not exist."
            )

        document_type = document[3]

        if document_type:
            normalized_type = document_type.strip().upper()
        else:
            normalized_type = "OTHER"

        if normalized_type not in ALLOWED_DOCUMENT_TYPES:
            normalized_type = "OTHER"

        # Update the classified document type
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE application_documents
                SET document_type = %s
                WHERE id = %s;
                """,
                (normalized_type, document_id),
            )

        conn.commit()

        return {
            "document_id": document[0],
            "application_id": document[1],
            "file_name": document[2],
            "document_type": normalized_type,
        }

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()
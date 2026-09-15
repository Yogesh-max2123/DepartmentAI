from pathlib import Path

import fitz

from backend.database.connection import get_connection


def extract_document_text(document_id):
    """
    Extract text from an uploaded PDF document and store the result
    in the document_extractions table.
    """

    conn = get_connection()

    try:
        # --------------------------------------------------------
        # 1. Get document information
        # --------------------------------------------------------
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    file_path,
                    mime_type
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

        file_path = Path(document[1])
        mime_type = document[2]

        # --------------------------------------------------------
        # 2. Validate file
        # --------------------------------------------------------
        if not file_path.exists():
            raise ValueError("Document file does not exist.")

        if mime_type != "application/pdf":
            raise ValueError(
                "Text extraction currently supports PDF documents only."
            )

        # --------------------------------------------------------
        # 3. Extract text from PDF
        # --------------------------------------------------------
        pdf = fitz.open(file_path)

        pages = []

        for page in pdf:
            pages.append(page.get_text())

        pdf.close()

        extracted_text = "\n".join(pages).strip()

        if not extracted_text:
            extraction_status = "NO_TEXT"
            confidence = 0.0
        else:
            extraction_status = "COMPLETED"
            confidence = 1.0

        # --------------------------------------------------------
        # 4. Store extraction result
        # --------------------------------------------------------
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO document_extractions (
                    application_document_id,
                    extracted_text,
                    extraction_status,
                    confidence
                )
                VALUES (%s, %s, %s, %s)
                RETURNING id;
                """,
                (
                    document_id,
                    extracted_text,
                    extraction_status,
                    confidence,
                ),
            )

            extraction_id = cursor.fetchone()[0]

        conn.commit()

        return {
            "extraction_id": extraction_id,
            "document_id": document_id,
            "extraction_status": extraction_status,
            "confidence": confidence,
            "text_length": len(extracted_text),
            "extracted_text": extracted_text,
        }

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()
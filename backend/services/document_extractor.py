from pathlib import Path

import fitz

from backend.database.connection import get_connection

MAX_DOCUMENT_SIZE_BYTES = 10 * 1024 * 1024
MAX_PDF_PAGES = 100
MAX_EXTRACTED_TEXT_CHARS = 1_000_000


class DocumentExtractionNotFoundError(ValueError):
    """Raised when a document is not part of the requested application."""


def extract_document_text(document_id, application_id):
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
                WHERE id = %s AND application_id = %s;
                """,
                (document_id, application_id),
            )

            document = cursor.fetchone()

        if document is None:
            raise DocumentExtractionNotFoundError(
                "Document does not belong to this application."
            )

        file_path = Path(document[1])
        mime_type = document[2]

        # --------------------------------------------------------
        # 2. Validate file
        # --------------------------------------------------------
        if not file_path.exists():
            raise ValueError("Document file does not exist.")
        if not file_path.is_file():
            raise ValueError("Document file is invalid.")
        if file_path.stat().st_size > MAX_DOCUMENT_SIZE_BYTES:
            raise ValueError(
                "PDF file exceeds the 10 MiB text-extraction limit."
            )

        if file_path.suffix.lower() != ".pdf" or mime_type not in (
            None,
            "",
            "application/octet-stream",
            "application/pdf",
        ):
            raise ValueError(
                "Text extraction currently supports PDF documents only."
            )

        # --------------------------------------------------------
        # 3. Extract text from PDF
        # --------------------------------------------------------
        try:
            with fitz.open(file_path) as pdf:
                if len(pdf) > MAX_PDF_PAGES:
                    raise ValueError(
                        f"PDF exceeds the {MAX_PDF_PAGES}-page "
                        "text-extraction limit."
                    )
                pages = []
                extracted_characters = 0
                for page in pdf:
                    page_text = page.get_text()
                    extracted_characters += len(page_text) + (
                        1 if pages else 0
                    )
                    if extracted_characters > MAX_EXTRACTED_TEXT_CHARS:
                        raise ValueError(
                            "PDF text exceeds the "
                            f"{MAX_EXTRACTED_TEXT_CHARS:,}-character "
                            "extraction limit."
                        )
                    pages.append(page_text)
        except (fitz.FileDataError, fitz.EmptyFileError, RuntimeError) as error:
            raise ValueError("PDF file is corrupt or cannot be read.") from error

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
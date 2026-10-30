import re
from pathlib import Path
from typing import Pattern

import fitz
from PIL import Image, UnidentifiedImageError

from backend.database.connection import get_connection

ALLOWED_DOCUMENT_TYPES = {
    "MARKSHEET",
    "IDENTITY_PROOF",
    "APPLICATION_FORM",
    "CERTIFICATE",
    "OTHER",
}

MIME_TYPES_BY_EXTENSION = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}

CATEGORY_PATTERNS: dict[str, tuple[Pattern[str], ...]] = {
    "MARKSHEET": (
        re.compile(
            r"\b(?:marksheet|mark\s+sheet|statement\s+of\s+marks|"
            r"academic\s+transcript|transcript\s+of\s+records|"
            r"grade\s+(?:sheet|report))\b",
            re.IGNORECASE,
        ),
        re.compile(r"\b(?:cgpa|sgpa)\b", re.IGNORECASE),
    ),
    "IDENTITY_PROOF": (
        re.compile(
            r"\b(?:identity\s+(?:proof|card)|national\s+id|passport|"
            r"voter(?:'s)?\s+id|driving\s+licen[cs]e|"
            r"driver'?s\s+licen[cs]e|aadhaar|uidai)\b",
            re.IGNORECASE,
        ),
    ),
    "APPLICATION_FORM": (
        re.compile(r"\bapplication\s+form\b", re.IGNORECASE),
        re.compile(r"\bapplication\s+for\b", re.IGNORECASE),
    ),
    "CERTIFICATE": (
        re.compile(
            r"\b(?:certificate|certify\s+that|certified\s+that|"
            r"degree\s+awarded|provisional\s+degree|"
            r"bonafide|bona\s+fide)\b",
            re.IGNORECASE,
        ),
    ),
}


class DocumentNotFoundError(ValueError):
    """Raised when a document is missing or outside the requested application."""


def _validate_document_file(
    file_path: Path,
    file_name: str,
    mime_type: str | None,
) -> tuple[str, str]:
    extension = Path(file_name).suffix.lower()
    if extension not in MIME_TYPES_BY_EXTENSION:
        raise ValueError(
            f"Unsupported document extension: {extension or '(none)'}. "
            f"Supported extensions: {', '.join(MIME_TYPES_BY_EXTENSION)}."
        )

    if file_path.suffix.lower() != extension:
        raise ValueError("Stored file extension does not match the document name.")

    expected_mime_type = MIME_TYPES_BY_EXTENSION[extension]
    if mime_type not in (None, "", "application/octet-stream", expected_mime_type):
        raise ValueError(
            f"Document MIME type does not match its {extension} file extension."
        )

    if not file_path.is_file():
        raise ValueError("Document file does not exist.")

    if file_path.stat().st_size <= 0:
        raise ValueError("Document file is empty.")

    if extension == ".pdf":
        try:
            with file_path.open("rb") as document_file:
                header = document_file.read(1024)
            if b"%PDF-" not in header:
                raise ValueError("File content is not a valid PDF.")

            with fitz.open(file_path) as pdf:
                if pdf.is_encrypted:
                    raise ValueError("Password-protected PDFs cannot be classified.")
                if len(pdf) == 0:
                    raise ValueError("PDF contains no pages.")
                extracted_text = "\n".join(page.get_text() for page in pdf).strip()
        except (fitz.FileDataError, fitz.EmptyFileError, RuntimeError) as error:
            raise ValueError("PDF file is corrupt or cannot be read.") from error
        return extracted_text, "pdf_text"

    try:
        with Image.open(file_path) as image:
            image.verify()
            image_format = image.format
    except (
        Image.DecompressionBombError,
        OSError,
        UnidentifiedImageError,
        ValueError,
    ) as error:
        raise ValueError("Image file is corrupt or cannot be read.") from error

    expected_image_format = {
        ".jpg": "JPEG",
        ".jpeg": "JPEG",
        ".png": "PNG",
    }[extension]
    if image_format != expected_image_format:
        raise ValueError(
            f"Image content does not match its {extension} file extension."
        )
    return "", "image_requires_ocr"


def _classify_text(text: str) -> tuple[str, list[str]]:
    matched_types = [
        document_type
        for document_type, patterns in CATEGORY_PATTERNS.items()
        if any(pattern.search(text) for pattern in patterns)
    ]
    if len(matched_types) == 1:
        return matched_types[0], matched_types
    return "OTHER", matched_types


def classify_document(document_id: int, application_id: int | None = None):
    """Validate an uploaded file and infer its category from readable content."""
    conn = get_connection()

    try:
        with conn.cursor() as cursor:
            if application_id is None:
                cursor.execute(
                    """
                    SELECT id, application_id, file_name, file_path, file_size, mime_type
                    FROM application_documents
                    WHERE id = %s;
                    """,
                    (document_id,),
                )
            else:
                cursor.execute(
                    """
                    SELECT id, application_id, file_name, file_path, file_size, mime_type
                    FROM application_documents
                    WHERE id = %s AND application_id = %s;
                    """,
                    (document_id, application_id),
                )
            document = cursor.fetchone()

        if document is None:
            raise DocumentNotFoundError("Document not found.")

        file_path = Path(document[3])
        file_size = file_path.stat().st_size if file_path.is_file() else 0
        if document[4] <= 0 or file_size <= 0:
            raise ValueError("Document file is missing or empty.")

        extracted_text, classification_method = _validate_document_file(
            file_path,
            document[2],
            document[5],
        )

        if extracted_text:
            document_type, matched_types = _classify_text(extracted_text)
            if document_type == "OTHER":
                classification_status = "NEEDS_REVIEW"
                confidence = 0.0
                reason = (
                    "The file is readable, but its text did not match one "
                    "unambiguous supported document category."
                )
            else:
                classification_status = "CLASSIFIED"
                confidence = 0.9
                reason = (
                    "Category inferred from readable PDF text. This is a "
                    "heuristic classification, not an eligibility decision."
                )
        else:
            document_type = "OTHER"
            matched_types = []
            classification_status = "NEEDS_REVIEW"
            confidence = 0.0
            reason = (
                "The file is structurally valid, but automatic text "
                "classification is unavailable for images and scanned PDFs."
            )

        if document_type not in ALLOWED_DOCUMENT_TYPES:
            raise RuntimeError("Classifier produced an unsupported document type.")

        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE application_documents
                SET document_type = %s
                WHERE id = %s AND application_id = %s;
                """,
                (document_type, document[0], document[1]),
            )

        conn.commit()
        return {
            "document_id": document[0],
            "application_id": document[1],
            "file_name": document[2],
            "document_type": document_type,
            "valid": True,
            "classification_status": classification_status,
            "confidence": confidence,
            "matched_categories": matched_types,
            "classification_method": classification_method,
            "reason": reason,
        }

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

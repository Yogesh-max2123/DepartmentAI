"""
DepartmentAI - PDF Ingestion Pipeline

Purpose:
    Extract text from the UG Ordinance PDF page-by-page.

Input:
    documents/ug/UG Ordinance.pdf

Output:
    documents/ug/processed/
        ug_ordinance_pages.json
        ug_ordinance_text.txt

The extracted data will later be used by:
    PDF -> Structure Detection -> Chunking -> Embeddings -> Knowledge Base -> RAG
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pymupdf

# ---------------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------------

# pdf_parser.py
#     -> ingestion/
#     -> ai/
#     -> DepartmentAI/
PROJECT_ROOT = Path(__file__).resolve().parents[2]

PDF_PATH = PROJECT_ROOT / "documents" / "ug" / "UG Ordinance.pdf"

OUTPUT_DIR = PROJECT_ROOT / "documents" / "ug" / "processed"

JSON_OUTPUT = OUTPUT_DIR / "ug_ordinance_pages.json"
TEXT_OUTPUT = OUTPUT_DIR / "ug_ordinance_text.txt"


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def clean_text(text: str) -> str:
    """
    Clean extracted PDF text while preserving meaningful content.

    We deliberately do NOT aggressively modify the text because this
    document is an official ordinance and we need to preserve its wording.
    """

    # Normalize different newline characters.
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Remove trailing whitespace from every line.
    lines = [line.rstrip() for line in text.split("\n")]

    # Collapse excessive blank lines.
    cleaned_lines = []

    previous_blank = False

    for line in lines:
        is_blank = not line.strip()

        if is_blank:
            if not previous_blank:
                cleaned_lines.append("")
            previous_blank = True
        else:
            cleaned_lines.append(line)
            previous_blank = False

    return "\n".join(cleaned_lines).strip()


def detect_sections(text: str) -> list[str]:
    """
    Detect section/subsection identifiers from a page.

    Examples:
        1. INTRODUCTION
        1.6 Department Undergraduate Committee
        6.2.4 Make-up Examination
        9.1 Attendance Requirement
    """

    patterns = [
        # Main sections:
        r"(?m)^\s*(\d{1,2})\.\s+[A-Z][^\n]+",

        # Subsections:
        r"(?m)^\s*(\d{1,2}\.\d{1,3})\s+[A-Z][^\n]+",
    ]

    sections = []

    for pattern in patterns:
        matches = re.findall(pattern, text)

        for match in matches:
            if match not in sections:
                sections.append(match)

    return sections


def detect_forms(text: str) -> list[str]:
    """
    Detect ordinance forms such as BP-01, BP-10, BP-13.
    """

    matches = re.findall(
        r"\bBP[-–]\s*\d{1,2}\b",
        text,
        flags=re.IGNORECASE,
    )

    forms = []

    for match in matches:
        normalized = re.sub(r"[-–]\s*", "-", match.upper())

        if normalized not in forms:
            forms.append(normalized)

    return forms


def extract_page_data(page: pymupdf.Page, page_number: int) -> dict:
    """
    Extract and structure information from one PDF page.
    """

    raw_text = page.get_text("text")
    text = clean_text(raw_text)

    return {
        "page_number": page_number,
        "text": text,
        "character_count": len(text),
        "word_count": len(text.split()),
        "sections_detected": detect_sections(text),
        "forms_detected": detect_forms(text),
    }


# ---------------------------------------------------------------------------
# PDF validation
# ---------------------------------------------------------------------------

def validate_pdf(pdf_path: Path) -> None:
    """
    Validate that the input PDF exists and can be opened.
    """

    if not pdf_path.exists():
        raise FileNotFoundError(
            f"PDF file was not found:\n{pdf_path}"
        )

    if not pdf_path.is_file():
        raise ValueError(
            f"The specified PDF path is not a file:\n{pdf_path}"
        )

    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError(
            f"Expected a PDF file, but received:\n{pdf_path}"
        )


# ---------------------------------------------------------------------------
# Main extraction function
# ---------------------------------------------------------------------------

def parse_pdf(pdf_path: Path = PDF_PATH) -> list[dict]:
    """
    Extract all pages from the PDF.

    Returns:
        List of dictionaries, one dictionary per PDF page.
    """

    validate_pdf(pdf_path)

    print(f"Opening PDF:")
    print(f"  {pdf_path}")

    try:
        document = pymupdf.open(pdf_path)
    except Exception as exc:
        raise RuntimeError(
            f"Unable to open PDF: {exc}"
        ) from exc

    pages = []

    try:
        total_pages = len(document)

        print(f"Total PDF pages: {total_pages}")
        print("Extracting text...")

        for index, page in enumerate(document):
            page_number = index + 1

            page_data = extract_page_data(
                page,
                page_number,
            )

            pages.append(page_data)

            print(
                f"  Page {page_number:02d}/{total_pages}: "
                f"{page_data['character_count']} characters"
            )

    finally:
        document.close()

    return pages


# ---------------------------------------------------------------------------
# Save extracted data
# ---------------------------------------------------------------------------

def save_results(pages: list[dict]) -> None:
    """
    Save both structured JSON and plain text representations.
    """

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # -------------------------------------------------------
    # JSON output
    # -------------------------------------------------------

    document_data = {
        "document": {
            "filename": PDF_PATH.name,
            "document_type": "UG Ordinance",
            "institution": "Motilal Nehru National Institute of Technology Allahabad",
            "source": "UG Ordinance.pdf",
            "total_pages": len(pages),
        },
        "pages": pages,
    }

    with JSON_OUTPUT.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            document_data,
            file,
            ensure_ascii=False,
            indent=2,
        )

    # -------------------------------------------------------
    # Plain text output
    # -------------------------------------------------------

    with TEXT_OUTPUT.open(
        "w",
        encoding="utf-8",
    ) as file:

        for page in pages:
            file.write(
                f"\n{'=' * 80}\n"
            )

            file.write(
                f"PAGE {page['page_number']}\n"
            )

            file.write(
                f"{'=' * 80}\n\n"
            )

            file.write(
                page["text"]
            )

            file.write("\n")

    print()
    print("Extraction completed successfully.")
    print()
    print("Generated files:")
    print(f"  JSON : {JSON_OUTPUT}")
    print(f"  TEXT : {TEXT_OUTPUT}")


# ---------------------------------------------------------------------------
# Basic validation
# ---------------------------------------------------------------------------

def validate_results(pages: list[dict]) -> None:
    """
    Perform basic sanity checks after extraction.
    """

    if not pages:
        raise RuntimeError(
            "No pages were extracted from the PDF."
        )

    pages_with_text = [
        page for page in pages
        if page["text"].strip()
    ]

    if not pages_with_text:
        raise RuntimeError(
            "PDF opened successfully, but no text was extracted."
        )

    total_characters = sum(
        page["character_count"]
        for page in pages
    )

    if total_characters < 1000:
        raise RuntimeError(
            "Very little text was extracted. "
            "The PDF may require OCR."
        )

    print()
    print("Validation:")
    print(f"  Pages extracted : {len(pages)}")
    print(f"  Pages with text : {len(pages_with_text)}")
    print(f"  Total characters: {total_characters}")

    detected_sections = set()

    for page in pages:
        detected_sections.update(
            page["sections_detected"]
        )

    detected_forms = set()

    for page in pages:
        detected_forms.update(
            page["forms_detected"]
        )

    print(f"  Sections detected: {len(detected_sections)}")
    print(f"  Forms detected   : {len(detected_forms)}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """
    Main program entry point.
    """

    print("=" * 80)
    print("DepartmentAI - UG Ordinance PDF Parser")
    print("=" * 80)
    print()

    try:
        pages = parse_pdf()

        validate_results(pages)

        save_results(pages)

        print()
        print("=" * 80)
        print("SUCCESS")
        print("=" * 80)

    except Exception as exc:
        print()
        print("=" * 80)
        print("ERROR")
        print("=" * 80)
        print(str(exc))
        print()

        sys.exit(1)


if __name__ == "__main__":
    main()
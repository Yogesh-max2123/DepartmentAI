"""
DepartmentAI PDF Ingestion Pipeline (B.Tech. / M.Tech. / Ph.D.)

Purpose:
    Extract text from an ordinance PDF page-by-page.

Use --programme phd|mtech|ug (default phd).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import pymupdf

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ai.programme_paths import get_programme_paths

# ---------------------------------------------------------------------------
# Project paths (overridden by apply_programme)
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PDF_PATH = PROJECT_ROOT / "documents" / "phd" / "Ordinances_for_Doctoral_Programm2023.pdf"
OUTPUT_DIR = PROJECT_ROOT / "documents" / "phd" / "processed"
JSON_OUTPUT = OUTPUT_DIR / "phd_ordinance_pages.json"
TEXT_OUTPUT = OUTPUT_DIR / "phd_ordinance_text.txt"
ACTIVE_LABEL = "Ph.D."


def apply_programme(programme: str = "phd"):
    global PDF_PATH, OUTPUT_DIR, JSON_OUTPUT, TEXT_OUTPUT, ACTIVE_LABEL
    config = get_programme_paths(programme)
    PDF_PATH = config["pdf_path"]
    OUTPUT_DIR = config["processed_dir"]
    JSON_OUTPUT = config["pages_json"]
    TEXT_OUTPUT = config["text_txt"]
    ACTIVE_LABEL = config["label"]
    return config


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
        1.3 Department Doctoral Programme Committee (DDPC)
        8.1 Termination from the Programme
        12.3 Constitution of Comprehensive Examination Board
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
    Detect ordinance forms such as DP-01, DP-02, DP-24 and GL-1.
    """

    matches = re.findall(
        r"\b(DP|GL)[-–\s]?\s*(\d{1,2})\b",
        text,
        flags=re.IGNORECASE,
    )

    forms = []

    for prefix, number in matches:
        normalized = f"{prefix.upper()}-{number.zfill(2)}"

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
            "document_type": "Doctoral Programmes Ordinance",
            "institution": "Motilal Nehru National Institute of Technology Allahabad",
            "source": "Ordinances_for_Doctoral_Programm2023.pdf",
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
    parser = argparse.ArgumentParser(description="Extract ordinance PDF text.")
    parser.add_argument("--programme", choices=["phd", "mtech", "ug"], default="phd")
    args = parser.parse_args()
    apply_programme(args.programme)

    print("=" * 80)
    print(f"DepartmentAI ({ACTIVE_LABEL}) - Ordinance PDF Parser")
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

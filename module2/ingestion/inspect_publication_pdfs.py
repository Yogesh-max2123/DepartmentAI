from __future__ import annotations

from pathlib import Path
import re

from pypdf import PdfReader


PDF_DIR = Path("module2/ingestion/debug_publication_structures/pdf")

TARGET_FILES = [
    "prof_m_m_gore.pdf",
    "prof_d_s_kushwaha.pdf",
    "dr_shashank_srivastava.pdf",
    "dr_vibhav_prakash_singh.pdf",
    "dr_abhinav_kumar.pdf",
    "dr_satarupa_chakrabarti.pdf",
]


def clean_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def detect_numbered_lines(text: str) -> list[str]:
    results = []

    for line in text.splitlines():
        line = line.strip()

        if not line:
            continue

        # Common publication numbering styles:
        # 1.
        # 38.
        # [1]
        # 1)
        # 38)
        # 1 -
        # 38 -
        if re.match(r"^(?:\d+[\.\)]|\[\d+\]|\d+\s*[-:])\s+", line):
            results.append(line)

    return results


def detect_category_lines(text: str) -> list[str]:
    category_keywords = (
        "journal",
        "journals",
        "conference",
        "proceedings",
        "book",
        "books",
        "book chapter",
        "chapters",
        "patent",
        "publication",
        "publications",
    )

    results = []

    for line in text.splitlines():
        line = line.strip()

        if not line:
            continue

        normalized = re.sub(r"\s+", " ", line).strip()
        lower = normalized.lower()

        # Keep short/medium lines that look like section/category labels.
        if len(normalized) <= 120 and any(
            keyword in lower for keyword in category_keywords
        ):
            if normalized not in results:
                results.append(normalized)

    return results


def detect_doi_lines(text: str) -> list[str]:
    results = []

    for line in text.splitlines():
        line = line.strip()

        if "doi" in line.lower() or "doi.org/" in line.lower():
            if line not in results:
                results.append(line)

    return results


def inspect_pdf(filename: str) -> None:
    path = PDF_DIR / filename

    print()
    print("=" * 100)
    print(f"FILE: {filename}")
    print("=" * 100)

    if not path.exists():
        print("ERROR: File does not exist")
        return

    try:
        reader = PdfReader(str(path))
    except Exception as exc:
        print(f"ERROR opening PDF: {type(exc).__name__}: {exc}")
        return

    print(f"Pages: {len(reader.pages)}")
    print(f"Size: {path.stat().st_size:,} bytes")

    all_pages: list[str] = []
    extraction_errors = 0

    for page_number, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
            text = clean_text(text)
            all_pages.append(text)
        except Exception as exc:
            extraction_errors += 1
            all_pages.append("")
            print(
                f"WARNING: Page {page_number} extraction failed: "
                f"{type(exc).__name__}: {exc}"
            )

    full_text = "\n\n".join(all_pages)

    print(f"Pages with extraction errors: {extraction_errors}")
    print(f"Total extracted characters: {len(full_text):,}")

    non_empty_pages = sum(bool(text.strip()) for text in all_pages)

    print(f"Non-empty extracted pages: {non_empty_pages}/{len(all_pages)}")

    print()
    print("-" * 100)
    print("CATEGORY-LIKE HEADINGS / LABELS")
    print("-" * 100)

    categories = detect_category_lines(full_text)

    if categories:
        for item in categories[:50]:
            print(f"  - {item}")
    else:
        print("  None detected")

    print()
    print("-" * 100)
    print("NUMBERED RECORD-LIKE LINES")
    print("-" * 100)

    numbered = detect_numbered_lines(full_text)

    if numbered:
        print(f"Detected numbered lines: {len(numbered)}")
        for item in numbered[:30]:
            print(f"  - {item}")
    else:
        print("  None detected")

    print()
    print("-" * 100)
    print("DOI-LIKE LINES")
    print("-" * 100)

    doi_lines = detect_doi_lines(full_text)

    if doi_lines:
        print(f"Detected DOI-like lines: {len(doi_lines)}")
        for item in doi_lines[:20]:
            print(f"  - {item}")
    else:
        print("  None detected")

    print()
    print("-" * 100)
    print("FIRST 2 PAGES")
    print("-" * 100)

    for page_number, text in enumerate(all_pages[:2], start=1):
        print()
        print(f"[PAGE {page_number}]")
        print("-" * 80)

        if not text:
            print("(No extractable text)")
            continue

        print(text[:6000])

    print()
    print("-" * 100)
    print("LAST PAGE")
    print("-" * 100)

    if all_pages:
        last_page = all_pages[-1]

        if last_page:
            print(last_page[:6000])
        else:
            print("(No extractable text)")

    print()
    print("-" * 100)
    print("PAGE-BY-PAGE CHARACTER COUNTS")
    print("-" * 100)

    for page_number, text in enumerate(all_pages, start=1):
        print(f"Page {page_number:02d}: {len(text):6,} characters")


def main() -> None:
    print("=" * 100)
    print("PUBLICATION PDF STRUCTURE INSPECTION")
    print("=" * 100)
    print()
    print(f"PDF directory: {PDF_DIR}")
    print(f"Target PDFs: {len(TARGET_FILES)}")

    missing = []

    for filename in TARGET_FILES:
        if not (PDF_DIR / filename).exists():
            missing.append(filename)

    if missing:
        print()
        print("Missing files:")
        for filename in missing:
            print(f"  - {filename}")

    for filename in TARGET_FILES:
        inspect_pdf(filename)

    print()
    print("=" * 100)
    print("INSPECTION COMPLETE")
    print("=" * 100)


if __name__ == "__main__":
    main()
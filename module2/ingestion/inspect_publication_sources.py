from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
import re

import requests

from module2.ingestion.faculty_directory import (
    discover_faculty,
)
from module2.ingestion.faculty_profile import (
    discover_profile_components,
)


DEBUG_DIR = Path("module2/ingestion/debug_publications")
REQUEST_TIMEOUT = 30


@dataclass
class PublicationSourceInspection:
    faculty_name: str
    profile_url: str
    publications_url: str = ""
    source_type: str = "ERROR"
    pdf_url: str = ""
    html_record_content: bool = False
    error: str = ""


def _safe_filename(name: str) -> str:
    """
    Convert a faculty name into a safe filename.
    """
    value = re.sub(r"[^A-Za-z0-9]+", "_", name.strip())
    value = value.strip("_")

    if not value:
        value = "unknown_faculty"

    return value.lower()


def _normalize_url(url: str, base_url: str) -> str:
    """
    Convert a relative URL into an absolute URL.
    """
    if not url:
        return ""

    return requests.compat.urljoin(base_url, url.strip())


def _extract_pdf_url(html: str, page_url: str) -> str:
    """
    Detect an embedded PDF from common HTML elements.

    Currently checks iframe and embed elements because the M.M. Gore
    Publications page uses an iframe containing the PDF.
    """
    iframe_pattern = re.compile(
        r"<iframe\b[^>]*\bsrc\s*=\s*[\"']([^\"']+)[\"']",
        re.IGNORECASE,
    )

    embed_pattern = re.compile(
        r"<embed\b[^>]*\bsrc\s*=\s*[\"']([^\"']+)[\"']",
        re.IGNORECASE,
    )

    object_pattern = re.compile(
        r"<object\b[^>]*\bdata\s*=\s*[\"']([^\"']+)[\"']",
        re.IGNORECASE,
    )

    for pattern in (iframe_pattern, embed_pattern, object_pattern):
        match = pattern.search(html)

        if not match:
            continue

        candidate = _normalize_url(match.group(1), page_url)

        if ".pdf" in candidate.lower():
            return candidate

    return ""


def _contains_html_publication_content(html: str) -> bool:
    """
    Detect whether the Publications page appears to contain publication
    records directly in HTML.

    This intentionally uses broad structural signals rather than trying
    to parse publications at this stage.
    """
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()

    if not text:
        return False

    publication_headings = (
        "journal",
        "journals",
        "book chapter",
        "book chapters",
        "conference proceedings",
        "conference papers",
        "books",
        "research publications",
    )

    lower_text = text.lower()

    heading_found = any(
        heading in lower_text
        for heading in publication_headings
    )

    if not heading_found:
        return False

    # Look for signs that there is actual content after a publication
    # category heading. We deliberately do not attempt to parse records.
    category_patterns = (
        r"(?:book\s+chapters?|journals?|conference\s+proceedings?|"
        r"conference\s+papers?|books?)\s*:",
        r"(?:book\s+chapters?|journals?|conference\s+proceedings?|"
        r"conference\s+papers?|books?)",
    )

    return any(
        re.search(pattern, lower_text, re.IGNORECASE)
        for pattern in category_patterns
    )


def _classify_publications_page(
    html: str,
    page_url: str,
) -> tuple[str, str, bool]:
    """
    Classify a Publications page without parsing its records.

    Returns:
        (source_type, pdf_url, html_record_content)
    """
    pdf_url = _extract_pdf_url(html, page_url)

    if pdf_url:
        return "PDF", pdf_url, False

    has_html_content = _contains_html_publication_content(html)

    if has_html_content:
        return "HTML", "", True

    return "OTHER", "", False


def inspect_faculty_publications(
    faculty_name: str,
    profile_url: str,
) -> PublicationSourceInspection:
    """
    Discover the actual Publications URL for one faculty member,
    fetch it, save the raw HTML, and classify its source format.
    """
    result = PublicationSourceInspection(
        faculty_name=faculty_name,
        profile_url=profile_url,
    )

    try:
        components = discover_profile_components(
            faculty_name=faculty_name,
            profile_url=profile_url,
        )

        publications_url = components.publications_url
        result.publications_url = publications_url

        if not publications_url:
            result.source_type = "ERROR"
            result.error = "Publications URL not found"
            return result

        response = requests.get(
            publications_url,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()

        html = response.text

        DEBUG_DIR.mkdir(parents=True, exist_ok=True)

        filename = f"{_safe_filename(faculty_name)}.html"
        output_path = DEBUG_DIR / filename

        output_path.write_text(
            html,
            encoding="utf-8",
        )

        (
            source_type,
            pdf_url,
            html_record_content,
        ) = _classify_publications_page(
            html=html,
            page_url=publications_url,
        )

        result.source_type = source_type
        result.pdf_url = pdf_url
        result.html_record_content = html_record_content

        return result

    except Exception as exc:
        result.source_type = "ERROR"
        result.error = f"{type(exc).__name__}: {exc}"
        return result


def _print_result(
    index: int,
    result: PublicationSourceInspection,
) -> None:
    print(
        f"{index:02d}. {result.faculty_name}\n"
        f"    Type: {result.source_type}\n"
        f"    Publications URL: {result.publications_url or '-'}"
    )

    if result.pdf_url:
        print(f"    PDF: {result.pdf_url}")

    if result.html_record_content:
        print("    HTML records detected: Yes")

    if result.error:
        print(f"    Error: {result.error}")

    print()


def main() -> None:
    print("=" * 60)
    print("PUBLICATION SOURCE INSPECTION")
    print("=" * 60)
    print()

    DEBUG_DIR.mkdir(parents=True, exist_ok=True)

    faculty = discover_faculty()

    print(f"Total faculty discovered: {len(faculty)}")
    print()

    results: list[PublicationSourceInspection] = []

    for index, person in enumerate(faculty, start=1):
        result = inspect_faculty_publications(
            faculty_name=person.name,
            profile_url=person.profile_url,
        )

        results.append(result)
        _print_result(index, result)

    pdf_count = sum(
        result.source_type == "PDF"
        for result in results
    )

    html_count = sum(
        result.source_type == "HTML"
        for result in results
    )

    other_count = sum(
        result.source_type == "OTHER"
        for result in results
    )

    error_count = sum(
        result.source_type == "ERROR"
        for result in results
    )

    print("=" * 60)
    print("PUBLICATION SOURCE SUMMARY")
    print("=" * 60)
    print(f"PDF:    {pdf_count}")
    print(f"HTML:   {html_count}")
    print(f"OTHER:  {other_count}")
    print(f"ERROR:  {error_count}")
    print(f"Total:  {len(results)}")
    print("=" * 60)

    print()
    print("Debug HTML files saved to:")
    print(f"  {DEBUG_DIR}")


if __name__ == "__main__":
    main()

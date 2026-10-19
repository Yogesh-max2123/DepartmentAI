from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse
import re

import requests

from module2.ingestion.faculty_directory import discover_faculty
from module2.ingestion.faculty_profile import discover_profile_components


DEBUG_DIR = Path("module2/ingestion/debug_publication_structures")
HTML_DIR = DEBUG_DIR / "html"
PDF_DIR = DEBUG_DIR / "pdf"

REQUEST_TIMEOUT = 30

# Representative PDF sources selected from the verified 29 PDF-based profiles.
REPRESENTATIVE_PDF_FACULTY = {
    "Prof. M.M.Gore",
    "Prof. D.S. Kushwaha",
    "Dr. Shashank Srivastava",
    "Dr. Vibhav Prakash Singh",
    "Dr. Abhinav Kumar",
    "Dr. Satarupa Chakrabarti",
}


@dataclass
class HTMLInspection:
    faculty_name: str
    publications_url: str = ""
    status: str = "ERROR"
    headings: list[str] = field(default_factory=list)
    record_like_lines: list[str] = field(default_factory=list)
    saved_file: str = ""
    error: str = ""


@dataclass
class PDFInspection:
    faculty_name: str
    publications_url: str = ""
    pdf_url: str = ""
    status: str = "ERROR"
    downloaded: bool = False
    saved_file: str = ""
    file_size: int = 0
    error: str = ""


def _safe_filename(name: str) -> str:
    """Convert a faculty name into a safe filename."""
    value = re.sub(r"[^A-Za-z0-9]+", "_", name.strip())
    value = value.strip("_")

    return value.lower() or "unknown_faculty"


def _absolute_url(url: str, base_url: str) -> str:
    """Convert a relative URL into an absolute URL."""
    return requests.compat.urljoin(base_url, url.strip())


def _clean_text(value: str) -> str:
    """Normalize whitespace while preserving the actual text content."""
    return re.sub(r"\s+", " ", value).strip()


def _strip_html(html: str) -> str:
    """
    Convert HTML into approximate visible text.

    This is used only for structural inspection.
    It is NOT the final HTML publication parser.
    """
    html = re.sub(
        r"<script\b[^>]*>.*?</script>",
        " ",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )

    html = re.sub(
        r"<style\b[^>]*>.*?</style>",
        " ",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )

    html = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"</p\s*>", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"</div\s*>", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"</li\s*>", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"</tr\s*>", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"</h[1-6]\s*>", "\n", html, flags=re.IGNORECASE)

    text = re.sub(r"<[^>]+>", " ", html)

    text = (
        text.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
    )

    lines = []

    for line in text.splitlines():
        line = _clean_text(line)

        if line:
            lines.append(line)

    return "\n".join(lines)


def _extract_html_headings(html: str) -> list[str]:
    """
    Extract visible heading text from h1-h6 elements.

    The purpose is to discover category naming variations such as:
    Journal Papers, Journals, Book Chapter, Conference Proceedings, etc.
    """
    pattern = re.compile(
        r"<h([1-6])\b[^>]*>(.*?)</h\1\s*>",
        re.IGNORECASE | re.DOTALL,
    )

    headings: list[str] = []

    for match in pattern.finditer(html):
        raw = match.group(2)

        text = re.sub(r"<[^>]+>", " ", raw)
        text = _clean_text(text)

        if text and text not in headings:
            headings.append(text)

    return headings


def _extract_html_record_like_lines(html: str) -> list[str]:
    """
    Extract lines that look like publication records.

    This is intentionally heuristic and is only for inspection.
    It does NOT claim that these are final publication records.
    """
    text = _strip_html(html)

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    results: list[str] = []

    category_words = (
        "journal",
        "journals",
        "book",
        "chapter",
        "conference",
        "proceedings",
        "publication",
        "paper",
    )

    for line in lines:
        lower = line.lower()

        if len(line) < 25:
            continue

        has_category_signal = any(
            word in lower
            for word in category_words
        )

        has_year = bool(
            re.search(r"\b(?:19|20)\d{2}\b", line)
        )

        has_doi = "doi" in lower or "https://doi.org/" in lower

        if has_category_signal or has_year or has_doi:
            if line not in results:
                results.append(line)

    return results[:30]


def _extract_pdf_url(html: str, page_url: str) -> str:
    """
    Extract an embedded PDF URL from iframe/embed/object elements.
    """
    patterns = (
        re.compile(
            r"<iframe\b[^>]*\bsrc\s*=\s*[\"']([^\"']+)[\"']",
            re.IGNORECASE,
        ),
        re.compile(
            r"<embed\b[^>]*\bsrc\s*=\s*[\"']([^\"']+)[\"']",
            re.IGNORECASE,
        ),
        re.compile(
            r"<object\b[^>]*\bdata\s*=\s*[\"']([^\"']+)[\"']",
            re.IGNORECASE,
        ),
    )

    for pattern in patterns:
        for match in pattern.finditer(html):
            candidate = _absolute_url(
                match.group(1),
                page_url,
            )

            if ".pdf" in candidate.lower():
                return candidate

    return ""


def _download_pdf(
    faculty_name: str,
    pdf_url: str,
) -> tuple[bool, str, int, str]:
    """
    Download a representative Publications PDF.

    Returns:
        downloaded, saved_path, file_size, error
    """
    PDF_DIR.mkdir(parents=True, exist_ok=True)

    filename = f"{_safe_filename(faculty_name)}.pdf"
    output_path = PDF_DIR / filename

    try:
        response = requests.get(
            pdf_url,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()

        content = response.content

        if not content:
            return False, "", 0, "Downloaded PDF is empty"

        if not content.startswith(b"%PDF"):
            return (
                False,
                "",
                len(content),
                "Response does not have a valid PDF signature",
            )

        output_path.write_bytes(content)

        return (
            True,
            str(output_path),
            len(content),
            "",
        )

    except Exception as exc:
        return (
            False,
            "",
            0,
            f"{type(exc).__name__}: {exc}",
        )


def inspect_html_source(
    faculty_name: str,
    publications_url: str,
) -> HTMLInspection:
    """Inspect and save one HTML Publications source."""
    result = HTMLInspection(
        faculty_name=faculty_name,
        publications_url=publications_url,
    )

    try:
        response = requests.get(
            publications_url,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()

        html = response.text

        HTML_DIR.mkdir(parents=True, exist_ok=True)

        output_path = (
            HTML_DIR
            / f"{_safe_filename(faculty_name)}.html"
        )

        output_path.write_text(
            html,
            encoding="utf-8",
        )

        result.headings = _extract_html_headings(html)
        result.record_like_lines = (
            _extract_html_record_like_lines(html)
        )
        result.saved_file = str(output_path)
        result.status = "SUCCESS"

        return result

    except Exception as exc:
        result.status = "ERROR"
        result.error = (
            f"{type(exc).__name__}: {exc}"
        )
        return result


def inspect_pdf_source(
    faculty_name: str,
    publications_url: str,
) -> PDFInspection:
    """Inspect and download one representative PDF source."""
    result = PDFInspection(
        faculty_name=faculty_name,
        publications_url=publications_url,
    )

    try:
        response = requests.get(
            publications_url,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()

        html = response.text

        pdf_url = _extract_pdf_url(
            html=html,
            page_url=publications_url,
        )

        if not pdf_url:
            result.status = "ERROR"
            result.error = (
                "No embedded PDF URL found"
            )
            return result

        result.pdf_url = pdf_url

        (
            downloaded,
            saved_file,
            file_size,
            error,
        ) = _download_pdf(
            faculty_name=faculty_name,
            pdf_url=pdf_url,
        )

        result.downloaded = downloaded
        result.saved_file = saved_file
        result.file_size = file_size
        result.error = error

        if downloaded:
            result.status = "SUCCESS"
        else:
            result.status = "ERROR"

        return result

    except Exception as exc:
        result.status = "ERROR"
        result.error = (
            f"{type(exc).__name__}: {exc}"
        )
        return result


def _print_html_result(
    index: int,
    result: HTMLInspection,
) -> None:
    print(
        f"{index:02d}. {result.faculty_name}"
    )
    print(
        f"    Publications URL: "
        f"{result.publications_url or '-'}"
    )
    print(
        f"    Status: {result.status}"
    )

    if result.headings:
        print("    Headings:")

        for heading in result.headings:
            print(f"      - {heading}")

    if result.record_like_lines:
        print("    Sample record-like content:")

        for line in result.record_like_lines[:8]:
            print(f"      - {line}")

    if result.saved_file:
        print(
            f"    Saved HTML: {result.saved_file}"
        )

    if result.error:
        print(
            f"    Error: {result.error}"
        )

    print()


def _print_pdf_result(
    index: int,
    result: PDFInspection,
) -> None:
    print(
        f"{index:02d}. {result.faculty_name}"
    )
    print(
        f"    Publications URL: "
        f"{result.publications_url or '-'}"
    )
    print(
        f"    PDF URL: "
        f"{result.pdf_url or '-'}"
    )
    print(
        f"    Status: {result.status}"
    )

    if result.downloaded:
        print(
            f"    Downloaded: Yes"
        )
        print(
            f"    File size: "
            f"{result.file_size:,} bytes"
        )
        print(
            f"    Saved PDF: "
            f"{result.saved_file}"
        )

    if result.error:
        print(
            f"    Error: {result.error}"
        )

    print()


def main() -> None:
    print("=" * 70)
    print("PUBLICATION STRUCTURE INSPECTION")
    print("=" * 70)
    print()

    HTML_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    PDF_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    faculty = discover_faculty()

    print(
        f"Total faculty discovered: "
        f"{len(faculty)}"
    )
    print()

    html_results: list[HTMLInspection] = []
    pdf_results: list[PDFInspection] = []

    html_index = 0
    pdf_index = 0

    for person in faculty:
        components = discover_profile_components(
            faculty_name=person.name,
            profile_url=person.profile_url,
        )

        publications_url = (
            components.publications_url
        )

        if not publications_url:
            print(
                f"WARNING: No Publications URL for "
                f"{person.name}"
            )
            print()
            continue

        if person.name in REPRESENTATIVE_PDF_FACULTY:
            pdf_index += 1

            result = inspect_pdf_source(
                faculty_name=person.name,
                publications_url=publications_url,
            )

            pdf_results.append(result)

            _print_pdf_result(
                pdf_index,
                result,
            )

        else:
            # We only inspect HTML pages here if their actual
            # Publications page is HTML. The source-format
            # inspection already established the complete
            # 29 PDF / 17 HTML classification.
            #
            # To avoid downloading all 29 PDFs again, we inspect
            # non-representative profiles as HTML candidates only
            # when the page itself contains no embedded PDF.
            try:
                response = requests.get(
                    publications_url,
                    timeout=REQUEST_TIMEOUT,
                )
                response.raise_for_status()

                html = response.text

                pdf_url = _extract_pdf_url(
                    html=html,
                    page_url=publications_url,
                )

                if pdf_url:
                    continue

            except Exception as exc:
                html_index += 1

                result = HTMLInspection(
                    faculty_name=person.name,
                    publications_url=publications_url,
                    status="ERROR",
                    error=(
                        f"{type(exc).__name__}: "
                        f"{exc}"
                    ),
                )

                html_results.append(result)

                _print_html_result(
                    html_index,
                    result,
                )

                continue

            html_index += 1

            result = inspect_html_source(
                faculty_name=person.name,
                publications_url=publications_url,
            )

            html_results.append(result)

            _print_html_result(
                html_index,
                result,
            )

    html_success = sum(
        result.status == "SUCCESS"
        for result in html_results
    )

    html_errors = sum(
        result.status == "ERROR"
        for result in html_results
    )

    pdf_success = sum(
        result.status == "SUCCESS"
        for result in pdf_results
    )

    pdf_errors = sum(
        result.status == "ERROR"
        for result in pdf_results
    )

    print("=" * 70)
    print("STRUCTURE INSPECTION SUMMARY")
    print("=" * 70)
    print()
    print(
        f"HTML sources inspected: "
        f"{len(html_results)}"
    )
    print(
        f"HTML successful:        "
        f"{html_success}"
    )
    print(
        f"HTML errors:            "
        f"{html_errors}"
    )
    print()
    print(
        f"Representative PDFs:    "
        f"{len(pdf_results)}"
    )
    print(
        f"PDF downloads successful:"
        f" {pdf_success}"
    )
    print(
        f"PDF download errors:    "
        f"{pdf_errors}"
    )
    print()
    print(
        "HTML files saved to:"
    )
    print(
        f"  {HTML_DIR}"
    )
    print()
    print(
        "Representative PDFs saved to:"
    )
    print(
        f"  {PDF_DIR}"
    )
    print()
    print("=" * 70)
    print("Inspection complete.")
    print("=" * 70)


if __name__ == "__main__":
    main()

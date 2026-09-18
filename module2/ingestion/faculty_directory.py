from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests


SOURCE_URL = "https://mnnit.ac.in/index.php/department/engineering/csed#publications"

REQUEST_TIMEOUT = 30


@dataclass
class FacultyDirectoryRecord:
    """
    Faculty discovered from the official MNNIT CSE Faculty Profile section.
    """

    name: str
    profile_url: str
    source_url: str


def normalize_text(value: str) -> str:
    """
    Normalize whitespace and common HTML spacing artifacts.
    """
    value = value.replace("\xa0", " ")
    return " ".join(value.split()).strip()


def normalize_url(url: str, base_url: str) -> str:
    """
    Convert a discovered profile URL into a normalized absolute URL.
    """
    absolute = urljoin(base_url, url.strip())

    parsed = urlparse(absolute)

    if parsed.netloc.lower() == "www.mnnit.ac.in":
        absolute = absolute.replace(
            "https://www.mnnit.ac.in",
            "https://mnnit.ac.in",
            1,
        ).replace(
            "http://www.mnnit.ac.in",
            "https://mnnit.ac.in",
            1,
        )

    elif parsed.netloc.lower() == "mnnit.ac.in":
        absolute = absolute.replace(
            "http://mnnit.ac.in",
            "https://mnnit.ac.in",
            1,
        )

    return absolute


def fetch_directory_html() -> str:
    """
    Fetch the official MNNIT CSE department page.
    """
    response = requests.get(
        SOURCE_URL,
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    return response.text


class _FacultySectionParser(HTMLParser):
    """
    Parse only the Faculty Profile section.

    Important structure discovered from the actual MNNIT HTML:

        Faculty Profile
        └── outer table
            ├── direct <tr> = faculty name row
            ├── direct <tr> = faculty details row
            │   └── nested table
            │       └── View Profile anchor
            ├── direct <tr> = next faculty name row
            └── ...

    We therefore track the outer table and ONLY its direct rows.
    """

    def __init__(self) -> None:
        super().__init__(
            convert_charrefs=True,
        )

        self.in_faculty_section = False
        self.faculty_section_depth: Optional[int] = None

        self.outer_table_depth: Optional[int] = None

        self.current_row_depth: Optional[int] = None
        self.current_row_text: list[str] = []
        self.current_row_profile_urls: list[str] = []

        self.rows: list[tuple[str, list[str]]] = []

        self._table_depth = 0
        self._tag_depth = 0

        self._capture_anchor = False
        self._current_anchor_href: Optional[str] = None
        self._current_anchor_text: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()

        attrs_dict = dict(attrs)

        # Detect the Faculty Profile section.
        if tag == "div":
            element_id = attrs_dict.get("id")

            if element_id == "faculty-profile":
                self.in_faculty_section = True
                self.faculty_section_depth = self._tag_depth

        if not self.in_faculty_section:
            self._tag_depth += 1
            return

        if tag == "table":
            self._table_depth += 1

            if (
                self.outer_table_depth is None
                and self.faculty_section_depth is not None
            ):
                self.outer_table_depth = self._table_depth

        # Direct <tr> of the outer faculty table.
        if (
            tag == "tr"
            and self.outer_table_depth is not None
            and self._table_depth == self.outer_table_depth
        ):
            self.current_row_depth = self._table_depth
            self.current_row_text = []
            self.current_row_profile_urls = []

        # Capture every anchor inside the current outer row.
        if (
            tag == "a"
            and self.current_row_depth is not None
            and self._table_depth >= self.outer_table_depth
        ):
            self._capture_anchor = True
            self._current_anchor_href = attrs_dict.get("href")
            self._current_anchor_text = []

        self._tag_depth += 1

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()

        if not self.in_faculty_section:
            self._tag_depth = max(0, self._tag_depth - 1)
            return

        # Finish anchor capture.
        if tag == "a" and self._capture_anchor:
            anchor_text = normalize_text(
                "".join(self._current_anchor_text)
            )

            if (
                anchor_text.lower() == "view profile"
                and self._current_anchor_href
                and self.current_row_depth is not None
            ):
                self.current_row_profile_urls.append(
                    self._current_anchor_href
                )

            self._capture_anchor = False
            self._current_anchor_href = None
            self._current_anchor_text = []

        # Finish a direct outer-table row.
        if (
            tag == "tr"
            and self.current_row_depth is not None
            and self._table_depth == self.outer_table_depth
        ):
            row_text = normalize_text(
                "".join(self.current_row_text)
            )

            self.rows.append(
                (
                    row_text,
                    self.current_row_profile_urls.copy(),
                )
            )

            self.current_row_depth = None
            self.current_row_text = []
            self.current_row_profile_urls = []

        if tag == "table":
            self._table_depth = max(0, self._table_depth - 1)

        self._tag_depth = max(0, self._tag_depth - 1)

    def handle_data(self, data: str) -> None:
        if not self.in_faculty_section:
            return

        if self.current_row_depth is not None:
            self.current_row_text.append(data)

        if self._capture_anchor:
            self._current_anchor_text.append(data)


def _extract_faculty_records(
    parser: _FacultySectionParser,
) -> list[FacultyDirectoryRecord]:
    """
    Convert consecutive outer-table rows into:

        faculty name -> View Profile URL

    The MNNIT structure places the name in one row and the
    corresponding details/View Profile link in the immediately
    following row.
    """

    records: list[FacultyDirectoryRecord] = []

    rows = parser.rows

    for index in range(len(rows) - 1):
        name_row_text, name_row_urls = rows[index]
        details_row_text, details_row_urls = rows[index + 1]

        # The name row should not itself contain a View Profile link.
        if name_row_urls:
            continue

        # The following row must contain exactly the View Profile
        # link(s) belonging to this faculty.
        if len(details_row_urls) != 1:
            continue

        name = normalize_text(name_row_text)

        if not name:
            continue

        # Remove accidental standalone whitespace/punctuation.
        name = name.strip(" |•:-")

        profile_url = normalize_url(
            details_row_urls[0],
            SOURCE_URL,
        )

        records.append(
            FacultyDirectoryRecord(
                name=name,
                profile_url=profile_url,
                source_url=SOURCE_URL,
            )
        )

    return records


def discover_faculty(
    html: Optional[str] = None,
) -> list[FacultyDirectoryRecord]:
    """
    Discover faculty from the official MNNIT CSE Faculty Profile section.

    This function does NOT:
    - insert anything into PostgreSQL
    - visit individual faculty profiles
    - scrape publications/achievements/etc.
    - use an LLM

    It only discovers:

        faculty name + actual View Profile URL
    """

    if html is None:
        html = fetch_directory_html()

    parser = _FacultySectionParser()
    parser.feed(html)
    parser.close()

    records = _extract_faculty_records(parser)

    # Deduplicate using the actual profile URL.
    unique_records: list[FacultyDirectoryRecord] = []
    seen_urls: set[str] = set()

    for record in records:
        if record.profile_url in seen_urls:
            continue

        seen_urls.add(record.profile_url)
        unique_records.append(record)

    return unique_records


def main() -> None:
    """
    Simple command-line verification.
    """

    records = discover_faculty()

    print(f"Faculty discovered: {len(records)}")
    print("-" * 80)

    for index, record in enumerate(records, start=1):
        print(f"{index}. {record.name}")
        print(f"   Profile: {record.profile_url}")


if __name__ == "__main__":
    main()
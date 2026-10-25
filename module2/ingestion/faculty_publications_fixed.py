from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
import re
from typing import Any
from urllib.parse import urljoin
from urllib.request import Request, urlopen

import fitz


PUBLICATION_TYPES = {
    "JOURNAL",
    "CONFERENCE",
    "BOOK",
    "BOOK_CHAPTER",
}


# ---------------------------------------------------------------------------
# Raw extraction model
# ---------------------------------------------------------------------------

@dataclass
class RawPublicationItem:
    raw_text: str
    source_category: str
    source_identifier: str | None = None
    source_year: int | None = None
    source_page: int | None = None
    source_url: str | None = None
    source_document: str | None = None
    faculty_name: str | None = None
    raw_metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Normalized publication model
# ---------------------------------------------------------------------------

@dataclass
class PublicationRecord:
    title: str
    publication_type: str
    journal_or_conference: str | None = None
    publisher: str | None = None
    publication_date: date | None = None
    publication_year: int | None = None
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    doi: str | None = None
    indexing_information: str | None = None
    impact_information: str | None = None
    authors: str | None = None
    source_url: str | None = None
    source_document: str | None = None
    raw_metadata: dict[str, Any] = field(default_factory=dict)
    faculty_name: str | None = None


# ---------------------------------------------------------------------------
# Publication source
# ---------------------------------------------------------------------------

@dataclass
class PublicationSource:
    faculty_name: str
    source_url: str
    source_document: str | None = None
    source_category: str | None = None


# ---------------------------------------------------------------------------
# Generic HTML text parser
# ---------------------------------------------------------------------------

class _HTMLTextParser(HTMLParser):
    def __init__(self):
        super().__init__()

        self.parts: list[str] = []
        self.links: list[dict[str, str]] = []

        self._in_anchor = False
        self._anchor_href = ""
        self._anchor_parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        attributes = dict(attrs)

        if tag == "a":
            self._in_anchor = True
            self._anchor_href = attributes.get("href", "")
            self._anchor_parts = []

    def handle_data(self, data):
        text = " ".join(data.split())

        if not text:
            return

        self.parts.append(text)

        if self._in_anchor:
            self._anchor_parts.append(text)

    def handle_endtag(self, tag):
        if tag.lower() != "a":
            return

        if self._in_anchor:
            text = " ".join(
                " ".join(self._anchor_parts).split()
            )

            self.links.append(
                {
                    "text": text,
                    "href": self._anchor_href,
                }
            )

        self._in_anchor = False
        self._anchor_href = ""
        self._anchor_parts = []

    def text(self) -> str:
        return "\n".join(self.parts)


class _HTMLStructureParser(HTMLParser):
    """Collect HTML text in semantic blocks without requiring a fixed layout."""

    BLOCK_TAGS = {"tr", "li", "p", "dt", "dd", "h1", "h2", "h3", "h4", "h5", "h6"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks: list[dict[str, Any]] = []
        self._active: list[dict[str, Any]] = []
        self._all_text: list[str] = []
        self._counter = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in self.BLOCK_TAGS:
            self._counter += 1
            block = {"tag": tag, "parts": [], "order": self._counter}
            self._active.append(block)

    def handle_data(self, data):
        text = " ".join(data.split())
        if not text:
            return
        self._all_text.append(text)
        for block in self._active:
            block["parts"].append(text)

    def handle_endtag(self, tag):
        tag = tag.lower()
        for index in range(len(self._active) - 1, -1, -1):
            if self._active[index]["tag"] == tag:
                block = self._active.pop(index)
                text = " ".join(" ".join(block["parts"]).split()).strip()
                if text:
                    self.blocks.append({"tag": tag, "text": text, "order": block["order"]})
                break

    def text(self) -> str:
        return "\n".join(self._all_text)

    def preferred_blocks(self) -> list[dict[str, Any]]:
        # MNNIT publication pages commonly use <dt> section headings and
        # <dd> publication entries. Preserve both in their original order.
        definition_entries = [block for block in self.blocks if block["tag"] == "dd"]
        if definition_entries:
            headings = [
                block for block in self.blocks
                if block["tag"].startswith("h") or block["tag"] == "dt"
            ]
            return sorted(definition_entries + headings, key=lambda block: block["order"])

        # Other faculty pages use tables, lists, or paragraphs.
        for tag in ("tr", "li", "p"):
            chosen = [block for block in self.blocks if block["tag"] == tag]
            if chosen:
                headings = [block for block in self.blocks if block["tag"].startswith("h")]
                return sorted(chosen + headings, key=lambda block: block["order"])
        return sorted(self.blocks, key=lambda block: block["order"])


# ---------------------------------------------------------------------------
# Publication extraction
# ---------------------------------------------------------------------------

class _PublicationExtractor:
    """
    Extract raw publication records from faculty publication PDFs.

    Supports heading-based sections and common record markers:
    [J11], [C15], [B1], [BC2], [1], 1., and 1).
    Source headings and identifiers are retained as extraction metadata.
    """

    # Explicit category words are used rather than assuming every faculty PDF
    # follows the same heading names or ordering.
    HEADING_CATEGORY_PATTERNS = [
        ("BOOK_CHAPTER", re.compile(
            r"^(?:book\s+chapters?|chapters?\s+in\s+books?)(?:\s*\([^()\n]{1,50}\))?$", re.I)),
        ("CONFERENCE", re.compile(
            r"^(?:(?:international\s+)?conference\s+(?:papers?|proceedings?)"
            r"|published\s+conferences?"
            r"|proceedings\s+of\s+(?:the\s+)?(?:international\s+)?conferences?)"
            r"(?:\s*\([^()\n]{1,50}\))?$", re.I)),
        ("BOOK", re.compile(
            r"^(?:monographs?|books?|textbooks?)(?:\s*\([^()\n]{1,50}\))?$", re.I)),
        ("JOURNAL", re.compile(
            r"^(?:(?:(?:international|national)\s+)?journal\s+(?:papers?|articles?|publications?)"
            r"|published\s+journals?"
            r"|research\s+papers?(?:\s*\(\s*journals?\s*\))?)"
            r"(?:\s*\([^()\n]{1,50}\))?$", re.I)),
    ]

    # Headings are recognized as whole logical lines by _find_sections. These
    # patterns merely insert boundaries when PDF extraction joins headings to
    # surrounding text on the same line.
    HEADING_BOUNDARY_PATTERNS = [
        r"(?:International\s+|National\s+)?Journal\s+(?:Papers?|Articles?|Publications?)",
        r"Published\s+Journals?",
        r"Research\s+Papers?(?:\s*\(\s*Journals?\s*\))?",
        r"Book\s+Chapters?",
        r"Chapters?\s+in\s+Books?",
        r"(?:International\s+)?Conference\s+(?:Papers?|Proceedings?)",
        r"Published\s+Conferences?",
        r"Proceedings\s+of\s+(?:the\s+)?(?:International\s+)?Conferences?",
        r"Monographs?",
        r"Book\s*:",
        r"Books?(?=\s*\[(?:BC|BOOK|B)?\s*\d{1,3}\])",
        r"Textbooks?",
        r"Patents?",
        r"Sponsored\s+Projects?",
        r"Research\s+Projects?",
        r"Project\s+Grants?",
        r"Other\s+Academic\s+Achievements",
        r"Thesis\s+Supervised",
        r"Professional\s+Experience",
        r"Work\s+Experience",
        r"Education(?:al\s+Qualifications?)?",
        r"Responsibilities",
        r"Funding",
        r"Curriculum\s+Vitae",
    ]

    # Bracketed source IDs are common in some MNNIT CV PDFs. The numeric
    # fallback handles other faculty PDFs using ordinary list numbering.
    BRACKETED_MARKER_PATTERN = re.compile(
        r"(?<!\w)\[(?P<prefix>JOURNAL|J|CONF|CONFERENCE|BC|CH|BOOK|B|C)?"
        r"\s*[-.]?\s*(?P<number>\d{1,3})\](?!\w)",
        re.I,
    )
    NUMBER_PATTERN = re.compile(
        r"(?<![\w/])(?P<number>\d{1,3})[.)][ \t]+(?=[A-Z\"“‘])"
    )
    GLUED_NUMBER_PATTERN = re.compile(r"((?:19|20)\d{2})(\d{1,3})\.(?=\s)")

    NON_PUBLICATION_HEADING_PATTERN = re.compile(
        r"^(?:patents?|sponsored\\s+projects?|research\\s+projects?|"
        r"project\\s+grants?|other\\s+academic\\s+achievements|"
        r"thesis\\s+supervised|professional\\s+experience|work\\s+experience|"
        r"education(?:al\\s+qualifications?)?|responsibilities|funding|"
        r"curriculum\\s+vitae|administrative\\s+experience|awards?"
        r"(?:\\s+and\\s+achievements?)?)"
        r"(?:\\s*\\(\\s*\\d+\\s*\\))?\\s*:?$",
        re.I,
    )

    def __init__(self, faculty_name: str = ""):
        self.faculty_name = faculty_name

    @staticmethod
    def _normalize_text(text: str) -> str:
        text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\f", "\n")
        text = re.sub(r"[ \t]+", " ", text)
        return text

    @classmethod
    def _repair_glued_record_numbers(cls, text: str) -> str:
        return cls.GLUED_NUMBER_PATTERN.sub(r"\1\n\2.", text)

    @classmethod
    def _insert_heading_boundaries(cls, text: str) -> str:
        publication_boundary_patterns = [
            r"(?:International\s+|National\s+)?Journal\s+(?:Papers?|Articles?|Publications?)",
            r"Published\s+Journals?",
            r"Research\s+Papers?(?:\s*\(\s*Journals?\s*\))?",
            r"Book\s+Chapters?",
            r"Chapters?\s+in\s+Books?",
            r"(?:International\s+)?Conference\s+(?:Papers?|Proceedings?)",
            r"Published\s+Conferences?",
            r"Proceedings\s+of\s+(?:the\s+)?(?:International\s+)?Conferences?",
            r"Monographs?",
            r"Book\s*:",
            r"Books?(?=\s*\[(?:BC|BOOK|B)?\s*\d{1,3}\])",
            r"Textbooks?",
        ]
        stop_boundary_patterns = [
            r"Patents?",
            r"Sponsored\s+Projects?",
            r"Research\s+Projects?",
            r"Project\s+Grants?",
            r"Other\s+Academic\s+Achievements",
            r"Thesis\s+Supervised",
            r"Professional\s+Experience",
            r"Work\s+Experience",
            r"Education(?:al\s+Qualifications?)?",
            r"Responsibilities",
            r"Funding",
            r"Curriculum\s+Vitae",
        ]

        for pattern in publication_boundary_patterns:
            # A heading joined to text is separated only when a record marker
            # follows it; otherwise the same phrase could be part of a citation.
            text = re.sub(
                rf"(?i)(?<![A-Za-z])({pattern})(?=\s*(?:\([^()\n]{{1,50}}\)\s*)?(?:\[|(?:\d{{1,3}})[.)]))",
                r"\n\1\n",
                text,
            )

        for pattern in stop_boundary_patterns:
            # Stop-section labels are less likely to occur in citation titles,
            # but are still only split when they are heading-like (line start
            # or immediately after punctuation in flattened text).
            text = re.sub(
                rf"(?i)(?<![A-Za-z])({pattern})(?=\s*(?:\n|$|:))",
                r"\n\1\n",
                text,
            )
        return text

    @classmethod
    def prepare_text(cls, text: str) -> str:
        text = cls._normalize_text(text)
        text = cls._repair_glued_record_numbers(text)
        return cls._insert_heading_boundaries(text)

    @classmethod
    def _category_for_heading(cls, heading: str) -> str | None:
        normalized = re.sub(r"\s+", " ", heading).strip()
        # Ignore optional count suffixes often printed next to section titles.
        normalized = re.sub(r"\s*\(\s*\d+\s*\)\s*$", "", normalized).strip(" :")
        normalized = normalized.rstrip(":").strip()
        for category, pattern in cls.HEADING_CATEGORY_PATTERNS:
            if pattern.fullmatch(normalized):
                return category
        return None

    @classmethod
    def _find_sections(cls, text: str) -> list[dict[str, Any]]:
        """Find publication section headings and non-publication stop headings."""
        matches: list[dict[str, Any]] = []
        for match in re.finditer(r"(?m)^[ \t]*(?P<heading>[^\n]{1,120})[ \t]*$", text):
            heading = match.group("heading").strip()
            category = cls._category_for_heading(heading)
            if category is not None:
                matches.append({
                    "category": category, "heading": heading,
                    "start": match.start(), "end": match.end(),
                })
            elif cls.NON_PUBLICATION_HEADING_PATTERN.fullmatch(heading):
                matches.append({
                    "category": None, "heading": heading,
                    "start": match.start(), "end": match.end(),
                })

        matches.sort(key=lambda item: (item["start"], item["end"]))
        deduplicated: list[dict[str, Any]] = []
        for item in matches:
            if deduplicated and item["start"] < deduplicated[-1]["end"]:
                previous = deduplicated[-1]
                if item["end"] - item["start"] > previous["end"] - previous["start"]:
                    deduplicated[-1] = item
                continue
            deduplicated.append(item)
        return deduplicated

    @classmethod
    def _record_marker_matches(cls, section_text: str):
        """Return source markers in text order, avoiding duplicate marker matches."""
        matches = []
        for match in cls.BRACKETED_MARKER_PATTERN.finditer(section_text):
            matches.append({
                "match": match,
                "identifier": f"{(match.group('prefix') or '').upper()}{match.group('number')}",
                "prefix": (match.group("prefix") or "").upper(),
                "kind": "bracketed",
            })
        for match in cls.NUMBER_PATTERN.finditer(section_text):
            matches.append({
                "match": match,
                "identifier": match.group("number"),
                "prefix": "",
                "kind": "numbered",
            })
        matches.sort(key=lambda item: (item["match"].start(), item["match"].end()))

        # Bracketed IDs are authoritative. Suppress numeric matches that overlap
        # a bracket marker or occur within its immediate marker text.
        result = []
        for item in matches:
            match = item["match"]
            if any(
                previous["kind"] == "bracketed"
                and previous["match"].start() <= match.start() <= previous["match"].end()
                for previous in result
            ):
                continue
            result.append(item)
        return result

    @staticmethod
    def _category_from_marker(prefix: str, section_category: str) -> str:
        if prefix in {"J", "JOURNAL"}:
            return "JOURNAL"
        if prefix in {"C", "CONF", "CONFERENCE"}:
            return "CONFERENCE"
        if prefix in {"BC", "CH"}:
            return "BOOK_CHAPTER"
        if prefix in {"B", "BOOK"}:
            # Some CVs use B for books and others use it for a book/chapter
            # subsection. Preserve the explicit heading when it clarifies this.
            return "BOOK_CHAPTER" if section_category == "BOOK_CHAPTER" else "BOOK"
        return section_category

    @classmethod
    def _extract_numbered_records(
        cls,
        section_text: str,
        category: str,
        section_heading: str,
        base_offset: int,
        faculty_name: str,
        source_document: str | None,
        source_url: str | None,
        page_for_offset,
    ) -> list[RawPublicationItem]:
        matches = cls._record_marker_matches(section_text)
        if not matches:
            return []

        records: list[RawPublicationItem] = []
        for index, item in enumerate(matches):
            match = item["match"]
            start = match.end()
            end = matches[index + 1]["match"].start() if index + 1 < len(matches) else len(section_text)
            raw_text = section_text[start:end].strip(" \t\r\n.;:-")
            raw_text = re.sub(r"\s+", " ", raw_text).strip()
            if not raw_text:
                continue

            identifier = item["identifier"]
            record_category = cls._category_from_marker(item["prefix"], category)
            absolute_start = base_offset + match.start()
            source_page = page_for_offset(absolute_start) if page_for_offset else None
            source_year = _extract_year(raw_text)

            records.append(RawPublicationItem(
                raw_text=raw_text,
                source_category=record_category,
                source_identifier=identifier,
                source_year=source_year,
                source_page=source_page,
                source_url=source_url,
                source_document=source_document,
                faculty_name=faculty_name,
                raw_metadata={
                    "section_heading": section_heading,
                    "record_number": identifier,
                    "marker_prefix": item["prefix"] or None,
                    "marker_style": item["kind"],
                },
            ))
        return records

    def extract_from_pdf(
        self,
        pages: list[str],
        source_document: str | None = None,
        source_url: str | None = None,
    ) -> list[RawPublicationItem]:
        page_starts: list[int] = []
        combined_parts: list[str] = []
        current_offset = 0
        for page_text in pages:
            page_starts.append(current_offset)
            normalized_page = page_text or ""
            combined_parts.append(normalized_page)
            current_offset += len(normalized_page) + 2

        combined_text = self.prepare_text("\n\n".join(combined_parts))
        sections = self._find_sections(combined_text)
        if not sections:
            return []

        def page_for_offset(offset: int) -> int | None:
            page_number = 1
            for index, start in enumerate(page_starts):
                if start <= offset:
                    page_number = index + 1
                else:
                    break
            return page_number

        records: list[RawPublicationItem] = []
        for index, section in enumerate(sections):
            if section["category"] is None:
                continue
            section_start = section["end"]
            section_end = sections[index + 1]["start"] if index + 1 < len(sections) else len(combined_text)
            section_text = combined_text[section_start:section_end]
            records.extend(self._extract_numbered_records(
                section_text=section_text,
                category=section["category"],
                section_heading=section["heading"],
                base_offset=section_start,
                faculty_name=self.faculty_name,
                source_document=source_document,
                source_url=source_url,
                page_for_offset=page_for_offset,
            ))
        return records


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

def _clean_text(text: str) -> str:
    return " ".join(
        text.replace("\n", " ").split()
    ).strip()


def _normalize_whitespace(text: str) -> str:
    return _clean_text(text)


def _extract_year(text: str) -> int | None:
    """
    Extract a plausible publication year.

    Prefer years in the normal publication range rather than arbitrary
    four-digit numbers appearing in titles or page information.
    """

    years = re.findall(
        r"\b((?:19|20)\d{2})\b",
        text,
    )

    if not years:
        return None

    candidates = [
        int(year)
        for year in years
        if 1900 <= int(year) <= 2100
    ]

    if not candidates:
        return None

    return candidates[-1]


def _extract_doi(text: str) -> str | None:
    match = re.search(
        r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b",
        text,
        re.IGNORECASE,
    )

    if not match:
        return None

    return match.group(0).rstrip(
        ".,;)"
    )


def _extract_volume_issue_pages(
    text: str,
) -> tuple[str | None, str | None, str | None]:

    volume = None
    issue = None
    pages = None

    volume_issue = re.search(
        r"\b(\d{1,4})\s*\(\s*(\d{1,4})\s*\)",
        text,
    )

    if volume_issue:
        volume = volume_issue.group(1)
        issue = volume_issue.group(2)

    page_match = re.search(
        r"\b(?:pp?\.?\s*)?(\d{1,6}\s*[-–]\s*\d{1,6})\b",
        text,
        re.IGNORECASE,
    )

    if page_match:
        pages = page_match.group(1)

    return volume, issue, pages


def _extract_indexing(text: str) -> str | None:
    patterns = [
        r"\bSCIE\b",
        r"\bESCI\b",
        r"\bScopus\b",
        r"\bWeb of Science\b",
        r"\bUGC\b",
        r"\bSCI\b",
    ]

    found = []

    for pattern in patterns:
        match = re.search(
            pattern,
            text,
            re.IGNORECASE,
        )

        if match:
            found.append(
                match.group(0)
            )

    if not found:
        return None

    unique = []

    for item in found:
        if item.lower() not in {
            value.lower()
            for value in unique
        }:
            unique.append(item)

    return ", ".join(unique)


def _extract_impact(text: str) -> str | None:
    match = re.search(
        r"(?:impact\s*factor|IF)\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)",
        text,
        re.IGNORECASE,
    )

    if not match:
        return None

    return match.group(1)


# ---------------------------------------------------------------------------
# Publication normalizer
# ---------------------------------------------------------------------------

class PublicationNormalizer:
    """
    Convert RawPublicationItem into homogeneous PublicationRecord data.

    No source-specific numbering is used as database identity.
    """

    def normalize(
        self,
        item: RawPublicationItem,
    ) -> PublicationRecord:

        raw_text = _normalize_whitespace(
            item.raw_text
        )

        publication_year = (
            item.source_year
            or _extract_year(raw_text)
        )

        doi = _extract_doi(
            raw_text
        )

        volume, issue, pages = (
            _extract_volume_issue_pages(
                raw_text
            )
        )

        indexing = _extract_indexing(
            raw_text
        )

        impact = _extract_impact(
            raw_text
        )

        title = self._extract_title(
            raw_text,
            item.source_category,
        )

        return PublicationRecord(
            title=title,
            publication_type=item.source_category,
            publication_year=publication_year,
            volume=volume,
            issue=issue,
            pages=pages,
            doi=doi,
            indexing_information=indexing,
            impact_information=impact,
            source_url=item.source_url,
            source_document=item.source_document,
            faculty_name=item.faculty_name,
            raw_metadata={
                **item.raw_metadata,
                "source_identifier": (
                    item.source_identifier
                ),
                "source_year": (
                    item.source_year
                ),
                "source_page": (
                    item.source_page
                ),
                "raw_text": item.raw_text,
            },
        )

    @staticmethod
    def _extract_title(
        raw_text: str,
        publication_type: str,
    ) -> str:

        text = raw_text

        # Remove leading author/reference labels where obvious.
        text = re.sub(
            r"^\s*(?:authors?|by)\s*:\s*",
            "",
            text,
            flags=re.IGNORECASE,
        )

        # Remove DOI.
        text = re.sub(
            r"\bdoi\s*:\s*10\.\S+",
            "",
            text,
            flags=re.IGNORECASE,
        )

        # Remove trailing indexing/impact metadata.
        text = re.sub(
            r"\b(?:SCIE|ESCI|Scopus|SCI|Web of Science)\b",
            "",
            text,
            flags=re.IGNORECASE,
        )

        text = re.sub(
            r"(?:impact\s*factor|IF)\s*[:=]?\s*[0-9]+(?:\.[0-9]+)?",
            "",
            text,
            flags=re.IGNORECASE,
        )

        text = _normalize_whitespace(
            text
        )

        return text


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def _deduplication_key(
    publication: PublicationRecord,
) -> tuple:

    if publication.doi:
        return (
            "DOI",
            publication.doi.lower().strip(),
        )

    normalized_title = re.sub(
        r"[^a-z0-9]+",
        " ",
        publication.title.lower(),
    )

    normalized_title = " ".join(
        normalized_title.split()
    )

    return (
        "TITLE",
        normalized_title,
        publication.publication_type,
        publication.publication_year,
    )


def deduplicate_publications(
    publications: list[PublicationRecord],
) -> list[PublicationRecord]:

    seen: set[tuple] = set()
    result: list[PublicationRecord] = []

    for publication in publications:
        key = _deduplication_key(
            publication
        )

        if key in seen:
            continue

        seen.add(key)
        result.append(publication)

    return result


# ---------------------------------------------------------------------------
# PDF extraction
# ---------------------------------------------------------------------------

def extract_pdf_text(
    pdf_path: str | Path,
) -> list[str]:

    path = Path(pdf_path)

    if not path.exists():
        raise FileNotFoundError(
            f"PDF not found: {path}"
        )

    pages: list[str] = []

    with fitz.open(path) as document:
        for page in document:
            pages.append(
                page.get_text("text")
            )

    return pages


def extract_raw_publications_from_pdf(
    pdf_path: str | Path,
    faculty_name: str = "",
    source_url: str | None = None,
) -> list[RawPublicationItem]:

    path = Path(pdf_path)

    pages = extract_pdf_text(
        path
    )

    extractor = _PublicationExtractor(
        faculty_name=faculty_name
    )

    return extractor.extract_from_pdf(
        pages=pages,
        source_document=path.name,
        source_url=source_url,
    )


def parse_publication_pdf(
    pdf_path: str | Path,
    faculty_name: str = "",
    source_url: str | None = None,
) -> list[PublicationRecord]:

    raw_items = extract_raw_publications_from_pdf(
        pdf_path=pdf_path,
        faculty_name=faculty_name,
        source_url=source_url,
    )

    normalizer = PublicationNormalizer()

    normalized = [
        normalizer.normalize(item)
        for item in raw_items
    ]

    return deduplicate_publications(
        normalized
    )


# ---------------------------------------------------------------------------
# HTML extraction
# ---------------------------------------------------------------------------

def _category_from_heading(text: str) -> str | None:
    value = re.sub(r"\s+", " ", text).strip().lower()
    if re.search(r"\b(book\s+chapters?|chapters\s+in\s+books?)\b", value):
        return "BOOK_CHAPTER"
    if re.search(r"\b(conference|proceedings|symposium|workshop|seminar)\b", value):
        return "CONFERENCE"
    if re.search(r"\b(books?|textbooks?)\b", value) and not re.search(r"\b(book\s+chapters?)\b", value):
        return "BOOK"
    if re.search(r"\b(journal|journals|research\s+papers?)\b", value):
        return "JOURNAL"
    return None


def _looks_like_non_publication_section(text: str) -> bool:
    return bool(re.search(
        r"\b(patents?|project\s+(?:grant|fund|proposal|details?)|sponsored\s+projects?|"
        r"research\s+projects?|funding|grant\s+details?|work\s+experience|"
        r"professional\s+experience|qualifications?|education|responsibilities|"
        r"thesis\s+supervised|students?\s+supervised|awards?|achievements?|"
        r"administrative\s+experience|personal\s+details|curriculum\s+vitae)\b",
        text, re.IGNORECASE
    ))


def _infer_publication_category(text: str, current: str | None) -> str | None:
    if current:
        return current
    lowered = text.lower()
    if re.search(r"\b(in\s*:|book\s+chapter|chapter\s+\d+|edited\s+by)\b", lowered):
        return "BOOK_CHAPTER"
    if re.search(r"\b(conference|proceedings|symposium|workshop|international\s+conference)\b", lowered):
        return "CONFERENCE"
    if re.search(r"\b(publisher|press|isbn|textbook|edition)\b", lowered) and not re.search(r"\b(journal|vol\.?|doi)\b", lowered):
        return "BOOK"
    if re.search(r"\b(journal|doi|volume|vol\.?|issue|issn)\b|10\.\d{4,9}/", lowered):
        return "JOURNAL"
    return None


def _split_numbered_html_text(text: str) -> list[tuple[str, str | None]]:
    """Split numbered citations while tolerating numbering not at line starts."""
    pattern = re.compile(r"(?<!\w)(\d{1,3})\s*[.)]\s+(?=[A-Z\"“‘])")
    matches = list(pattern.finditer(text))
    if not matches:
        return [(text.strip(), None)] if text.strip() else []
    if len(matches) == 1:
        match = matches[0]
        # Strip a single leading list number; retain numbers embedded in prose.
        if match.start() <= 3:
            item = text[match.end():].strip(" \t\r\n.;")
            return [(item, match.group(1))] if item else []
        return [(text.strip(), None)]
    result = []
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        item = text[match.end():end].strip(" \t\r\n.;")
        if item:
            result.append((item, match.group(1)))
    return result


def extract_raw_publications_from_html(
    html: str,
    faculty_name: str = "",
    source_url: str | None = None,
    source_document: str | None = None,
) -> list[RawPublicationItem]:
    """Extract records from varied HTML layouts, retaining source evidence.

    HTML is handled structurally first (table rows/list items/paragraphs). A
    flat-text numbered fallback is used only when structural extraction yields
    no records. Oversized merged blocks are rejected instead of being saved as
    one misleading publication; the caller can then try an official PDF link.
    """
    parser = _HTMLStructureParser()
    parser.feed(html)
    parser.close()

    blocks = parser.preferred_blocks()
    records: list[RawPublicationItem] = []
    current_category: str | None = None

    for block in blocks:
        text = re.sub(r"\s+", " ", block["text"]).strip()
        if not text:
            continue

        heading_category = _category_from_heading(text)
        is_heading_block = block["tag"].startswith("h") or (
            len(text) < 90 and not re.search(r"\b(doi|19\d{2}|20\d{2}|https?://|vol\.?|issue)\b", text, re.I)
        )
        if heading_category and is_heading_block:
            current_category = heading_category
            continue
        # A publication citation may mention awards, projects, or other
        # terms that also appear in non-publication headings. Only treat
        # non-publication blocks as section boundaries, never <dd> citations.
        if block["tag"] != "dd" and _looks_like_non_publication_section(text):
            current_category = None
            continue

        # Rows that are just labels/headers should not become publications.
        if len(text) < 35 and not re.search(r"\b(doi|19\d{2}|20\d{2}|conference|journal)\b", text, re.I):
            continue

        pieces = _split_numbered_html_text(text)
        for piece, identifier in pieces:
            if not piece:
                continue
            # A giant block usually means the HTML layout has been flattened
            # into one container, not that it is one valid publication.
            if len(piece) > 1800:
                continue
            category = _infer_publication_category(piece, current_category)
            if category is None:
                continue
            records.append(RawPublicationItem(
                raw_text=piece,
                source_category=category,
                source_identifier=identifier,
                source_year=_extract_year(piece),
                source_url=source_url,
                source_document=source_document,
                faculty_name=faculty_name,
                raw_metadata={"html_block_tag": block["tag"], "extraction_method": "structured_html"},
            ))

    # If structural parsing did not identify any records, attempt the existing
    # section/number parser on flattened text, but reject suspicious mega-records.
    if not records:
        text = parser.text()
        extractor = _PublicationExtractor(faculty_name=faculty_name)
        raw_items = extractor.extract_from_pdf(
            pages=[text], source_document=source_document, source_url=source_url
        )
        records = [item for item in raw_items if len(item.raw_text) <= 1800]

    return records


def parse_publication_html(
    html: str,
    faculty_name: str = "",
    source_url: str | None = None,
    source_document: str | None = None,
) -> list[PublicationRecord]:

    raw_items = extract_raw_publications_from_html(
        html=html,
        faculty_name=faculty_name,
        source_url=source_url,
        source_document=source_document,
    )

    normalizer = PublicationNormalizer()

    normalized = [
        normalizer.normalize(item)
        for item in raw_items
    ]

    return deduplicate_publications(
        normalized
    )


# ---------------------------------------------------------------------------
# Source discovery helpers
# ---------------------------------------------------------------------------

def _find_embedded_pdf_url(
    html: str,
    base_url: str,
) -> str | None:

    parser = _HTMLTextParser()

    parser.feed(html)
    parser.close()

    for link in parser.links:
        href = link.get(
            "href",
            "",
        ).strip()

        if not href:
            continue

        if ".pdf" in href.lower():
            return urljoin(
                base_url,
                href,
            )

        text = link.get(
            "text",
            "",
        ).lower()

        if "publication" in text and (
            "pdf" in text
            or ".pdf" in href.lower()
        ):
            return urljoin(
                base_url,
                href,
            )

    pdf_match = re.search(
        r"""(?:href|src)\s*=\s*["']([^"']+\.pdf(?:\?[^"']*)?)["']""",
        html,
        re.IGNORECASE,
    )

    if pdf_match:
        return urljoin(
            base_url,
            pdf_match.group(1),
        )

    return None


def fetch_publication_source(
    url: str,
) -> tuple[bytes, str, str]:

    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "Chrome/153.0 Safari/537.36"
            )
        },
    )

    with urlopen(
        request,
        timeout=30,
    ) as response:

        content = response.read()

        content_type = (
            response.headers.get(
                "Content-Type",
                "",
            )
        )

        final_url = response.geturl()

    return (
        content,
        content_type,
        final_url,
    )


def download_publication_pdf(
    url: str,
    output_path: str | Path,
) -> Path:

    content, content_type, final_url = (
        fetch_publication_source(url)
    )

    if (
        "pdf" not in content_type.lower()
        and not final_url.lower().split("?")[0].endswith(".pdf")
    ):
        raise ValueError(
            f"Source does not appear to be a PDF: "
            f"{final_url}"
        )

    path = Path(output_path)

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_bytes(
        content
    )

    return path


# ---------------------------------------------------------------------------
# Simple manual verification
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    pdf = Path(
        "module2/ingestion/"
        "debug_publication_structures/pdf/"
        "prof_d_s_kushwaha.pdf"
    )

    if not pdf.exists():
        print(
            f"PDF not found: {pdf}"
        )
        raise SystemExit(1)

    raw = extract_raw_publications_from_pdf(
        pdf,
        "Prof. D.S. Kushwaha",
    )

    from collections import Counter

    counts = Counter(
        item.source_category
        for item in raw
    )

    print(
        f"RAW ITEMS: {len(raw)}"
    )

    print(
        f"COUNTS: {dict(counts)}"
    )

    if raw:
        print(
            "FIRST:",
            raw[0].source_category,
            raw[0].source_identifier,
            raw[0].source_year,
            raw[0].source_page,
        )

        print(
            "LAST:",
            raw[-1].source_category,
            raw[-1].source_identifier,
            raw[-1].source_year,
            raw[-1].source_page,
        )
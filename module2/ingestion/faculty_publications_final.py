from __future__ import annotations

"""Layout-tolerant PDF publication extraction for DepartmentAI Module II."""
from pathlib import Path
import re
from typing import Any
import fitz

from module2.ingestion.faculty_publications_fixed import (
    PublicationNormalizer, PublicationRecord, RawPublicationItem,
)

MARKER = re.compile(r"(?m)^[ \t]*\[(?P<kind>BCh|J|C|B)\s*(?P<num>\d+)\][ \t]*", re.I)
BRACKET_NUMBER = re.compile(r"(?m)^[ \t]*\[(?P<num>\d{1,3})\][ \t]*")
NUMBER = re.compile(r"(?m)^[ \t]*(?P<num>\d{1,3})(?:[.)][ \t]+|[ \t]{2,})(?=[A-Z0-9\"“‘(\[])")
BULLET = re.compile(r"(?m)^[ \t]*(?:[•●▪◦]\s+|[-–]\s{2,})(?=[A-Z\"“‘(\[])")
STANDALONE = re.compile(r"(?m)^[ \t]*(?P<num>\d{1,3})(?P<dot>[.]?)[ \t]*$")
GLUED = re.compile(r"((?:19|20)\d{2})(\d{1,3})\.(?=\s)")

STOP = re.compile(r"^(?:patents?|sponsored projects?|completed research grants?(?:\s*/\s*projects?)?|research projects?|project grants?|other academic achievements|thesis supervised|ph\.?d\.? thesis supervised|m\.?tech\.? thesis supervised|b\.?tech\.? project supervised|responsibilities|education|professional experience|work experience|funding|curriculum vitae|other details|invited talks?|awards?|consultancy|session chaired(?: in international conferences?)?|workshops?/fdp organized|outreach activities|participated)\b", re.I)


def _clean_heading(line: str) -> str:
    line = re.sub(r"\s+", " ", line).strip()
    line = re.sub(r"^[\s•●▪◦]+", "", line)
    return re.sub(r"^\d{1,2}[.\-)]\s*", "", line).strip()


def _category_heading(line: str) -> str | None:
    value = _clean_heading(line).lower().strip(" :.-")
    if not value or len(value) > 180:
        return None
    if re.fullmatch(r"(?:list of )?(?:research )?publications?", value) or value.startswith("research contributions at a glance"):
        return None
    if "books and chapters" in value or re.match(r"^conferences\s+international:", value):
        return None
    if re.match(r"^(?:international|national) journals?\s+of\b", value):
        return None
    if re.match(r"^(?:international|national) conferences?\s+(?:on|in)\b", value):
        return None
    if re.match(r"^(?:journal|journals)\s+of\b", value) or re.match(r"^proceedings?\s+of\b", value):
        return None
    if re.match(r"^(?:research papers? in|publication in journals?|publication in conferences?|papers in conference proceedings|papers published/accepted in conference proceedings|published journals?|published conferences?|sci(?:/|[-\s]).*journals?|scopus index conferences?)\b", value):
        if re.search(r"\bconference|proceedings\b", value):
            return "CONFERENCE"
        return "JOURNAL"
    if re.fullmatch(r"journal papers? published / accepted", value):
        return "JOURNAL"
    if re.fullmatch(r"conference papers? published(?: / accepted)?", value):
        return "CONFERENCE"
    if re.fullmatch(r"(?:international|national) journals?(?:\s*\([^)]*\))?(?:\s*:\s*.*)?", value):
        return "JOURNAL"
    if re.fullmatch(r"(?:international|national) conferences?(?:\s*\([^)]*\))?(?:\s*:\s*.*)?", value):
        return "CONFERENCE"
    if re.fullmatch(r"journals?(?:\s*\([^)]*\))?(?:\s*:\s*.*)?", value) or re.fullmatch(r"journal(?: papers?| articles?| publications?)(?:\s*\([^)]*\))?(?:\s*:\s*.*)?", value):
        return "JOURNAL"
    if re.fullmatch(r"(?:conference(?:s| papers?| proceedings?| publications?)|proceedings|papers in conference proceedings)(?:\s*\([^)]*\))?(?:\s*:\s*.*)?", value):
        return "CONFERENCE"
    if re.fullmatch(r"(?:book chapters?|chapters? in books?)(?:\s*\([^)]*\))?(?:\s*:\s*.*)?", value):
        return "BOOK_CHAPTER"
    if re.fullmatch(r"books?(?:\s*:\s*.*)?", value):
        return "BOOK"
    return None


def _is_heading(line: str) -> bool:
    value = _clean_heading(line)
    low = value.lower().strip(" :.-")
    if not value or len(value) > 180:
        return False
    if STOP.match(low):
        # Do not treat a patent citation or project description as a heading.
        if re.search(r"[\"“”]", value) or re.match(r"^patents?\s+(?:published|granted|application)\b", low):
            return False
        return len(value.split()) <= 12
    if _category_heading(value) is not None:
        return True
    return bool(re.fullmatch(r"(?:list of )?(?:research )?publications?(?:\s*:\s*.*)?", low) or re.fullmatch(r"research contributions at a glance(?:\s*\([^)]*\))?", low))


def _prepare(text: str) -> str:
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n").replace("\f", "\n")
    text = text.replace("\u00a0", " ").replace("\u200b", "").replace("ﬁ", "fi").replace("ﬂ", "fl")
    text = GLUED.sub(r"\1\n\2.", text)
    # Only repair a heading glued directly to a year/punctuation; do not
    # split phrases such as "Total Book Chapters: 2" inside summary tables.
    text = re.sub(
        r"(?i)(?<=[0-9.])(?=(?:Journal\s+Papers?|Journal\s+Articles?|Published\s+Journals?|Conference\s+Papers?|Conference\s+Proceedings?|Book\s+Chapters?)\s*:)",
        "\n",
        text,
    )
    return text


def _sections(text: str) -> list[dict[str, Any]]:
    out, offset = [], 0
    for line in text.splitlines(keepends=True):
        clean = _clean_heading(line)
        if _is_heading(clean):
            out.append({"heading": clean, "category": _category_heading(clean), "start": offset, "end": offset + len(line.rstrip("\r\n"))})
        offset += len(line)
    # Keep only one marker at any one offset.
    unique = []
    for item in out:
        if unique and item["start"] == unique[-1]["start"]:
            if item["category"] and not unique[-1]["category"]:
                unique[-1] = item
        else:
            unique.append(item)
    return unique


def _infer_category(raw: str, fallback: str | None = None) -> str:
    # A clear section heading is more reliable than incidental venue words
    # appearing inside a citation.
    if fallback in {"JOURNAL", "CONFERENCE", "BOOK", "BOOK_CHAPTER"}:
        return fallback
    s = re.sub(r"\s+", " ", raw).lower()
    if re.search(r"\b(book chapter|chapter in|book title:)\b", s):
        return "BOOK_CHAPTER"
    if re.search(r"\b(proceedings?|international conference|national conference|conference on|symposium)\b", s):
        return "CONFERENCE"
    if re.search(r"\b(isbn|publisher|published by)\b", s) and not re.search(r"\b(journal|transactions|letters)\b", s):
        return "BOOK"
    return "JOURNAL"


def _is_table(text: str) -> bool:
    low = text.lower()
    return ("author" in low and "title" in low and ("sl." in low or "sl no" in low or "serial no" in low))


def _boundaries(text: str, table: bool = False):
    found = []
    for m in BRACKET_NUMBER.finditer(text):
        found.append((m.start(), m.group("num"), None))
    for m in MARKER.finditer(text):
        k = m.group("kind").upper()
        found.append((m.start(), m.group("num"), {"J": "JOURNAL", "C": "CONFERENCE", "B": None}[k]))
    for m in NUMBER.finditer(text):
        found.append((m.start(), m.group("num"), None))
    for m in BULLET.finditer(text):
        found.append((m.start(), None, None))
    # Some official faculty PDFs put the serial number on its own line and
    # start the citation on the following line (e.g. K. Sowjanya).
    for m in STANDALONE.finditer(text):
        number = m.group("num")
        if int(number) <= 150:
            tail = text[m.end():m.end() + 180]
            first_nonempty = next((line.strip() for line in tail.splitlines() if line.strip()), "")
            if first_nonempty and (m.group("dot") == "." or (len(first_nonempty) >= 8 and not re.fullmatch(r"(?:19|20)\d{2}", first_nonempty))):
                found.append((m.start(), number, None))
    found.sort(key=lambda x: x[0])
    out = []
    for item in found:
        if out and item[0] < out[-1][0] + 2:
            if item[0] == out[-1][0]:
                old = out[-1]
                out[-1] = (old[0], old[1] or item[1], old[2] or item[2])
            continue
        out.append(item)
    return out


def _raw_items_from_section(section_text: str, category: str | None, heading: str, faculty: str, document: str, url: str | None, page_starts: list[int]) -> list[RawPublicationItem]:
    table = _is_table(section_text)
    starts = _boundaries(section_text, table=table)
    records = []
    for i, (start, number, marker_category) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(section_text)
        raw = section_text[start:end].strip()
        raw = re.sub(r"^\s*(?:\[[JCB]\s*\d+\]|\[\d{1,3}\]|\d{1,3}[.)])\s*", "", raw, flags=re.I)
        # Serial numbers printed on their own line, as in K. Sowjanya's PDF.
        raw = re.sub(r"^\s*\d{1,3}[ \t]*\n\s*", "", raw)
        raw = re.sub(r"^\s*[•●▪◦]\s*", "", raw)
        raw = re.sub(r"\s+", " ", raw).strip()
        if len(raw) < 30:
            continue
        cat = marker_category or _infer_category(raw, category)
        page_no = 1
        for n, pstart in enumerate(page_starts, 1):
            if pstart <= start:
                page_no = n
            else:
                break
        meta = {"raw_text": raw, "section_heading": heading, "record_number": number, "extraction_strategy": "table_rows" if table else "section_boundaries"}
        if table:
            meta.update({"requires_review": True, "review_reason": "PDF table columns are flattened in extracted text"})
        records.append(RawPublicationItem(raw_text=raw, source_category=cat, source_identifier=number, source_page=page_no, source_url=url, source_document=document, faculty_name=faculty, raw_metadata=meta))
    return records


def _scholar_fallback(pages: list[str], faculty: str, document: str, url: str | None) -> list[RawPublicationItem]:
    """Parse Google Scholar print-to-PDF text where rows are not numbered.

    Scholar printouts flatten title, authors, venue, cited-by count and year into
    text lines. We use year boundaries plus title-like line heuristics. Metadata
    may be incomplete, so records are tagged for review rather than discarded.
    """
    all_text = "\n".join(pages)
    if not re.search(r"google scholar", all_text, re.I) or not re.search(r"\bTITLE\b.*\bCITED BY\b.*\bYEAR\b", all_text, re.I | re.S):
        return []

    def clean_line(line: str) -> str:
        line = re.sub(r"\s+", " ", line).strip()
        if not line:
            return ""
        if re.search(r"google\.scholar\.co\.in/citations|\b\d+ of \d+\b|^Notebook$|^Kapil Gupta - Google Scholar$|^TITLE$|^CITED BY$|^YEAR$", line, re.I):
            return ""
        if re.fullmatch(r"(?:All|Since \d{4}|Citations|h-index|i10-index|TITLE|CITED BY|YEAR)", line, re.I):
            return ""
        if re.fullmatch(r"\d{1,3}", line):
            return ""
        return line

    # Remove page chrome but preserve page order; the text layout often places
    # a citation's year at the end of the row, sometimes on a separate line.
    lines: list[tuple[int, str]] = []
    started = False
    for page_no, page in enumerate(pages, 1):
        for raw_line in page.splitlines():
            if not started and raw_line.strip().upper() == "YEAR":
                started = True
                continue
            line = clean_line(raw_line)
            if not line or not started:
                continue
            lines.append((page_no, line))

    # A Scholar item usually ends with a standalone year. Collect line groups
    # and use the first title-like line(s), excluding author/venue/footer rows.
    chunks: list[tuple[int, list[str]]] = []
    current: list[str] = []
    current_page = 1
    for page_no, line in lines:
        current_page = page_no
        year_match = re.fullmatch(r"(?:19|20)\d{2}", line)
        inline_year = re.search(r"\b((?:19|20)\d{2})\s*$", line)
        if year_match:
            if current:
                chunks.append((page_no, current + [line]))
                current = []
            continue
        if inline_year and len(line) > 12:
            current.append(line)
            chunks.append((page_no, current))
            current = []
            continue
        current.append(line)
        # If PDF extraction has no separate year line, keep a bounded chunk.
        if len(current) >= 9:
            chunks.append((page_no, current))
            current = []
    if current:
        chunks.append((current_page, current))

    venue_re = re.compile(r"\b(journal|transactions|conference|proceedings|springer|elsevier|ieee|systems|computing|applications|neurocomputing|multimedia tools|soft computing|knowledge-based|neural networks|signal, image)\b", re.I)
    author_re = re.compile(r"^(?:[A-Z][A-Za-z.-]*\s+){1,3}[A-Z][A-Za-z.-]*(?:,\s*(?:[A-Z.]+\s*)?[A-Z][A-Za-z.-]*)+$")
    result: list[RawPublicationItem] = []
    for page_no, chunk in chunks:
        chunk_year_match = next((re.fullmatch(r"((?:19|20)\d{2})", x) for x in chunk if re.fullmatch(r"(?:19|20)\d{2}", x)), None)
        chunk_year = int(chunk_year_match.group(1)) if chunk_year_match else None
        chunk = [x for x in chunk if x and not re.fullmatch(r"(?:19|20)\d{2}", x)]
        if not chunk:
            continue
        # Remove common page-header/profile text and year/count-only artifacts.
        chunk = [x for x in chunk if not re.search(r"^(?:all|since \d{4}|citations|h-index|i10-index|statistical machine learning|data analytics|quantum computing|nit kurukshetra)\b", x, re.I)]
        if not chunk:
            continue
        title_lines: list[str] = []
        for line in chunk:
            # Keep the first long line even when the title itself contains words
            # such as "systems", "computing", or "knowledge-based".
            if title_lines and (venue_re.search(line) or author_re.match(line) or len(line) < 15):
                break
            if not title_lines and (len(line) < 18 or author_re.match(line)):
                continue
            title_lines.append(line)
            if len(" ".join(title_lines)) >= 95:
                break
        if not title_lines:
            # Fallback: choose the longest non-venue line as a minimally useful title.
            candidates = [x for x in chunk if len(x) >= 22 and not venue_re.search(x) and not author_re.match(x)]
            if candidates:
                title_lines = [max(candidates, key=len)]
        title = re.sub(r"\s+", " ", " ".join(title_lines)).strip(" .-–")
        if not title or len(title) < 12 or len(title) > 350:
            continue
        full = " ".join(chunk)
        year_match = re.search(r"\b((?:19|20)\d{2})\b", full)
        category = _infer_category(full)
        result.append(RawPublicationItem(
            raw_text=full,
            source_category=category,
            source_year=chunk_year or (int(year_match.group(1)) if year_match else None),
            source_page=page_no,
            source_url=url,
            source_document=document,
            faculty_name=faculty,
            raw_metadata={
                "raw_text": full,
                "title_candidate": title,
                "extraction_strategy": "google_scholar_printout_year_chunks",
                "requires_review": True,
                "review_reason": "Google Scholar printout has flattened columns; metadata may be approximate",
            },
        ))

    unique: list[RawPublicationItem] = []
    seen: set[str] = set()
    for item in result:
        key = re.sub(r"\W+", " ", str(item.raw_metadata.get("title_candidate", item.raw_text)).lower()).strip()
        if key and key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def extract_raw_publications_from_pages(pages: list[str], faculty_name: str = "", source_document: str = "publications.pdf", source_url: str | None = None) -> list[RawPublicationItem]:
    cleaned_pages = []
    for page_no, page_text in enumerate(pages, 1):
        lines = (page_text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
        first = next((i for i, line in enumerate(lines) if line.strip()), None)
        if first is not None and re.fullmatch(r"\d{1,2}", lines[first].strip()) and int(lines[first].strip()) == page_no:
            lines.pop(first)
        cleaned_pages.append("\n".join(lines))
    combined = _prepare("\n\n".join(cleaned_pages))
    page_starts, offset = [], 0
    for page in pages:
        page_starts.append(offset); offset += len(page) + 2
    found: list[RawPublicationItem] = []

    # Typed [J1]/[C1]/[B1] labels are the strongest available boundaries.
    typed = list(MARKER.finditer(combined))
    if typed:
        for i, match in enumerate(typed):
            end = typed[i + 1].start() if i + 1 < len(typed) else len(combined)
            raw = re.sub(r"^\s*\[[JCB]\s*\d+\]\s*", "", combined[match.start():end].strip(), flags=re.I)
            raw = re.sub(r"\s+", " ", raw).strip()
            kind = match.group("kind").upper()
            cat = {"J": "JOURNAL", "C": "CONFERENCE", "B": "BOOK", "BCH": "BOOK_CHAPTER"}[kind]
            if len(raw) >= 30:
                found.append(RawPublicationItem(raw_text=raw, source_category=cat or _infer_category(raw), source_identifier=match.group("num"), source_url=source_url, source_document=source_document, faculty_name=faculty_name, raw_metadata={"raw_text": raw, "record_number": match.group("num"), "extraction_strategy": "typed_record_marker"}))
    else:
        sections = _sections(combined)
        for i, section in enumerate(sections):
            if not section["category"]:
                continue
            end = sections[i + 1]["start"] if i + 1 < len(sections) else len(combined)
            found.extend(_raw_items_from_section(combined[section["end"]:end], section["category"], section["heading"], faculty_name, source_document, source_url, page_starts))

    # Deduplicate marker/section paths without merging different categories.
    unique, seen = [], set()
    for item in found:
        key = (item.source_category, re.sub(r"\W+", " ", item.raw_text.lower()).strip())
        if key[1] and key not in seen:
            seen.add(key); unique.append(item)

    if not unique:
        unique = _scholar_fallback(pages, faculty_name, source_document, source_url)
    return unique



def _extract_coordinate_table_records(pdf_path: str | Path, faculty_name: str, source_url: str | None) -> list[RawPublicationItem]:
    """Recover publications from official CV PDFs whose table columns flatten badly.

    The routine discovers serial-number and title columns from the PDF's own
    header geometry, rather than assuming fixed column coordinates or a fixed
    faculty template. It is intentionally conservative: it emits a row only
    when both a serial number and a plausible title cell are present.
    """
    result: list[RawPublicationItem] = []
    try:
        document = fitz.open(pdf_path)
    except Exception:
        return result

    heading_re = re.compile(
        r"(?i)(journal papers?|journal articles?|published journals?|conference papers?|"
        r"papers published/accepted in conference proceedings|conference proceedings|"
        r"book chapters?|chapters in books?|books?)(?:\s*[:(].*)?$"
    )
    nonpub_re = re.compile(
        r"(?i)^(?:patents?|sponsored projects?|completed research grants?|research projects?|"
        r"other academic achievements|thesis supervised|responsibilities|education|funding|"
        r"awards?|invited talks?|consultancy|workshops?/fdp organized|outreach activities)\b"
    )

    for page_no, page in enumerate(document, 1):
        blocks = [b for b in page.get_text("blocks") if len(b) >= 5 and str(b[4]).strip()]
        words = page.get_text("words")
        if not blocks or not words:
            continue
        # Locate section headings by their rendered text, because PDF extractors
        # sometimes merge a heading into the previous table row's text block.
        headings = []
        heading_queries = [
            ("Papers published/accepted in Conference Proceedings", "CONFERENCE"),
            ("Conference Proceedings", "CONFERENCE"),
            ("Conference Papers", "CONFERENCE"),
            ("Conferences", "CONFERENCE"),
            ("Journal Papers", "JOURNAL"),
            ("Journal Articles", "JOURNAL"),
            ("Published Journals", "JOURNAL"),
            ("Journals", "JOURNAL"),
            ("Book Chapters", "BOOK_CHAPTER"),
            ("Chapters in Books", "BOOK_CHAPTER"),
            ("Books", "BOOK"),
        ]
        for phrase, cat in heading_queries:
            try:
                rects = page.search_for(phrase, quads=False)
            except Exception:
                rects = []
            for rect in rects:
                headings.append((float(rect.y0), float(rect.y1), cat, phrase))
        headings.sort(key=lambda h: (h[0], h[1]))
        compact_headings = []
        for h in headings:
            if compact_headings and abs(h[0] - compact_headings[-1][0]) < 4:
                # Prefer the longer/more specific heading phrase at same position.
                if len(h[3]) > len(compact_headings[-1][3]):
                    compact_headings[-1] = h
            else:
                compact_headings.append(h)
        headings = compact_headings
        # Find table headers. A usable header contains both "title" and "paper".
        title_headers = []
        for b in blocks:
            txt = re.sub(r"\s+", " ", str(b[4])).strip().lower()
            if "title" in txt and "paper" in txt:
                title_headers.append(b)
        for title_block in title_headers:
            tx0, ty0, tx1, ty1, _ = title_block[:5]
            # The serial-number column header is usually close to this header vertically.
            serial_headers = []
            for b in blocks:
                txt = re.sub(r"\s+", " ", str(b[4])).strip().lower()
                if re.search(r"\bsl\.?\s*no\.?(?:\b|$)|\bserial\s+no\.?(?:\b|$)", txt):
                    # Ignore merged content blocks that merely contain the header text.
                    if float(b[2]) - float(b[0]) <= 100:
                        distance = abs(float(b[1]) - float(ty0))
                        serial_headers.append((distance, b))
            if not serial_headers:
                continue
            serial_block = min(serial_headers, key=lambda x: x[0])[1]
            sx0, _, sx1, _, _ = serial_block[:5]

            # Infer the next column boundary from other headers on the same header row.
            next_x = None
            for b in blocks:
                bx0, by0, bx1, by1, btxt = b[:5]
                txt = re.sub(r"\s+", " ", str(btxt)).strip().lower()
                if bx0 <= tx0 + 15 or bx0 >= tx0 + 220:
                    continue
                if by0 > ty0 + 12 or by1 < ty0 - 20:
                    continue
                if "title" in txt and "paper" in txt:
                    continue
                if next_x is None or bx0 < next_x:
                    next_x = float(bx0)
            if next_x is None:
                continue
            title_left, title_right = max(0.0, float(tx0) - 8), float(next_x) - 15
            if title_right - title_left < 25:
                continue

            # Keep rows inside this section/table, excluding rows in later sections.
            next_heading_y = min((h[0] for h in headings if h[0] > ty1), default=float(page.rect.height))
            # Select numbered rows within the discovered serial-number column.
            row_numbers = []
            for x0, y0, x1, y1, word, *_ in words:
                if not re.fullmatch(r"\d{1,3}[.]?", str(word)):
                    continue
                if not (float(sx0) - 8 <= x0 <= float(sx1) + 8):
                    continue
                if y0 <= ty1 + 1 or y0 >= next_heading_y:
                    continue
                row_numbers.append((float(y0), str(word).rstrip(".")))
            row_numbers.sort()
            dedup_rows = []
            for row in row_numbers:
                if not dedup_rows or abs(row[0] - dedup_rows[-1][0]) > 3:
                    dedup_rows.append(row)
            if not dedup_rows:
                continue

            preceding = [h for h in headings if h[0] < ty0 and not nonpub_re.search(h[3])]
            category = preceding[-1][2] if preceding else None
            if category not in {"JOURNAL", "CONFERENCE", "BOOK", "BOOK_CHAPTER"}:
                continue

            for idx, (row_y, serial) in enumerate(dedup_rows):
                next_row_y = dedup_rows[idx + 1][0] if idx + 1 < len(dedup_rows) else next_heading_y
                if next_row_y <= row_y:
                    continue
                row_words = [w for w in words if row_y - 1 <= w[1] < next_row_y - 0.5]
                title_words = [w for w in row_words if title_left <= w[0] < title_right]
                if not title_words:
                    continue

                def words_to_lines(items):
                    groups: dict[int, list] = {}
                    for item in items:
                        groups.setdefault(round(float(item[1]) / 3) * 3, []).append(item)
                    lines = []
                    for _, line_words in sorted(groups.items()):
                        line_words.sort(key=lambda w: w[0])
                        lines.append(" ".join(str(w[4]) for w in line_words))
                    return lines

                title = " ".join(words_to_lines(title_words))
                title = re.sub(r"(?<=[A-Za-z])\s+[-‐‑]\s*(?=[a-z])", "", title)
                title = re.sub(r"(?<=[A-Za-z])[-‐‑]\s+(?=[A-Z])", "-", title)
                title = re.sub(r"\s+", " ", title).strip(" \t\n:;,.–-")
                title = re.sub(r"(?i)^(?:title\s+of\s+the\s+paper)\s*", "", title)
                if len(title) < 12 or len(title) > 600:
                    continue
                if re.search(r"(?i)^(?:source software|new[- ]delhi|june\s+\d{1,2})\b", title):
                    continue

                full = " ".join(words_to_lines(row_words))
                full = re.sub(r"(?<=[A-Za-z])[-‐‑]\s+(?=[a-z])", "", full)
                full = re.sub(r"\s+", " ", full).strip()
                year_match = re.search(r"\b((?:19|20)\d{2})\b", full)
                result.append(RawPublicationItem(
                    raw_text=full or title,
                    source_category=category,
                    source_identifier=serial,
                    source_year=int(year_match.group(1)) if year_match else None,
                    source_page=page_no,
                    source_url=source_url,
                    source_document=Path(pdf_path).name,
                    faculty_name=faculty_name,
                    raw_metadata={
                        "raw_text": full or title,
                        "title_candidate": title,
                        "record_number": serial,
                        "section_heading": next((h[3] for h in reversed(preceding)), ""),
                        "extraction_strategy": "coordinate_aware_table_row",
                    },
                ))
    document.close()
    # A row can be detected twice if a PDF repeats headers; deduplicate by category/title.
    unique, seen = [], set()
    for item in result:
        key = (item.source_category, re.sub(r"\W+", " ", item.raw_metadata.get("title_candidate", "").lower()).strip())
        if key[1] and key not in seen:
            seen.add(key)
            unique.append(item)
    return unique

def extract_raw_publications_from_pdf(pdf_path: str | Path, faculty_name: str = "", source_url: str | None = None) -> list[RawPublicationItem]:
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")
    with fitz.open(path) as pdf:
        pages = [page.get_text("text") or "" for page in pdf]
    parsed = extract_raw_publications_from_pages(pages, faculty_name, path.name, source_url)
    # Coordinate-aware extraction repairs CV tables whose narrow columns become
    # interleaved when converted to plain text. Prefer it only when it recovers
    # a more complete table result than the plain-text pass.
    table_records = _extract_coordinate_table_records(path, faculty_name, source_url)
    if table_records and len(table_records) > len(parsed):
        return table_records
    return parsed


def parse_publication_pdf(pdf_path: str | Path, faculty_name: str = "", source_url: str | None = None) -> list[PublicationRecord]:
    raw = extract_raw_publications_from_pdf(pdf_path, faculty_name, source_url)
    normalizer = PublicationNormalizer()
    normalized = []
    for item in raw:
        record = normalizer.normalize(item)
        candidate = (item.raw_metadata or {}).get("title_candidate")
        if not candidate:
            # Many CV citations quote the publication title within a longer
            # author/venue citation. Prefer that quoted title when unambiguous.
            raw = item.raw_text or ""
            quoted = re.findall(r"[“‘\"]([^”’\"]{12,350})[”’\"]", raw)
            quoted = [re.sub(r"\s+", " ", value).strip(" .;,:-–") for value in quoted]
            quoted = [value for value in quoted if len(value) >= 12 and not re.match(r"(?i)^(?:journal|conference|proceedings|springer|elsevier)\b", value)]
            if quoted:
                candidate = quoted[0]
        if candidate:
            record.title = str(candidate).strip()
        normalized.append(record)
    # Preserve same-title records when their source citations differ (for example,
    # the same work listed at two distinct conferences). Deduplicate exact repeats
    # and repeated DOIs, not title/type/year alone.
    unique: list[PublicationRecord] = []
    seen: set[tuple[str, ...]] = set()
    for record in normalized:
        if record.doi:
            key = ("DOI", re.sub(r"\s+", "", record.doi).lower())
        else:
            raw = str((record.raw_metadata or {}).get("raw_text") or record.title or "")
            normalized_raw = re.sub(r"[^a-z0-9]+", " ", raw.lower())
            normalized_raw = " ".join(normalized_raw.split())
            key = ("CITATION", record.publication_type, str(record.publication_year or ""), normalized_raw)
        if key in seen:
            continue
        seen.add(key)
        unique.append(record)
    return unique

"""
Reconcile thesis program/status/year fields against official MNNIT thesis pages.

Run from the DepartmentAI project root:
    python -m module2.ingestion.repair_thesis_classification
    python -m module2.ingestion.repair_thesis_classification --apply

Default mode is DRY RUN. --apply is required to write updates.
This script only updates rows matched by normalized student name AND research topic.
It never inserts/deletes records and never guesses a program/year from an unclassified row.
"""

import argparse
import csv
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

from module2.database.connection import get_connection

PLACEHOLDER_LEVELS = {
    "", "not specified on source page", "not classified from source heading",
    "unknown", "n/a", "none",
}
USER_AGENT = "DepartmentAI-Thesis-Reconciliation/1.0"
TIMEOUT_SECONDS = 30


def norm(value):
    return " ".join(re.findall(r"[a-z0-9]+", (value or "").lower()))


def clean(value):
    return re.sub(r"\s+", " ", (value or "").replace("\xa0", " ")).strip()


def year_from(value):
    match = re.search(r"\b(?:19|20)\d{2}\b", value or "")
    if not match:
        return None
    year = int(match.group())
    return year if 1900 <= year <= 2100 else None


def classify_heading(text):
    """Return (program_level, status) only when the heading provides evidence."""
    value = clean(text).lower()
    compact = re.sub(r"[^a-z0-9]+", "", value)

    if "phd" in compact or "doctoral" in compact:
        program = "Ph.D."
        if "ongoing" in compact or "pursuing" in compact or "current" in compact:
            return program, "Ongoing"
        if "completed" in compact or "awarded" in compact or "graduated" in compact:
            return program, "Completed"
        return program, None

    if "mtech" in compact or "masteroftechnology" in compact:
        return "M.Tech", None
    if "btech" in compact or "bacheloroftechnology" in compact:
        return "B.Tech", None
    if "mca" in compact:
        return "MCA", None
    return None, None


def fetch_html(url):
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        body = response.read()
        charset = response.headers.get_content_charset() or "utf-8"
    return body.decode(charset, errors="replace")


def parse_thesis_page(html, source_url):
    """Parse category headings and student rows robustly across MNNIT page layouts."""
    if BeautifulSoup is None:
        raise RuntimeError("Missing dependency beautifulsoup4. Install it in the active venv before continuing.")

    soup = BeautifulSoup(html, "html.parser")
    parsed = []
    current_program = None
    current_status = None
    header_map = None
    header_table = None
    header_found = False
    seen_rows = 0

    def get_cells(node):
        return node.find_all(["th", "td"], recursive=False) if node.name == "tr" else []

    def make_header_map(cell_texts):
        mapping = {}
        for idx, label in enumerate(cell_texts):
            low = clean(label).lower()
            # Independent tests: a combined/malformed header cell can contain
            # more than one label, so these must not be an elif chain.
            if "research topic" in low or low == "topic":
                mapping["topic"] = idx
            if "student" in low or "scholar" in low or low in {"name", "name of student", "name of the student"}:
                mapping["student"] = idx
            if "year" in low or "registration" in low or "completion" in low:
                mapping["year"] = idx
            if "s.no" in low or low in {"sno", "serial no", "serial number", "s. no."}:
                mapping["serial"] = idx

        # MNNIT's common layout: S.No | Research Topic | Name of Student | Completion/Registration Year.
        # This fallback applies only when the header row has the expected multi-column shape.
        if len(cell_texts) >= 4:
            mapping.setdefault("topic", 1)
            mapping.setdefault("student", 2)
            mapping.setdefault("year", 3)
        elif len(cell_texts) == 3:
            # Some page versions omit the serial-number column.
            mapping.setdefault("topic", 0)
            mapping.setdefault("student", 1)
            mapping.setdefault("year", 2)
        return mapping

    # Walk the DOM in document order so section labels apply to following rows.
    for node in soup.find_all(["h1", "h2", "h3", "h4", "h5", "p", "tr"]):
        text = clean(node.get_text(" ", strip=True))
        if not text:
            continue

        cells = get_cells(node)
        cell_texts = [clean(cell.get_text(" ", strip=True)) for cell in cells]
        joined = " ".join(cell_texts).lower() if cells else text.lower()
        program, status = classify_heading(text)

        # Category labels can be heading elements or table rows. Do not mistake
        # ordinary data rows for category labels.
        if program is not None and "research topic" not in joined and not (
            "student" in joined and ("year" in joined or "registration" in joined or "completion" in joined)
        ):
            current_program, current_status = program, status
            continue

        if node.name != "tr" or not cells:
            continue

        # Recognize header even if labels are distributed unusually across cells.
        looks_like_header = (
            ("research topic" in joined or "topic" in joined)
            and ("student" in joined or "scholar" in joined)
            and ("year" in joined or "registration" in joined or "completion" in joined)
        )
        if looks_like_header:
            header_map = make_header_map(cell_texts)
            header_table = node.find_parent("table")
            header_found = True
            continue

        if not header_map or current_program is None:
            continue
        if node.find_parent("table") is not header_table:
            continue

        # If markup combines header labels into a single cell, infer the usual
        # column layout from the actual data-row shape as a last resort.
        row_map = dict(header_map)
        if ("topic" not in row_map or "student" not in row_map) and len(cell_texts) >= 4:
            row_map.setdefault("topic", 1)
            row_map.setdefault("student", 2)
            row_map.setdefault("year", 3)
        elif ("topic" not in row_map or "student" not in row_map) and len(cell_texts) == 3:
            row_map.setdefault("topic", 0)
            row_map.setdefault("student", 1)
            row_map.setdefault("year", 2)

        def cell_value(key):
            idx = row_map.get(key)
            return cell_texts[idx] if idx is not None and idx < len(cell_texts) else ""

        topic = cell_value("topic")
        student = cell_value("student")
        year_text = cell_value("year")
        if not topic or not student or topic.lower() in {"research topic", "topic"}:
            continue
        if classify_heading(" ".join(cell_texts))[0] is not None:
            continue
        # Avoid treating table's serial number/empty formatting rows as records.
        if len(cell_texts) < 3:
            continue

        seen_rows += 1
        parsed.append({
            "program_level": current_program,
            "status": current_status,
            "student_name": student,
            "research_topic": topic,
            "source_year": year_from(year_text),
            "source_year_text": year_text,
            "source_url": source_url,
        })

    # Diagnostics are attached to the list so the caller can explain zero-row parses.
    return parsed



def fetch_source_urls():
    """Return unique official thesis URLs globally; do not trust their faculty_id association."""
    query = """
        SELECT DISTINCT source_url
        FROM m2_thesis_supervision
        WHERE source_url LIKE '%previewt.php%'
        ORDER BY source_url
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            return [row[0] for row in cur.fetchall() if row and row[0]]


def fetch_faculties():
    query = "SELECT id, full_name FROM m2_faculties ORDER BY id"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            return cur.fetchall()


def extract_page_title(html):
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    return clean(re.sub(r"<[^>]+>", " ", match.group(1))) if match else ""


def person_key(value):
    value = clean(value).lower()
    value = re.sub(r"profile\s*page.*$", "", value)
    tokens = re.findall(r"[a-z0-9]+", value)
    ignored = {"prof", "professor", "dr", "doctor", "lt", "lieutenant", "mr", "mrs", "ms"}
    return " ".join(token for token in tokens if token not in ignored)


def resolve_faculty_from_title(title, faculties, source_rows=None, db_rows_by_faculty=None):
    """
    Resolve a page to a faculty by the official HTML title, not the potentially
    mis-associated faculty_id on existing thesis rows. Ambiguous names fail closed.
    """
    from difflib import SequenceMatcher

    title_key = person_key(title)
    if not title_key:
        return None, "Page has no usable title"

    scored = []
    title_tokens = set(title_key.split())
    for faculty_id, full_name in faculties:
        key = person_key(full_name)
        if not key:
            continue
        if key == title_key:
            score = 1.0
        else:
            faculty_tokens = set(key.split())
            overlap = len(title_tokens & faculty_tokens) / max(1, len(title_tokens | faculty_tokens))
            ratio = SequenceMatcher(None, title_key, key).ratio()
            score = max(ratio, overlap)
        scored.append((score, faculty_id, full_name, key))

    if not scored:
        return None, f"No faculty records available for title {title!r}"

    scored.sort(reverse=True)
    best_score = scored[0][0]
    best = [item for item in scored if abs(item[0] - best_score) < 0.015]

    if best_score < 0.82:
        return None, f"Title {title!r} did not match a faculty name confidently (best score={best_score:.2f})"

    # If multiple faculty DB rows share the same name, use exact student/topic overlap
    # only when it uniquely identifies one row. Otherwise do not guess.
    if len(best) > 1 and source_rows and db_rows_by_faculty:
        source_keys = {source_key(r["student_name"], r["research_topic"]) for r in source_rows}
        overlaps = []
        for score, faculty_id, full_name, key in best:
            db_rows = db_rows_by_faculty.get(faculty_id, [])
            db_keys = {source_key(r.get("student_name"), r.get("research_topic")) for r in db_rows}
            overlaps.append((len(source_keys & db_keys), score, faculty_id, full_name, key))
        overlaps.sort(reverse=True)
        if len(overlaps) == 1 or overlaps[0][0] > overlaps[1][0]:
            return (overlaps[0][2], overlaps[0][3]), None
        return None, f"Ambiguous faculty title {title!r}: {[item[3] for item in overlaps]}"

    if len(best) != 1:
        return None, f"Ambiguous faculty title {title!r}: {[item[2] for item in best]}"

    return (best[0][1], best[0][2]), None


def fetch_database_rows(faculty_id):
    query = """
        SELECT id, student_name, research_topic, program_level, status,
               registration_year, completion_year
        FROM m2_thesis_supervision
        WHERE faculty_id = %s
        ORDER BY id
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (faculty_id,))
            cols = [item.name if hasattr(item, "name") else item[0] for item in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]


def source_key(student, topic):
    return norm(student), norm(topic)


def make_updates(source_rows, db_rows, faculty_id, faculty_name):
    source_index = defaultdict(list)
    for row in source_rows:
        source_index[source_key(row["student_name"], row["research_topic"])].append(row)

    db_index = defaultdict(list)
    for row in db_rows:
        db_index[source_key(row["student_name"], row["research_topic"])].append(row)

    updates = []
    unmatched_source = []
    ambiguous_source = []

    for key, source_matches in source_index.items():
        if len(source_matches) != 1:
            ambiguous_source.extend(source_matches)
            continue
        source = source_matches[0]
        candidates = db_index.get(key, [])
        if not candidates:
            unmatched_source.append(source)
            continue
        if len(candidates) > 1:
            # Do not update duplicated database rows automatically.
            ambiguous_source.append(source)
            continue

        db = candidates[0]
        changes = {}

        current_level = clean(db.get("program_level"))
        if source.get("program_level") and (
            current_level.lower() in PLACEHOLDER_LEVELS
            or current_level != source["program_level"]
        ):
            changes["program_level"] = source["program_level"]

        if source.get("status") in {"Ongoing", "Completed"}:
            if clean(db.get("status")).lower() != source["status"].lower():
                changes["status"] = source["status"]

            # The official table labels its year column "Completion/Registration Year".
            # Status makes the Ph.D. year role explicit for these two categories.
            year = source.get("source_year")
            if year:
                if source["status"] == "Completed":
                    if db.get("completion_year") != year:
                        changes["completion_year"] = year
                    if db.get("registration_year") is not None:
                        changes["registration_year"] = None
                elif source["status"] == "Ongoing":
                    if db.get("registration_year") != year:
                        changes["registration_year"] = year
                    if db.get("completion_year") is not None:
                        changes["completion_year"] = None

        if changes:
            updates.append({
                "faculty_id": faculty_id,
                "faculty_name": faculty_name,
                "record_id": db["id"],
                "student_name": db["student_name"],
                "research_topic": db["research_topic"],
                "source_program_level": source["program_level"],
                "source_status": source.get("status"),
                "source_year": source.get("source_year"),
                "changes": changes,
                "source_url": source["source_url"],
            })

    return updates, unmatched_source, ambiguous_source



def write_report(export_dir, filename, rows, default_fields):
    """Write every report; if Excel has locked the standard file, use a timestamped name."""
    from datetime import datetime

    fields = sorted({key for row in rows for key in row.keys()}) if rows else default_fields
    candidates = [export_dir / filename]
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    candidates.append(export_dir / f"{Path(filename).stem}_{stamp}{Path(filename).suffix}")
    for path in candidates:
        try:
            with path.open("w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(rows)
            return path
        except PermissionError:
            continue
    raise PermissionError(f"Cannot write report {filename}; close it in Excel or another application and rerun.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Apply verified updates; default is dry-run")
    parser.add_argument("--limit", type=int, default=0, help="Optional limit of source URLs for a controlled test")
    args = parser.parse_args()

    if BeautifulSoup is None:
        print("Missing dependency beautifulsoup4. Install it in the active venv before continuing.")
        return 2

    faculties = fetch_faculties()
    source_urls = fetch_source_urls()
    db_rows_by_faculty = {faculty_id: fetch_database_rows(faculty_id) for faculty_id, _ in faculties}
    if args.limit:
        source_urls = source_urls[:args.limit]

    # Parse every unique URL, then assign it to the faculty named by the page itself.
    # The previous version trusted ts.faculty_id; logs showed that association can be wrong.
    source_rows_by_faculty = defaultdict(list)
    fetch_errors = []
    url_mapping_review = []
    total_parsed = 0

    print("THESIS CLASSIFICATION REPAIR — " + ("APPLY MODE" if args.apply else "DRY RUN"))
    print("Safety: official page title is used to resolve faculty; ambiguous/mismatched pages are skipped.")
    print("No inserts or deletes will be performed.")

    for index, url in enumerate(source_urls, 1):
        try:
            html = fetch_html(url)
            title = extract_page_title(html)
            rows = parse_thesis_page(html, url)
            total_parsed += len(rows)
            resolved, reason = resolve_faculty_from_title(
                title, faculties, rows, db_rows_by_faculty
            )
            if not rows:
                url_mapping_review.append({
                    "source_url": url, "page_title": title,
                    "parsed_rows": 0, "resolved_faculty": "",
                    "issue": "No thesis rows parsed from page",
                })
            elif reason:
                url_mapping_review.append({
                    "source_url": url, "page_title": title,
                    "parsed_rows": len(rows), "resolved_faculty": "",
                    "issue": reason,
                })
            else:
                faculty_id, faculty_name = resolved
                source_rows_by_faculty[faculty_id].extend(rows)
                print(f"[{index}/{len(source_urls)}] {title}: rows={len(rows)} -> {faculty_name} (faculty_id={faculty_id})")
            time.sleep(0.15)
        except Exception as exc:
            fetch_errors.append({
                "source_url": url,
                "error": str(exc),
            })

    all_updates = []
    unmatched_source_rows = []
    ambiguous_rows = []
    parsed_for_matched_faculties = 0

    faculty_name_by_id = {faculty_id: name for faculty_id, name in faculties}
    for faculty_id, source_rows in source_rows_by_faculty.items():
        faculty_name = faculty_name_by_id[faculty_id]
        parsed_for_matched_faculties += len(source_rows)
        updates, unmatched, ambiguous = make_updates(
            source_rows, db_rows_by_faculty[faculty_id], faculty_id, faculty_name
        )
        all_updates.extend(updates)
        unmatched_source_rows.extend({
            "faculty_id": faculty_id, "faculty_name": faculty_name, **row
        } for row in unmatched)
        ambiguous_rows.extend({
            "faculty_id": faculty_id, "faculty_name": faculty_name, **row
        } for row in ambiguous)

    export_dir = Path("module2") / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)

    preview_path = write_report(
        export_dir, "thesis_classification_repair_preview.csv", all_updates,
        ["faculty_id", "faculty_name", "record_id", "student_name", "research_topic",
         "source_program_level", "source_status", "source_year", "changes", "source_url"]
    )
    unmatched_path = write_report(
        export_dir, "thesis_classification_unmatched_source.csv", unmatched_source_rows,
        ["faculty_id", "faculty_name", "student_name", "research_topic", "source_url"]
    )
    ambiguous_path = write_report(
        export_dir, "thesis_classification_ambiguous_rows.csv", ambiguous_rows,
        ["faculty_id", "faculty_name", "student_name", "research_topic", "source_url"]
    )
    fetch_path = write_report(
        export_dir, "thesis_classification_fetch_errors.csv", fetch_errors,
        ["source_url", "error"]
    )
    mapping_path = write_report(
        export_dir, "thesis_classification_url_mapping_review.csv", url_mapping_review,
        ["source_url", "page_title", "parsed_rows", "resolved_faculty", "issue"]
    )

    print("\nSUMMARY")
    print(f"Faculty records in database: {len(faculties)}")
    print(f"Unique thesis source URLs inspected: {len(source_urls)}")
    print(f"Source rows parsed: {total_parsed}")
    print(f"Rows from confidently mapped pages: {parsed_for_matched_faculties}")
    print(f"Proposed record updates: {len(all_updates)}")
    print(f"Unmatched source rows: {len(unmatched_source_rows)}")
    print(f"Ambiguous database/source rows skipped: {len(ambiguous_rows)}")
    print(f"Fetch errors: {len(fetch_errors)}")
    print(f"Unmapped or zero-row pages: {len(url_mapping_review)}")
    print("Reports:")
    for path in [preview_path, unmatched_path, ambiguous_path, fetch_path, mapping_path]:
        print(f"  {path.resolve()}")

    if args.apply:
        if url_mapping_review or fetch_errors or ambiguous_rows or unmatched_source_rows:
            print("\nREFUSING TO APPLY: review mapping/fetch/unmatched/ambiguous reports first.")
            print("The database was not changed.")
            return 3
        applied = 0
        with get_connection() as conn:
            with conn.cursor() as cur:
                for item in all_updates:
                    sets = []
                    values = []
                    for column, value in item["changes"].items():
                        sets.append(f"{column} = %s")
                        values.append(value)
                    if not sets:
                        continue
                    values.append(item["record_id"])
                    cur.execute(
                        f"UPDATE m2_thesis_supervision SET {', '.join(sets)} WHERE id = %s",
                        values,
                    )
                    applied += cur.rowcount
        print(f"Database updates committed: {applied}")
    else:
        print("\nDRY RUN ONLY: database unchanged.")
        print("Do not use --apply until URL mapping review is empty and all reports are verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

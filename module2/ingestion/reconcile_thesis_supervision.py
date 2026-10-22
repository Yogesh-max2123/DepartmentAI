"""Reconcile official MNNIT CSED thesis tables against Module II database rows.

READ-ONLY: this script fetches official profile pages and exports source/database
comparisons. It never inserts, updates, or deletes database records.

Run from the DepartmentAI project root:
    python -m module2.ingestion.reconcile_thesis_supervision

Outputs (module2/exports):
    thesis_source_all_faculty.csv
    thesis_database_all_faculty.csv
    thesis_source_database_summary.csv
    thesis_source_database_details.csv
    thesis_source_fetch_errors.csv
"""
from __future__ import annotations

import csv
import re
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from html.parser import HTMLParser
from urllib.parse import urlparse

import requests

from module2.database.connection import get_connection
from module2.ingestion.faculty_profile import discover_profile_components
try:
    from module2.ingestion.faculty_directory import discover_faculty as discover_directory_faculty
except ImportError:
    discover_directory_faculty = None

TIMEOUT = 30
HEADERS = {"User-Agent": "DepartmentAI thesis reconciliation/1.0"}
EXPORT_DIR = Path("module2") / "exports"


def clean(value: str | None) -> str:
    return " ".join((value or "").replace("\xa0", " ").split()).strip()


def normalized(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", clean(value)).casefold()
    text = re.sub(r"\b(professor|prof|doctor|dr)\b\.?", " ", text)
    return re.sub(r"[^a-z0-9]+", "", text)


def normalized_entry(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", clean(value)).casefold()
    text = text.replace("&", " and ")
    text = re.sub(r"\b(the|a|an)\b", " ", text)
    return re.sub(r"[^a-z0-9]+", "", text)


def fetch_html(url: str, session: requests.Session) -> str:
    response = session.get(url, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    raw = response.content
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        encoding = response.encoding or response.apparent_encoding or "cp1252"
        try:
            return raw.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            return raw.decode("utf-8", errors="replace")


class TableParser(HTMLParser):
    """Capture table rows and cells without requiring a particular table layout."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self.row: list[str] | None = None
        self.cell: list[str] | None = None
        self.in_cell = False
        self.skip_depth = 0
        self.skip_tag: str | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript"}:
            self.skip_depth += 1
            self.skip_tag = tag
            return
        if self.skip_depth:
            return
        if tag == "tr":
            self.row = []
        elif tag in {"td", "th"} and self.row is not None:
            self.cell = []
            self.in_cell = True
        elif tag == "br" and self.in_cell and self.cell is not None:
            self.cell.append(" ")

    def handle_data(self, data: str) -> None:
        if not self.skip_depth and self.in_cell and self.cell is not None:
            value = clean(data)
            if value:
                self.cell.append(value)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self.skip_depth:
            if tag == self.skip_tag:
                self.skip_depth -= 1
                if self.skip_depth == 0:
                    self.skip_tag = None
            return
        if tag in {"td", "th"} and self.in_cell and self.row is not None:
            self.row.append(clean(" ".join(self.cell or [])))
            self.cell = None
            self.in_cell = False
        elif tag == "tr" and self.row is not None:
            if any(clean(cell) for cell in self.row):
                self.rows.append(self.row)
            self.row = None
            self.cell = None
            self.in_cell = False


def detect_heading(cells: list[str]) -> tuple[str | None, str | None] | None:
    text = clean(" ".join(cells)).casefold()
    compact = re.sub(r"[^a-z0-9]+", " ", text).strip()
    if not compact:
        return None

    # These are section labels, not thesis records.
    if "ph d" in compact or "phd" in compact or "doctoral" in compact:
        if any(word in compact for word in ("ongoing", "current", "pursuing", "registered")):
            return ("Ph.D.", "Ongoing")
        if any(word in compact for word in ("completed", "awarded", "degree awarded")):
            return ("Ph.D.", "Completed")
        if len(cells) <= 2 and ("student" in compact or "thesis" in compact):
            return ("Ph.D.", None)

    if "m tech" in compact or "mtech" in compact or "master of technology" in compact:
        if len(cells) <= 2 or "student" in compact:
            return ("M.Tech.", None)
    if "m e " in f" {compact} " and len(cells) <= 2:
        return ("M.E.", None)
    if "b tech" in compact and len(cells) <= 2:
        return ("B.Tech.", None)
    return None


def parse_thesis_table(html: str) -> list[dict[str, Any]]:
    parser = TableParser()
    parser.feed(html)
    parser.close()

    current_program: str | None = None
    current_status: str | None = None
    records: list[dict[str, Any]] = []

    for raw_cells in parser.rows:
        cells = [clean(c) for c in raw_cells]
        joined = clean(" ".join(cells))
        if not joined:
            continue

        heading = detect_heading(cells)
        if heading:
            current_program, current_status = heading
            continue

        header_text = joined.casefold()
        if (
            ("research topic" in header_text and "student" in header_text)
            or ("name of student" in header_text)
            or (len(cells) >= 3 and cells[0].casefold().strip(". ") in {"s.no", "s no", "serial no", "s.no."})
        ):
            continue

        # Expected source columns: S.No., Research Topic, Name of Student, Year.
        # Find data rows by their content rather than blindly accepting unrelated tables.
        if len(cells) < 4:
            continue
        serial, topic, student, year_text = cells[:4]
        if not topic or not student:
            continue
        if any(marker in topic.casefold() for marker in ("research topic", "research area")):
            continue
        if any(marker in student.casefold() for marker in ("name of student", "student name")):
            continue

        # Section heading rows can span several cells and otherwise look like table rows.
        if detect_heading(cells[:2]):
            current_program, current_status = detect_heading(cells[:2]) or (current_program, current_status)
            continue

        years = re.findall(r"(?<!\d)(?:19|20)\d{2}(?!\d)", year_text)
        source_year = years[-1] if years else ""
        year_role = (
            "completion_year" if current_status == "Completed"
            else "registration_year" if current_status == "Ongoing"
            else "source_year_role_not_explicit"
        )
        records.append({
            "program_level": current_program or "Not classified from source heading",
            "status": current_status or "Not explicit in source heading",
            "student_name": student,
            "research_topic": topic,
            "source_year_text": year_text,
            "source_year": source_year,
            "source_year_role": year_role,
        })

    return records


def load_database_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    faculty_query = """
        SELECT f.id, f.full_name, f.profile_url, f.is_active,
               COUNT(ts.id) AS stored_thesis_count
        FROM m2_faculties f
        LEFT JOIN m2_thesis_supervision ts ON ts.faculty_id = f.id
        GROUP BY f.id, f.full_name, f.profile_url, f.is_active
        ORDER BY LOWER(f.full_name), f.id
    """
    thesis_query = """
        SELECT f.id AS faculty_id, f.full_name AS faculty_name,
               ts.id AS thesis_record_id, ts.program_level, ts.status,
               ts.student_name, ts.research_topic, ts.registration_year,
               ts.completion_year, ts.source_url, ts.details
        FROM m2_faculties f
        JOIN m2_thesis_supervision ts ON ts.faculty_id = f.id
        ORDER BY LOWER(f.full_name), f.id, ts.id
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(faculty_query)
            faculty_cols = [d.name if hasattr(d, "name") else d[0] for d in cur.description]
            faculties = [dict(zip(faculty_cols, row)) for row in cur.fetchall()]
            cur.execute(thesis_query)
            thesis_cols = [d.name if hasattr(d, "name") else d[0] for d in cur.description]
            theses = [dict(zip(thesis_cols, row)) for row in cur.fetchall()]
    return faculties, theses


def fetch_profile_theses(faculties: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    session = requests.Session()
    source_rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    directory_url_by_name: dict[str, str] = {}
    if discover_directory_faculty is not None and any(not clean(f.get("profile_url")) for f in faculties):
        try:
            for directory_record in discover_directory_faculty():
                directory_url_by_name[normalized(directory_record.name)] = directory_record.profile_url
        except Exception as exc:
            print(f"WARNING: official directory fallback could not be loaded: {type(exc).__name__}: {exc}", flush=True)

    for index, faculty in enumerate(faculties, start=1):
        faculty_id = faculty["id"]
        name = faculty["full_name"]
        profile_url = clean(faculty.get("profile_url"))
        if not profile_url:
            profile_url = directory_url_by_name.get(normalized(name), "")
        print(f"[{index}/{len(faculties)}] {name} (DB faculty ID {faculty_id})", flush=True)

        if not profile_url:
            errors.append({
                "faculty_id": faculty_id, "faculty_name": name,
                "profile_url": "", "thesis_url": "", "error": "No stored or directory-matched profile URL",
            })
            print("  ERROR: no stored or directory-matched profile URL", flush=True)
            continue

        try:
            components = discover_profile_components(name, profile_url)
            thesis_url = clean(getattr(components, "thesis_url", ""))
            if not thesis_url:
                raise ValueError("Thesis Supervised component URL not found on profile")
            html = fetch_html(thesis_url, session)
            records = parse_thesis_table(html)

            for row_number, record in enumerate(records, start=1):
                source_rows.append({
                    "faculty_id": faculty_id,
                    "faculty_name": name,
                    "profile_url": profile_url,
                    "thesis_url": thesis_url,
                    "source_row_number": row_number,
                    **record,
                })
            print(f"  Source thesis rows parsed: {len(records)}", flush=True)
            if not records:
                print("  WARNING: no thesis rows parsed; verify the source page manually", flush=True)
        except Exception as exc:
            errors.append({
                "faculty_id": faculty_id, "faculty_name": name,
                "profile_url": profile_url,
                "thesis_url": "",
                "error": f"{type(exc).__name__}: {exc}",
            })
            print(f"  ERROR: {type(exc).__name__}: {exc}", flush=True)
        time.sleep(0.15)

    return source_rows, errors


def write_csv(path: Path, columns: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: ("" if row.get(key) is None else row.get(key)) for key in columns})


def source_key(row: dict[str, Any]) -> tuple[str, str]:
    return (
        normalized_entry(row.get("student_name")),
        normalized_entry(row.get("research_topic")),
    )


def db_key(row: dict[str, Any]) -> tuple[str, str]:
    return source_key(row)


def canonical_program(value: Any) -> str:
    text = normalized_entry(str(value or ""))
    if text in {"phd", "phdcompleted", "phdongoing", "doctorofphilosophy", "doctoral"}:
        return "phd"
    if text in {"mtech", "masteroftechnology"}:
        return "mtech"
    if text in {"me", "masterofengineering"}:
        return "me"
    if text in {"btech", "bacheloroftechnology"}:
        return "btech"
    return text


def canonical_status(value: Any) -> str:
    text = normalized_entry(str(value or ""))
    if any(token in text for token in ("ongoing", "current", "pursuing", "registered")):
        return "ongoing"
    if any(token in text for token in ("completed", "complete", "awarded", "finished")):
        return "completed"
    return text


def field_mismatch_flags(source: dict[str, Any], dbrow: dict[str, Any]) -> str:
    flags: list[str] = []
    source_program = canonical_program(source.get("program_level"))
    db_program = canonical_program(dbrow.get("program_level"))
    if source_program not in {"", "notspecifiedonsourcepage", "notclassifiedfromsourceheading"} and db_program and source_program != db_program:
        flags.append("PROGRAM_LEVEL_DIFFERS")

    source_status = canonical_status(source.get("status"))
    db_status = canonical_status(dbrow.get("status"))
    if source_status not in {"", "notexplicitinsourceheading"} and db_status and source_status != db_status:
        flags.append("STATUS_DIFFERS")
    elif source_status not in {"", "notexplicitinsourceheading"} and not db_status:
        flags.append("DATABASE_STATUS_MISSING")

    year = str(source.get("source_year") or "").strip()
    role = source.get("source_year_role")
    reg_year = str(dbrow.get("registration_year") or "").strip()
    comp_year = str(dbrow.get("completion_year") or "").strip()
    if year:
        if role == "completion_year":
            if not comp_year:
                flags.append("DATABASE_COMPLETION_YEAR_MISSING")
            elif comp_year != year:
                flags.append("COMPLETION_YEAR_DIFFERS")
        elif role == "registration_year":
            if not reg_year:
                flags.append("DATABASE_REGISTRATION_YEAR_MISSING")
            elif reg_year != year:
                flags.append("REGISTRATION_YEAR_DIFFERS")
        elif year not in {reg_year, comp_year}:
            if not reg_year and not comp_year:
                flags.append("DATABASE_BOTH_YEARS_MISSING")
            else:
                flags.append("SOURCE_YEAR_NOT_MATCHED")
    else:
        flags.append("SOURCE_YEAR_NOT_PARSED")
    return ";".join(flags) if flags else "NO_OBVIOUS_FIELD_MISMATCH"


def compare_records(
    faculties: list[dict[str, Any]],
    source_rows: list[dict[str, Any]],
    db_rows: list[dict[str, Any]],
    errors: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    source_by_faculty: dict[int, list[dict[str, Any]]] = defaultdict(list)
    db_by_faculty: dict[int, list[dict[str, Any]]] = defaultdict(list)
    error_by_faculty = {int(e["faculty_id"]): e["error"] for e in errors}
    for row in source_rows:
        source_by_faculty[int(row["faculty_id"])].append(row)
    for row in db_rows:
        db_by_faculty[int(row["faculty_id"])].append(row)

    summaries: list[dict[str, Any]] = []
    details: list[dict[str, Any]] = []

    for faculty in faculties:
        fid = int(faculty["id"])
        sources = source_by_faculty.get(fid, [])
        stored = db_by_faculty.get(fid, [])
        source_counts = Counter(source_key(row) for row in sources)
        db_counts = Counter(db_key(row) for row in stored)
        common = source_counts & db_counts
        source_only_count = sum((source_counts - db_counts).values())
        db_only_count = sum((db_counts - source_counts).values())
        matched_count = sum(common.values())

        summaries.append({
            "faculty_id": fid,
            "faculty_name": faculty["full_name"],
            "faculty_is_active": faculty.get("is_active"),
            "profile_url": faculty.get("profile_url") or "",
            "source_thesis_count": len(sources) if fid not in error_by_faculty else "",
            "database_thesis_count": len(stored),
            "matched_student_topic_entries": matched_count,
            "source_only_entries": source_only_count if fid not in error_by_faculty else "",
            "database_only_entries": db_only_count if fid not in error_by_faculty else "",
            "source_fetch_status": "ERROR: " + error_by_faculty[fid] if fid in error_by_faculty else ("FETCHED" if sources else "FETCHED_ZERO_ROWS_CHECK_SOURCE"),
        })

        # Source rows with candidate database matches and field-level comparisons.
        remaining_db: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for row in stored:
            remaining_db[db_key(row)].append(row)

        for source in sources:
            key = source_key(source)
            candidates = remaining_db.get(key, [])
            if candidates:
                dbrow = candidates.pop(0)
                details.append({
                    "faculty_id": fid, "faculty_name": faculty["full_name"],
                    "comparison_status": "MATCHED_STUDENT_TOPIC_REVIEW_FIELDS",
                    "source_student_name": source["student_name"],
                    "database_student_name": dbrow.get("student_name") or "",
                    "source_research_topic": source["research_topic"],
                    "database_research_topic": dbrow.get("research_topic") or "",
                    "source_program_level": source["program_level"],
                    "database_program_level": dbrow.get("program_level") or "",
                    "source_status": source["status"],
                    "database_status": dbrow.get("status") or "",
                    "source_year_text": source["source_year_text"],
                    "source_year": source["source_year"],
                    "source_year_role": source["source_year_role"],
                    "database_registration_year": dbrow.get("registration_year") or "",
                    "database_completion_year": dbrow.get("completion_year") or "",
                    "database_record_id": dbrow.get("thesis_record_id"),
                    "source_profile_url": source["profile_url"],
                    "source_thesis_url": source["thesis_url"],
                    "database_source_url": dbrow.get("source_url") or "",
                    "database_details": dbrow.get("details") or "",
                    "field_mismatch_flags": field_mismatch_flags(source, dbrow),
                })
            else:
                details.append({
                    "faculty_id": fid, "faculty_name": faculty["full_name"],
                    "comparison_status": "SOURCE_ONLY_NOT_MATCHED_IN_DATABASE",
                    "source_student_name": source["student_name"],
                    "database_student_name": "",
                    "source_research_topic": source["research_topic"],
                    "database_research_topic": "",
                    "source_program_level": source["program_level"],
                    "database_program_level": "",
                    "source_status": source["status"],
                    "database_status": "",
                    "source_year_text": source["source_year_text"],
                    "source_year": source["source_year"],
                    "source_year_role": source["source_year_role"],
                    "database_registration_year": "",
                    "database_completion_year": "",
                    "database_record_id": "",
                    "source_profile_url": source["profile_url"],
                    "source_thesis_url": source["thesis_url"],
                    "database_source_url": "",
                    "database_details": "",
                    "field_mismatch_flags": "NO_DATABASE_MATCH",
                })

        for key, remaining in remaining_db.items():
            for dbrow in remaining:
                details.append({
                    "faculty_id": fid, "faculty_name": faculty["full_name"],
                    "comparison_status": "DATABASE_ONLY_NOT_MATCHED_TO_SOURCE",
                    "source_student_name": "",
                    "database_student_name": dbrow.get("student_name") or "",
                    "source_research_topic": "",
                    "database_research_topic": dbrow.get("research_topic") or "",
                    "source_program_level": "",
                    "database_program_level": dbrow.get("program_level") or "",
                    "source_status": "",
                    "database_status": dbrow.get("status") or "",
                    "source_year_text": "",
                    "source_year": "",
                    "source_year_role": "",
                    "database_registration_year": dbrow.get("registration_year") or "",
                    "database_completion_year": dbrow.get("completion_year") or "",
                    "database_record_id": dbrow.get("thesis_record_id"),
                    "source_profile_url": faculty.get("profile_url") or "",
                    "source_thesis_url": "",
                    "database_source_url": dbrow.get("source_url") or "",
                    "database_details": dbrow.get("details") or "",
                    "field_mismatch_flags": "NO_SOURCE_MATCH",
                })

    return summaries, details


def main() -> None:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
            sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
        except (AttributeError, OSError, ValueError):
            pass

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    faculties, db_rows = load_database_rows()
    print("THESIS SOURCE-TO-DATABASE RECONCILIATION (READ-ONLY)")
    print(f"Faculty rows in database: {len(faculties)}")
    print(f"Stored thesis records: {len(db_rows)}")
    print("Fetching official profile thesis tables. No database changes will be made.\n", flush=True)

    source_rows, errors = fetch_profile_theses(faculties)
    summaries, details = compare_records(faculties, source_rows, db_rows, errors)

    source_columns = [
        "faculty_id", "faculty_name", "profile_url", "thesis_url", "source_row_number",
        "program_level", "status", "student_name", "research_topic", "source_year_text",
        "source_year", "source_year_role",
    ]
    db_columns = [
        "faculty_id", "faculty_name", "thesis_record_id", "program_level", "status",
        "student_name", "research_topic", "registration_year", "completion_year",
        "source_url", "details",
    ]
    summary_columns = [
        "faculty_id", "faculty_name", "faculty_is_active", "profile_url",
        "source_thesis_count", "database_thesis_count", "matched_student_topic_entries",
        "source_only_entries", "database_only_entries", "source_fetch_status",
    ]
    detail_columns = [
        "faculty_id", "faculty_name", "comparison_status", "source_student_name",
        "database_student_name", "source_research_topic", "database_research_topic",
        "source_program_level", "database_program_level", "source_status", "database_status",
        "source_year_text", "source_year", "source_year_role", "database_registration_year",
        "database_completion_year", "database_record_id", "source_profile_url",
        "source_thesis_url", "database_source_url", "database_details", "field_mismatch_flags",
    ]
    error_columns = ["faculty_id", "faculty_name", "profile_url", "thesis_url", "error"]

    paths = {
        "source": EXPORT_DIR / "thesis_source_all_faculty.csv",
        "database": EXPORT_DIR / "thesis_database_all_faculty.csv",
        "summary": EXPORT_DIR / "thesis_source_database_summary.csv",
        "details": EXPORT_DIR / "thesis_source_database_details.csv",
        "errors": EXPORT_DIR / "thesis_source_fetch_errors.csv",
    }
    write_csv(paths["source"], source_columns, source_rows)
    write_csv(paths["database"], db_columns, db_rows)
    write_csv(paths["summary"], summary_columns, summaries)
    write_csv(paths["details"], detail_columns, details)
    write_csv(paths["errors"], error_columns, errors)

    print("\nRECONCILIATION SUMMARY")
    print(f"Official source records parsed: {len(source_rows)}")
    print(f"Database records: {len(db_rows)}")
    print(f"Profiles with fetch/parse errors: {len(errors)}")
    print("\nFiles created:")
    for path in paths.values():
        print(f"- {path.resolve()}")
    print("\nIMPORTANT: This is a read-only comparison. Do not bulk-update from counts alone.")
    print("Review source-vs-database details and any profile errors before creating a repair plan.")


if __name__ == "__main__":
    main()

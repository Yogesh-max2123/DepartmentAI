"""
Interactive Module II faculty assistant.

Run from the DepartmentAI project root:
    python -m module2.retrieval.faculty_assistant

This module reuses faculty_search.py and Module II's existing database.
It does not modify Module I or create a second embedding cache.
"""

import csv
import json
import re
from datetime import date, datetime
from pathlib import Path
from collections import deque

from module2.database.connection import get_connection
from module2.retrieval.faculty_search import (
    TOP_K,
    detect_requested_sections,
    display_results,
    ensure_corpus_loaded,
    faculty_search,
    resolve_faculty,
)
from module2.retrieval.faculty_gemini import generate_faculty_answer

HISTORY_LIMIT = 8
DEFAULT_LIST_LIMIT = 5
MAX_LIST_LIMIT = 20


def is_department_wide_question(question):
    q = (question or "").lower()
    phrases = (
        "csed", "cse department", "department-wide", "department wide",
        "all faculty", "all professors", "every faculty", "each professor",
        "department publications", "faculty publications",
    )
    return any(phrase in q for phrase in phrases)


def is_csed_faculty_related_question(question, has_faculty_context=False):
    """Reject clearly unrelated requests instead of sending them to faculty RAG."""
    q = (question or "").lower()
    domain_terms = (
        "faculty", "professor", "prof.", "dr.", "doctor", "research area",
        "research interest", "qualification", "education", "degree",
        "course", "taught", "publication", "publications", "paper", "papers",
        "journal", "conference", "doi", "citation", "thesis", "theses",
        "phd", "ph.d", "doctoral", "student", "students", "guided",
        "supervised", "supervision", "achievement", "award", "recognition",
        "responsibilit", "membership", "project", "research id", "orcid",
        "scholar", "h-index", "orcid", "researchgate", "email", "phone",
        "contact", "designation", "position", "office", "teaching",
        "academic profile", "academic background", "tell me about", "who is",
        "information about", "overview of", "latest", "recent", "profile",
        "these areas", "this area",
        "that professor", "this professor", "what about", "summarize", "summary",
    )
    if any(term in q for term in domain_terms):
        return True
    pronoun_followup = re.search(
        r"\\b(this|that|it|they|them|his|her|their|he|she|those|these)\\b", q
    )
    return bool(has_faculty_context and len(q.split()) <= 12 and pronoun_followup)


def extract_year_range(question):
    """Return an explicit year range or a single requested year as (year, year)."""
    years = re.findall(r"\b(?:19|20)\d{2}\b", question or "")
    if not years:
        return None
    parsed = [int(value) for value in years[:2]]
    if any(year < 1900 or year > 2100 for year in parsed):
        return None
    if len(parsed) == 1:
        return parsed[0], parsed[0]
    start, end = parsed
    if start > end:
        start, end = end, start
    return start, end


def requested_limit(question, default=DEFAULT_LIST_LIMIT):
    q = (question or "").lower()
    match = re.search(r"\b(?:top|first|last|latest|recent)\s+(\d{1,2})\b", q)
    if not match:
        match = re.search(r"\b(\d{1,2})\s+(?:latest|recent|newest)\b", q)
    if not match:
        return default
    return max(1, min(int(match.group(1)), MAX_LIST_LIMIT))


def asks_publication_count(question):
    q = (question or "").lower()
    count_intent = any(
        phrase in q
        for phrase in (
            "how many", "number of", "count of", "count the",
            "total number", "total publications", "how much",
        )
    )
    return count_intent and any(
        word in q for word in ("publication", "publications", "papers", "paper")
    )


def asks_latest_publications(question):
    q = (question or "").lower()
    publication_intent = any(
        word in q
        for word in ("publication", "publications", "paper", "papers")
    )
    return publication_intent and any(
        word in q for word in ("latest", "recent", "newest", "most recent")
    )


def asks_publication_list(question):
    q = (question or "").lower()
    has_publication_term = any(term in q for term in (
        "publication", "publications", "paper", "papers", "journal article",
    ))
    has_list_intent = any(term in q for term in (
        "list", "show", "mention", "get", "give me", "extract", "provide",
    ))
    return has_publication_term and has_list_intent and not asks_publication_count(question)


def _asks_count(question):
    q = (question or "").lower()
    return any(term in q for term in (
        "how many", "number of", "count of", "count the", "total number",
        "total count", "how much",
    ))


def asks_phd_scope(question):
    q = (question or "").lower()
    return bool(re.search(r"\bph\s*\.?\s*d\b|\bdoctoral\b", q))


def asks_thesis_count(question):
    q = (question or "").lower()
    thesis_term = any(term in q for term in (
        "thesis", "theses", "phd", "ph.d", "doctoral", "students guided",
        "students supervised", "phd guided", "phd supervised",
    ))
    return _asks_count(q) and thesis_term


def asks_thesis_list(question):
    q = (question or "").lower()
    thesis_term = any(term in q for term in (
        "thesis", "theses", "phd", "ph.d", "doctoral", "students guided",
        "students supervised",
    ))
    list_term = any(term in q for term in (
        "name", "names", "who", "which student", "students", "list", "show",
        "mention", "guided", "supervised", "research topic", "research topics",
        "student list", "students list",
    ))
    return thesis_term and list_term and not _asks_count(q)


def _thesis_scope_sql(faculty_id=None, faculty_ids=None, department_wide=False,
                      phd_only=False):
    conditions = ["f.is_active IS DISTINCT FROM FALSE"]
    params = []
    if not department_wide:
        if faculty_ids:
            conditions.append("ts.faculty_id = ANY(%s)")
            params.append(list(faculty_ids))
        elif faculty_id is not None:
            conditions.append("ts.faculty_id = %s")
            params.append(faculty_id)
    if phd_only:
        # Normalize punctuation first: "Ph.D.", "PhD", and "Ph.D. Ongoing"
        # all become searchable as "phd". This filter intentionally relies on
        # verified program_level data; unknown levels must not be called Ph.D.
        conditions.append(
            "(REGEXP_REPLACE(LOWER(COALESCE(ts.program_level, '')), "
            "'[^a-z]', '', 'g') LIKE '%%phd%%' "
            "OR LOWER(COALESCE(ts.program_level, '')) LIKE '%%doctoral%%')"
        )
    return conditions, params


def thesis_counts(faculty_id=None, faculty_ids=None, year_range=None,
                  department_wide=False, phd_only=False):
    """Exact thesis/student counts from PostgreSQL; no semantic retrieval involved."""
    conditions, scope_params = _thesis_scope_sql(
        faculty_id, faculty_ids, department_wide, phd_only
    )
    if year_range:
        start, end = year_range
        sql = f"""
            SELECT
                COUNT(DISTINCT ts.id) AS total_records,
                COUNT(DISTINCT NULLIF(BTRIM(ts.student_name), '')) AS unique_students,
                COUNT(DISTINCT ts.id) FILTER (
                    WHERE ts.registration_year BETWEEN %s AND %s
                ) AS registered_records_in_period,
                COUNT(DISTINCT NULLIF(BTRIM(ts.student_name), '')) FILTER (
                    WHERE ts.registration_year BETWEEN %s AND %s
                ) AS students_registered_in_period,
                COUNT(DISTINCT ts.id) FILTER (
                    WHERE ts.completion_year BETWEEN %s AND %s
                ) AS completed_records_in_period,
                COUNT(DISTINCT NULLIF(BTRIM(ts.student_name), '')) FILTER (
                    WHERE ts.completion_year BETWEEN %s AND %s
                ) AS students_completed_in_period,
                COUNT(DISTINCT ts.id) FILTER (
                    WHERE ts.registration_year IS NULL
                ) AS records_without_registration_year,
                COUNT(DISTINCT ts.id) FILTER (
                    WHERE ts.completion_year IS NULL
                ) AS records_without_completion_year,
                COUNT(DISTINCT ts.id) FILTER (
                    WHERE (ts.registration_year BETWEEN %s AND %s)
                       OR (ts.completion_year BETWEEN %s AND %s)
                ) AS total_records_in_period,
                COUNT(DISTINCT NULLIF(BTRIM(ts.student_name), '')) FILTER (
                    WHERE (ts.registration_year BETWEEN %s AND %s)
                       OR (ts.completion_year BETWEEN %s AND %s)
                ) AS unique_students_in_period,
                COUNT(DISTINCT ts.id) FILTER (
                    WHERE ts.registration_year IS NULL
                      AND ts.completion_year IS NULL
                ) AS records_without_both_years
            FROM m2_thesis_supervision ts
            JOIN m2_faculties f ON f.id = ts.faculty_id
            WHERE {' AND '.join(conditions)}
        """
        # SELECT placeholders precede WHERE placeholders in SQL order.
        params = [
            start, end, start, end, start, end, start, end,
            start, end, start, end,
        ] + scope_params
    else:
        sql = f"""
            SELECT
                COUNT(DISTINCT ts.id) AS total_records,
                COUNT(DISTINCT NULLIF(BTRIM(ts.student_name), '')) AS unique_students,
                COUNT(DISTINCT ts.id) FILTER (
                    WHERE ts.completion_year IS NOT NULL
                ) AS records_with_completion_year,
                COUNT(DISTINCT ts.id) FILTER (
                    WHERE ts.registration_year IS NULL
                ) AS records_without_registration_year,
                COUNT(DISTINCT ts.id) FILTER (
                    WHERE ts.completion_year IS NULL
                ) AS records_without_completion_year
            FROM m2_thesis_supervision ts
            JOIN m2_faculties f ON f.id = ts.faculty_id
            WHERE {' AND '.join(conditions)}
        """
        params = scope_params

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()

    if year_range:
        return {
            "total_records_in_scope": row[0],
            "unique_students_in_scope": row[1],
            "registered_records_in_period": row[2],
            "students_registered_in_period": row[3],
            "completed_records_in_period": row[4],
            "students_completed_in_period": row[5],
            "records_without_registration_year": row[6],
            "records_without_completion_year": row[7],
            "total_records_in_period": row[8],
            "unique_students_in_period": row[9],
            "records_without_both_years": row[10],
        }
    return {
        "total_records": row[0],
        "unique_students": row[1],
        "records_with_completion_year": row[2],
        "records_without_registration_year": row[3],
        "records_without_completion_year": row[4],
    }


def fetch_thesis_rows(faculty_id=None, faculty_ids=None, year_range=None,
                      department_wide=False, phd_only=False, question=""):
    conditions, params = _thesis_scope_sql(
        faculty_id, faculty_ids, department_wide, phd_only
    )
    if year_range:
        year_column = "ts.completion_year" if any(term in (question or "").lower()
            for term in ("completed", "completion", "graduated")) else "ts.registration_year"
        conditions.append(f"{year_column} BETWEEN %s AND %s")
        params.extend(year_range)

    sql = f"""
        SELECT f.full_name, ts.program_level, ts.student_name,
               ts.research_topic, ts.registration_year, ts.completion_year,
               ts.status, ts.details, ts.source_url
        FROM m2_thesis_supervision ts
        JOIN m2_faculties f ON f.id = ts.faculty_id
        WHERE {' AND '.join(conditions)}
        ORDER BY ts.completion_year DESC NULLS LAST,
                 ts.registration_year DESC NULLS LAST,
                 ts.student_name NULLS LAST, ts.id
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            columns = [item.name for item in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]


def _export_format(question):
    q = (question or "").lower()
    if re.search(r"\b(xlsx|excel|spreadsheet)\b", q):
        return "xlsx"
    if re.search(r"\b(json)\b", q):
        return "json"
    if re.search(r"\b(tsv|tab[- ]separated)\b", q):
        return "tsv"
    if re.search(r"\b(csv)\b", q):
        return "csv"
    if re.search(r"\b(markdown|md file)\b", q):
        return "md"
    return None


def _is_export_request(question):
    q = (question or "").lower()
    fmt = _export_format(q)
    data_intent = any(term in q for term in (
        "publication", "publications", "journal", "paper", "papers",
        "thesis", "theses", "phd", "ph.d", "doctoral", "student names",
    ))
    # A requested output format is itself sufficient to request a file export
    # when the question clearly identifies a faculty-data domain.
    return bool(fmt and data_intent)


def _write_export(rows, file_stem, fmt):
    if not rows:
        print("No matching database records found; no export file was created.")
        return None
    export_dir = Path(__file__).resolve().parents[1] / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    path = export_dir / f"{file_stem}_{timestamp}.{fmt}"
    columns = list(rows[0].keys())

    if fmt in {"csv", "tsv"}:
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(
                handle, fieldnames=columns,
                delimiter="\t" if fmt == "tsv" else ",",
                extrasaction="ignore",
            )
            writer.writeheader()
            for row in rows:
                writer.writerow({key: _serializable(value) for key, value in row.items()})
    elif fmt == "json":
        with path.open("w", encoding="utf-8") as handle:
            json.dump(rows, handle, ensure_ascii=False, indent=2, default=str)
    elif fmt == "md":
        with path.open("w", encoding="utf-8") as handle:
            handle.write("| " + " | ".join(columns) + " |\n")
            handle.write("| " + " | ".join("---" for _ in columns) + " |\n")
            for row in rows:
                values = [str(_serializable(row.get(key, "")) or "").replace("|", "\\|").replace("\n", " ") for key in columns]
                handle.write("| " + " | ".join(values) + " |\n")
    elif fmt == "xlsx":
        try:
            from openpyxl import Workbook
        except ImportError:
            print("Excel export requires the already-installed openpyxl package. No file was created; request CSV instead if openpyxl is unavailable.")
            return None
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Faculty Data"
        sheet.append(columns)
        for row in rows:
            sheet.append([_serializable(row.get(key)) for key in columns])
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        workbook.save(path)
    print(f"Exported {len(rows)} records to: {path}")
    return path


def _serializable(value):
    if value is None:
        return ""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def fetch_publication_export_rows(faculty_id=None, faculty_ids=None,
                                  year_range=None, department_wide=False,
                                  journal_only=False):
    year_expr = _year_sql("p.publication_year")
    conditions = ["f.is_active IS DISTINCT FROM FALSE"]
    params = []
    if not department_wide:
        if faculty_ids:
            conditions.append("fp.faculty_id = ANY(%s)")
            params.append(list(faculty_ids))
        elif faculty_id is not None:
            conditions.append("fp.faculty_id = %s")
            params.append(faculty_id)
    if year_range:
        conditions.append(f"{year_expr} BETWEEN %s AND %s")
        params.extend(year_range)
    if journal_only:
        conditions.append("LOWER(COALESCE(p.publication_type, '')) LIKE '%%journal%%'")
    sql = f"""
        SELECT DISTINCT f.full_name AS faculty_name, p.id AS publication_id,
               p.title, p.publication_type, p.journal_or_conference AS venue,
               p.publisher, {year_expr} AS publication_year, p.publication_date,
               p.volume, p.issue, p.pages, p.doi, p.authors,
               p.source_url, p.source_document
        FROM m2_publications p
        JOIN m2_faculty_publications fp ON fp.publication_id = p.id
        JOIN m2_faculties f ON f.id = fp.faculty_id
        WHERE {' AND '.join(conditions)}
        ORDER BY publication_year DESC NULLS LAST,
                 p.publication_date DESC NULLS LAST, f.full_name, p.id
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            columns = [item.name for item in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]


def run_export_query(question, faculty_id=None, faculty_ids=None,
                     faculty_name=None, department_wide=False):
    q = (question or "").lower()
    has_export_verb = any(term in q for term in ("export", "download", "save as", "save the"))
    has_data_target = any(term in q for term in (
        "publication", "publications", "journal", "paper", "papers",
        "thesis", "theses", "phd", "ph.d", "doctoral", "student names",
    ))
    if has_export_verb and has_data_target and not _export_format(question):
        print("Please specify an export format: CSV, JSON, TSV, Excel (XLSX), or Markdown.")
        return True
    if not _is_export_request(question):
        return False
    fmt = _export_format(question)
    year_range = extract_year_range(question)
    q = question.lower()
    phd_only = asks_phd_scope(question)
    if any(term in q for term in ("thesis", "theses", "phd", "ph.d", "doctoral", "student name", "student names")):
        rows = fetch_thesis_rows(
            faculty_id=faculty_id, faculty_ids=faculty_ids,
            year_range=year_range, department_wide=department_wide,
            phd_only=phd_only, question=question,
        )
        stem = "faculty_thesis_supervision"
    elif any(term in q for term in ("publication", "publications", "journal", "paper", "papers")):
        rows = fetch_publication_export_rows(
            faculty_id=faculty_id, faculty_ids=faculty_ids,
            year_range=year_range, department_wide=department_wide,
            journal_only=("journal" in q),
        )
        stem = "faculty_journal_publications" if "journal" in q else "faculty_publications"
    else:
        print("Export format was recognized, but the requested data type was unclear. Specify publications or thesis supervision.")
        return True
    if not rows:
        print("No matching records found for the requested export filters.")
        return True
    _write_export(rows, stem, fmt)
    if year_range:
        print(f"Applied year filter: {year_range[0]}–{year_range[1]}.")
    if faculty_name and not department_wide:
        print(f"Faculty filter: {faculty_name}.")
    if "journal" in q:
        print("Publication-type filter: journal records only.")
    return True


def run_thesis_analytics(question, faculty_id=None, faculty_ids=None,
                         faculty_name=None, department_wide=False):
    if _is_export_request(question):
        return False  # Export handler will produce the complete record set.
    is_count = asks_thesis_count(question)
    is_list = asks_thesis_list(question)
    if not (is_count or is_list):
        return False

    year_range = extract_year_range(question)
    phd_only = asks_phd_scope(question)
    label = "Ph.D. thesis-supervision records" if phd_only else "thesis-supervision records"
    if department_wide:
        scope = "active CSED faculty"
    elif faculty_name:
        scope = faculty_name
    else:
        scope = "the current CSED faculty dataset"

    if is_count:
        counts = thesis_counts(
            faculty_id=faculty_id, faculty_ids=faculty_ids,
            year_range=year_range, department_wide=department_wide,
            phd_only=phd_only,
        )
        print(f"\nDatabase counts for {label} associated with {scope}:")
        if year_range:
            print(f"- Registration-year range: {year_range[0]}–{year_range[1]}")
            total_scope_records = counts["total_records_in_scope"]
            registration_years_missing = counts["records_without_registration_year"]
            completion_years_missing = counts["records_without_completion_year"]
            if total_scope_records and registration_years_missing == total_scope_records:
                print(
                    "- Theses registered in period: NOT DETERMINABLE "
                    "(all records in scope have a missing registration_year; "
                    f"the raw SQL match count is {counts['registered_records_in_period']})"
                )
                print(
                    "- Distinct students registered in period: NOT DETERMINABLE "
                    "(registration years are missing for all records in scope)"
                )
            else:
                print(f"- Records registered in period: {counts['registered_records_in_period']}")
                print(f"- Distinct named students registered in period: {counts['students_registered_in_period']}")
            if total_scope_records and completion_years_missing == total_scope_records:
                print(
                    "- Theses completed in period: NOT DETERMINABLE "
                    "(all records in scope have a missing completion_year; "
                    f"the raw SQL match count is {counts['completed_records_in_period']})"
                )
                print(
                    "- Distinct students completed in period: NOT DETERMINABLE "
                    "(completion years are missing for all records in scope)"
                )
            else:
                print(f"- Records completed in period: {counts['completed_records_in_period']}")
                print(f"- Distinct named students completed in period: {counts['students_completed_in_period']}")
            print(
                f"- Total supervision records with a listed registration OR completion year in period: "
                f"{counts['total_records_in_period']}"
            )
            print(
                f"- Distinct named students with a listed registration OR completion year in period: "
                f"{counts['unique_students_in_period']}"
            )
            print(f"- Records with no registration year: {registration_years_missing}")
            print(f"- Records with no completion year: {completion_years_missing}")
            print(f"- Records missing BOTH registration and completion years: {counts['records_without_both_years']}")
            print("Registration counts use registration_year; completion counts use completion_year.")
            if counts["records_without_both_years"]:
                print(
                    "Data-quality note: records missing both year fields cannot be assigned to any year range. "
                    "The period totals may therefore exclude those records; verify them against the official profile."
                )
        else:
            print(f"- Thesis-supervision records: {counts['total_records']}")
            print(f"- Distinct named students: {counts['unique_students']}")
            print(f"- Records with a completion year: {counts['records_with_completion_year']}")
            print(f"- Records with no registration year: {counts['records_without_registration_year']}")
            print(f"- Records with no completion year: {counts['records_without_completion_year']}")
        return True

    rows = fetch_thesis_rows(
        faculty_id=faculty_id, faculty_ids=faculty_ids,
        year_range=year_range, department_wide=department_wide,
        phd_only=phd_only, question=question,
    )
    if not rows:
        if phd_only:
            # Distinguish "no Ph.D. students" from "program levels not classified".
            conditions, scope_params = _thesis_scope_sql(
                faculty_id=faculty_id,
                faculty_ids=faculty_ids,
                department_wide=department_wide,
                phd_only=False,
            )
            unknown_sql = f"""
                SELECT
                    COUNT(*) FILTER (
                        WHERE ts.program_level IS NULL
                           OR BTRIM(ts.program_level) = ''
                           OR LOWER(BTRIM(ts.program_level)) IN
                              ('not specified on source page',
                               'not classified from source heading',
                               'unknown', 'n/a')
                    ) AS unclassified,
                    COUNT(*) AS total
                FROM m2_thesis_supervision ts
                JOIN m2_faculties f ON f.id = ts.faculty_id
                WHERE {' AND '.join(conditions)}
            """
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(unknown_sql, scope_params)
                    unclassified, total = cur.fetchone()
            if total and unclassified:
                scope_label = faculty_name or (
                    "active CSED faculty" if department_wide else "the selected faculty"
                )
                print(
                    f"Cannot reliably identify Ph.D.-only records for {scope_label}: "
                    f"{unclassified} of {total} thesis records have an unclassified "
                    "program level. The database must be reconciled with the official "
                    "Thesis Supervised page before a Ph.D.-specific count/list can be trusted."
                )
            else:
                print(
                    "No Ph.D. thesis-supervision records matched the verified program-level "
                    "and year filters."
                )
        else:
            print("No thesis-supervision records matched the requested faculty and year filters.")
        return True
    if year_range:
        basis = "completion_year" if any(term in question.lower() for term in ("completed", "completion", "graduated")) else "registration_year"
        print(f"\nThesis records filtered by {basis} {year_range[0]}–{year_range[1]} ({len(rows)} records):")
    else:
        print(f"\nThesis-supervision records for {scope} ({len(rows)} records):")
    for index, row in enumerate(rows, 1):
        student = row.get("student_name") or "Student name not recorded"
        topic = row.get("research_topic") or "Research topic not recorded"
        print(f"{index}. {student} — {topic}")
        meta = []
        if row.get("program_level"):
            meta.append(str(row["program_level"]))
        if row.get("registration_year") is not None:
            meta.append(f"Registered: {row['registration_year']}")
        if row.get("completion_year") is not None:
            meta.append(f"Completed: {row['completion_year']}")
        if row.get("status"):
            meta.append(str(row["status"]))
        if meta:
            print("   " + " | ".join(meta))
        if row.get("source_url"):
            print(f"   Source: {row['source_url']}")
    return True


def _year_sql(expression="p.publication_year"):
    """Return a usable publication year without trusting malformed values.

    Prefer the structured publication_year when it is a four-digit year;
    otherwise fall back to the year of publication_date. This lets date-range
    queries use available structured evidence without guessing from titles.
    """
    # Reject implausible future years (for example, 2064) rather than
    # allowing corrupt metadata to dominate "latest publication" results.
    # Permit the current year plus one for records marked in press.
    return (
        "COALESCE("
        f"CASE WHEN ({expression})::text ~ '^(19|20)[0-9]{{2}}$' "
        f"AND ({expression})::text::integer BETWEEN 1900 "
        "AND EXTRACT(YEAR FROM CURRENT_DATE)::integer + 1 "
        f"THEN ({expression})::text::integer ELSE NULL END, "
        "CASE WHEN EXTRACT(YEAR FROM p.publication_date)::integer "
        "BETWEEN 1900 AND EXTRACT(YEAR FROM CURRENT_DATE)::integer + 1 "
        "THEN EXTRACT(YEAR FROM p.publication_date)::integer ELSE NULL END"
        ")"
    )


def publication_count(faculty_id=None, faculty_ids=None, year_range=None, journal_only=False):
    """
    Count distinct publication records and faculty-publication links.

    Unique publications count each publication once, even if several CSED
    faculty co-authored it. Association count counts each faculty link.
    """
    year_expr = _year_sql("p.publication_year")
    where = ["f.is_active IS DISTINCT FROM FALSE"]
    params = []

    # A total count includes records with an unrecorded year. A bounded
    # year-range query can only include records with a valid structured year.
    if year_range:
        where.append(f"{year_expr} BETWEEN %s AND %s")
        params.extend(year_range)
    if journal_only:
        where.append("LOWER(COALESCE(p.publication_type, '')) LIKE '%%journal%%'")

    if faculty_ids:
        where.append("fp.faculty_id = ANY(%s)")
        params.append(list(faculty_ids))
    elif faculty_id is not None:
        where.append("fp.faculty_id = %s")
        params.append(faculty_id)

    sql = f"""
        SELECT COUNT(DISTINCT p.id) AS unique_publications,
               COUNT(*) AS faculty_publication_associations,
               COUNT(DISTINCT p.id) FILTER (
                   WHERE {year_expr} IS NULL
               ) AS publications_without_known_year
        FROM m2_publications p
        JOIN m2_faculty_publications fp ON fp.publication_id = p.id
        JOIN m2_faculties f ON f.id = fp.faculty_id
        WHERE {' AND '.join(where)}
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()

    return {
        "unique_publications": row[0],
        "faculty_publication_associations": row[1],
        "publications_without_known_year": row[2],
    }


def fetch_publication_list(faculty_id=None, faculty_ids=None, year_range=None,
                           limit=5, recent_year_window=False, journal_only=False):
    """
    Fetch publication records directly from PostgreSQL.

    If recent_year_window=True, use the five latest distinct publication years
    represented in the selected scope. Rows with missing/invalid years are
    not silently classified as recent.
    """
    year_expr = _year_sql("p.publication_year")
    conditions = ["f.is_active IS DISTINCT FROM FALSE"]
    params = []

    scope_ids = list(faculty_ids) if faculty_ids else (
        [faculty_id] if faculty_id is not None else None
    )
    if scope_ids:
        conditions.append("fp.faculty_id = ANY(%s)")
        params.append(scope_ids)

    if year_range:
        conditions.append(f"{year_expr} BETWEEN %s AND %s")
        params.extend(year_range)
    if journal_only:
        conditions.append("LOWER(COALESCE(p.publication_type, '')) LIKE '%%journal%%'")

    recent_cte = ""
    recent_join = ""

    if recent_year_window and not year_range:
        recent_cte = f"""
            WITH selected_years AS (
                SELECT DISTINCT {year_expr} AS pub_year
                FROM m2_publications p
                JOIN m2_faculty_publications fp
                    ON fp.publication_id = p.id
                JOIN m2_faculties f ON f.id = fp.faculty_id
                WHERE f.is_active IS DISTINCT FROM FALSE
                  AND {year_expr} IS NOT NULL
                  {"AND fp.faculty_id = ANY(%s)" if scope_ids else ""}
                  {"AND LOWER(COALESCE(p.publication_type, '')) LIKE '%%journal%%'" if journal_only else ""}
                ORDER BY pub_year DESC
                LIMIT 5
            )
        """
        if scope_ids:
            # The CTE placeholder appears before main-query placeholders.
            params = [scope_ids] + params
        recent_join = (
            f"JOIN selected_years sy ON sy.pub_year = {year_expr}"
        )
        conditions.append(f"{year_expr} IS NOT NULL")

    sql = f"""
        {recent_cte}
        SELECT DISTINCT
               p.id,
               p.title,
               p.publication_type,
               p.journal_or_conference,
               p.publisher,
               {year_expr} AS publication_year,
               p.publication_date,
               p.volume,
               p.issue,
               p.pages,
               p.doi,
               p.authors,
               p.source_url,
               p.source_document
        FROM m2_publications p
        JOIN m2_faculty_publications fp ON fp.publication_id = p.id
        JOIN m2_faculties f ON f.id = fp.faculty_id
        {recent_join}
        WHERE {' AND '.join(conditions)}
        ORDER BY publication_year DESC NULLS LAST,
                 p.publication_date DESC NULLS LAST,
                 p.id DESC
        LIMIT %s
    """
    params.append(limit)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    results = []
    for row in rows:
        (pub_id, title, pub_type, venue, publisher, year, publication_date,
         volume, issue, pages, doi, authors, source_url, source_document) = row
        results.append({
            "id": pub_id,
            "title": title or "(Untitled publication)",
            "publication_type": pub_type,
            "venue": venue,
            "publisher": publisher,
            "year": year,
            "publication_date": publication_date,
            "volume": volume,
            "issue": issue,
            "pages": pages,
            "doi": doi,
            "authors": authors,
            "source_url": source_url,
            "source_document": source_document,
            "faculty_name": None,
        })
    return results


def print_publications(publications):
    if not publications:
        print("No publication records matched that request.")
        return

    for index, item in enumerate(publications, start=1):
        print(f"\n{index}. {item['title']}")
        details = []
        if item["publication_date"] is not None:
            details.append(f"Published: {item['publication_date']}")
        elif item["year"] is not None:
            details.append(f"Publication year: {item['year']} (exact date not recorded)")
        if item["venue"]:
            details.append(str(item["venue"]))
        if item["publication_type"]:
            details.append(str(item["publication_type"]))
        if details:
            print("   " + " | ".join(details))
        if item["authors"]:
            print(f"   Authors: {item['authors']}")
        if item["doi"]:
            print(f"   DOI: {item['doi']}")
        source = item["source_url"] or item["source_document"]
        if source:
            print(f"   Source: {source}")


def run_analytics(question, faculty_id=None, faculty_ids=None,
                  faculty_name=None, department_wide=False):
    """Handle exact publication counts and ordered publication lists."""
    year_range = extract_year_range(question)
    q = question.lower()
    is_count = asks_publication_count(question)
    is_latest = asks_latest_publications(question)
    is_list = asks_publication_list(question)

    if not (is_count or is_latest or is_list):
        return False

    if is_count:
        journal_only = "journal" in q
        counts = publication_count(
            faculty_id=None if department_wide else faculty_id,
            faculty_ids=None if department_wide else faculty_ids,
            year_range=year_range,
            journal_only=journal_only,
        )
        scope = (
            "active CSED faculty profiles"
            if department_wide
            else faculty_name
            if faculty_name
            else "CSED faculty profiles"
        )
        period = (
            f" in {year_range[0]}" if year_range and year_range[0] == year_range[1]
            else f" from {year_range[0]} to {year_range[1]}" if year_range else ""
        )
        if department_wide:
            range_label = (
                f"the year {year_range[0]}" if year_range and year_range[0] == year_range[1]
                else f"the period {year_range[0]}–{year_range[1]}" if year_range
                else "the available database period"
            )
            print(
                f"\nFor {range_label}, the database does not independently "
                "verify publications published by CSED itself. The count below "
                "covers publication records linked to active CSED faculty profiles."
            )
        print(
            f"Publication count associated with {scope}{period}: "
            f"{counts['unique_publications']} unique publication records."
        )
        if journal_only:
            print("Publication-type filter: journal records only.")
        print(
            "- Faculty-publication associations: "
            f"{counts['faculty_publication_associations']}"
        )
        if not year_range:
            print(
                "- Records without a usable publication year/date: "
                f"{counts['publications_without_known_year']}"
            )
        print(
            "Unique publication records count each database record once; "
            "faculty-publication associations count faculty-to-publication links. "
            "A co-authored paper may have multiple faculty associations. "
            "Year-range counts use a valid structured year, falling back to "
            "publication_date when available. "
            + (
                "Records without a usable year/date are excluded from this range."
                if year_range
                else "The total includes records with unknown years."
            )
        )
        return True

    asks_for_one_latest = (
        bool(re.search(r"\b(latest|newest|most recent)\s+one\b", q))
        or ("latest publication" in q and "publications" not in q)
    )
    limit = 1 if asks_for_one_latest else requested_limit(question, default=5)
    use_recent_window = (
        any(word in q for word in ("recent", "latest", "newest"))
        and year_range is None
    )

    publications = fetch_publication_list(
        faculty_id=None if department_wide else faculty_id,
        faculty_ids=None if department_wide else faculty_ids,
        year_range=year_range,
        limit=limit,
        recent_year_window=use_recent_window,
        journal_only=("journal" in q),
    )

    if department_wide:
        print("\nPublication records associated with active CSED faculty:")
    elif faculty_name:
        print(f"\nPublications for {faculty_name}:")

    if use_recent_window:
        print(
            "Sorted by recorded publication year, then exact publication date "
            "where available. Records without an exact date are shown with "
            "their year only; their order within that year cannot be confirmed."
        )
    if year_range:
        print(f"Publication-year range requested: {year_range[0]}–{year_range[1]}.")
    print_publications(publications)
    return True



def run_combined_recent_query(question, faculty_name=None, faculty_ids=None,
                              faculty_id=None):
    """
    For mixed requests such as "research areas and recent publications",
    fetch recent publications by structured year and retrieve other sections
    separately so the publication list does not crowd out the other section.
    """
    q = question.lower()
    requested = detect_requested_sections(question)
    has_recent_intent = any(
        term in q for term in ("recent", "latest", "newest", "most recent")
    )
    if (
        not has_recent_intent
        or "publications" not in requested
        or not any(section != "publications" for section in requested)
    ):
        return False

    other_sections = [section for section in requested if section != "publications"]
    other_results = faculty_search(
        question,
        top_k=TOP_K,
        faculty_name=faculty_name,
        sections=other_sections,
    )

    publications = fetch_publication_list(
        faculty_id=faculty_id,
        faculty_ids=faculty_ids,
        limit=requested_limit(question, default=5),
        recent_year_window=True,
    )

    evidence = []
    for item in other_results:
        evidence.append({
            "faculty": item.get("faculty_name") or faculty_name,
            "section": item.get("section"),
            "title": item.get("title"),
            "information": (
                item.get("content") or item.get("text")
                or item.get("information") or item.get("details")
            ),
            "source_url": (
                item.get("source_url") or item.get("source")
                or item.get("url")
            ),
            "retrieved_record": item,
        })
    for item in publications:
        evidence.append({
            "faculty": faculty_name,
            "section": "publications",
            "title": item.get("title"),
            "information": {
                "authors": item.get("authors"),
                "publication_type": item.get("publication_type"),
                "venue": item.get("venue"),
                "publisher": item.get("publisher"),
                "year": item.get("year"),
                "publication_date": item.get("publication_date"),
                "doi": item.get("doi"),
            },
            "source_url": item.get("source_url") or item.get("source_document"),
        })

    print("\n" + generate_faculty_answer(
        question,
        evidence,
        faculty_name=faculty_name,
    ))
    print_sources(evidence)
    return True


def should_reuse_faculty_context(question, status, department_wide):
    if status != "none" or department_wide:
        return False
    q = question.lower()
    followup_signals = (
        "his ", "her ", "their ", "he ", "she ", "them ",
        "those ", "these ", "that professor", "this professor",
        "his'", "her'", "what about", "how many", "latest",
        "recent", "achievements", "publications", "research areas",
        "education", "courses", "thesis", "supervision",
    )
    return any(signal in q for signal in followup_signals)


def print_sources(evidence):
    """Print unique source URLs associated with retrieved evidence."""
    sources = []
    seen = set()
    for item in evidence:
        url = item.get("source_url")
        if isinstance(url, str) and url.startswith(("https://", "http://")):
            if url not in seen:
                seen.add(url)
                sources.append(url)
    if sources:
        print("\nSources:")
        for index, url in enumerate(sources, start=1):
            print(f"[{index}] {url}")


def interactive_session():
    """Keep corpus, embeddings, faculty context, and short history in memory."""
    print("Loading Module II faculty data and embedding cache...")
    count = ensure_corpus_loaded()
    # ensure_corpus_loaded currently returns None; use the loaded module state
    # to report the actual count without reloading data.
    import importlib
    retrieval_module = importlib.import_module(
        "module2.retrieval.faculty_search"
    )
    count = len(retrieval_module._records or [])
    print(f"Ready. Searchable records loaded: {count}")
    print("Ask questions continuously. Type 'exit' or 'quit' to stop.")
    print("Commands: /context shows the current faculty; /reset clears context.\n")

    active_faculty_id = None
    active_faculty_ids = None
    active_faculty_name = None
    history = deque(maxlen=HISTORY_LIMIT)

    while True:
        try:
            question = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSession ended.")
            break

        if not question:
            continue
        command = question.lower()

        if command in {"exit", "quit"}:
            print("Session ended.")
            break
        if command == "/context":
            print(f"Current faculty: {active_faculty_name or 'none'}")
            print("Recent turns:")
            if not history:
                print("- No questions yet.")
            for old_question, _ in history:
                print(f"- {old_question}")
            continue
        if command == "/reset":
            active_faculty_id = None
            active_faculty_ids = None
            active_faculty_name = None
            history.clear()
            print("Conversation context cleared.")
            continue

        department_wide = is_department_wide_question(question)
        resolved_ids, explicit_name, status = resolve_faculty(
            question, _get_records()
        )

        if status == "ambiguous":
            print("That faculty name is ambiguous. Please use the full name.")
            continue
        if status == "unresolved":
            print(
                "I could not match that name to the Module II MNNIT CSED faculty records. "
                "I can answer using the CSED faculty dataset only; please check the faculty "
                "name or ask about a faculty member listed in the department records."
            )
            continue

        # Keep this assistant focused on the CSED faculty dataset. A named faculty
        # query, a recognized CSED-wide query, or a contextual faculty follow-up is allowed.
        has_existing_context = bool(active_faculty_name)
        if (
            status != "matched"
            and not is_csed_faculty_related_question(
                question, has_faculty_context=has_existing_context
            )
        ):
            print(
                "I can help with MNNIT CSED faculty records, including faculty "
                "profiles, education, research areas, courses, publications, "
                "achievements, thesis/Ph.D. supervision, and database-backed "
                "counts or exports. This query does not appear to be related "
                "to CSED faculty data. Please ask a question within that scope."
            )
            continue

        if status == "matched":
            # Resolve the matching IDs, not just a display name. The existing
            # resolver handles duplicate directory records with the same name.
            active_faculty_ids = set(resolved_ids)
            active_faculty_id = (
                next(iter(active_faculty_ids))
                if len(active_faculty_ids) == 1 else None
            )
            active_faculty_name = explicit_name
        elif department_wide:
            # Run this turn as department-wide, but retain the last named
            # faculty as a conversational antecedent for a subsequent
            # pronoun follow-up such as "Mention his latest publication."
            # The department_wide flag still controls the current SQL query.
            pass
        elif active_faculty_name and should_reuse_faculty_context(
            question, status, department_wide
        ):
            pass
        else:
            # Do not carry old faculty context into an unrelated broad query.
            active_faculty_id = None
            active_faculty_ids = None
            active_faculty_name = None

        previous_question = history[-1][0].lower() if history else ""
        effective_question = question
        if (
            any(term in command for term in ("latest", "most recent", "newest"))
            and any(term in command for term in ("one", "ones", "it", "them"))
            and any(term in previous_question for term in ("publication", "paper"))
        ):
            effective_question = question + " publications"

        history.append((question, active_faculty_name))

        if run_export_query(
            effective_question,
            faculty_id=active_faculty_id,
            faculty_ids=active_faculty_ids,
            faculty_name=active_faculty_name,
            department_wide=department_wide,
        ):
            continue

        if run_combined_recent_query(
            effective_question,
            faculty_name=active_faculty_name,
            faculty_ids=active_faculty_ids,
            faculty_id=active_faculty_id,
        ):
            continue

        if run_thesis_analytics(
            effective_question,
            faculty_id=active_faculty_id,
            faculty_ids=active_faculty_ids,
            faculty_name=active_faculty_name,
            department_wide=department_wide,
        ):
            continue

        if run_analytics(
            effective_question,
            faculty_id=active_faculty_id,
            faculty_ids=active_faculty_ids,
            faculty_name=active_faculty_name,
            department_wide=department_wide,
        ):
            continue

        # Preserve current retrieval behavior, but pass the active faculty
        # name on a follow-up so records from other faculty cannot leak in.
        results = faculty_search(
            question,
            top_k=TOP_K,
            faculty_name=active_faculty_name,
        )

        evidence = []
        for item in results:
            evidence.append({
                "faculty": item.get("faculty_name") or active_faculty_name,
                "section": item.get("section"),
                "title": item.get("title"),
                "information": (
                    item.get("content") or item.get("text")
                    or item.get("information") or item.get("details")
                ),
                "source_url": (
                    item.get("source_url") or item.get("source")
                    or item.get("url")
                ),
                "retrieved_record": item,
            })

        print("\n" + generate_faculty_answer(
            question,
            evidence,
            faculty_name=active_faculty_name,
        ))
        print_sources(evidence)

        requested = detect_requested_sections(question)
        returned = {item["section"] for item in results}
        missing = [section for section in requested if section not in returned]
        if missing:
            print("Evidence was not retrieved for: " + ", ".join(missing))



def _get_records():
    # Access the already-loaded corpus; do not refetch or re-embed per turn.
    import importlib
    retrieval_module = importlib.import_module(
        "module2.retrieval.faculty_search"
    )
    if retrieval_module._records is None:
        retrieval_module.ensure_corpus_loaded()
    return retrieval_module._records or []


if __name__ == "__main__":
    try:
        interactive_session()
    except Exception as exc:
        print(f"Faculty assistant failed: {exc}")

import argparse
import json
import re
import sys
import unicodedata
from collections import defaultdict
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlparse

import requests

from module2.database.connection import get_connection
from module2.ingestion.faculty_profile import discover_profile_components

HEADERS = {"User-Agent": "DepartmentAI academic profile ingestion/1.0"}
TIMEOUT = 30


def configure_console_encoding():
    """Prevent legacy faculty names/publication text from crashing Windows output."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is not None and hasattr(stream, "reconfigure"):
            try:
                # UTF-8 preserves source text in redirected logs; backslashreplace
                # guarantees an unusual character can never terminate processing.
                stream.reconfigure(encoding="utf-8", errors="backslashreplace")
            except (OSError, ValueError):
                pass


def clean(value):
    return " ".join(repair_mojibake(value or "").split()).strip()


_MOJIBAKE_MARKERS = (
    "â€œ", "â€", "â€™", "â€“", "â€”", "â€¦", "Ã", "Â",
    "ΓÇ", "╬ô", "╬ôé", "ï»¿",
)


def repair_mojibake(value):
    """
    Repair common UTF-8 decoding artifacts without changing ordinary Unicode.
    Direct replacements cover Windows-1252's undefined 0x9D byte, which cannot
    be round-tripped through Python's cp1252 codec. Remaining cases are repaired
    only when a reversible candidate reduces known mojibake markers.
    """
    if not value:
        return value

    direct_replacements = {
        "â€œ": "“",
        "â€": "”",
        "â€\x9d": "”",
        "â€™": "’",
        "â€˜": "‘",
        "â€“": "–",
        "â€”": "—",
        "â€¦": "…",
        "ΓÇ£": "“",
        "ΓÇ¥": "”",
        "ΓÇÖ": "’",
        "ΓÇ‘": "‘",
        "ΓÇô": "–",
        "ΓÇö": "—",
    }
    text = value
    for broken, fixed in direct_replacements.items():
        text = text.replace(broken, fixed)

    for _ in range(3):
        if not any(marker in text for marker in _MOJIBAKE_MARKERS):
            break
        candidates = []
        for source_encoding in ("cp1252", "latin-1", "cp437"):
            try:
                candidate = text.encode(source_encoding).decode("utf-8")
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue
            old_score = sum(text.count(marker) for marker in _MOJIBAKE_MARKERS)
            new_score = sum(candidate.count(marker) for marker in _MOJIBAKE_MARKERS)
            if new_score < old_score:
                candidates.append((new_score, candidate))
        if not candidates:
            break
        candidates.sort(key=lambda item: item[0])
        text = candidates[0][1]
    return text


def normalized_name(name):
    """Normalize titles/case/punctuation for detecting duplicate faculty rows."""
    value = unicodedata.normalize("NFKD", clean(name)).casefold()
    value = re.sub(r"\b(professor|prof|doctor|dr)\b\.?", " ", value)
    return re.sub(r"[^a-z0-9]+", "", value)


def profile_key(url):
    """Return a stable identity hint from a stored faculty profile URL."""
    parsed = urlparse(url or "")
    path = parsed.path.rstrip("/").lower()
    if path.endswith("/preview.php"):
        login = parse_qs(parsed.query).get("login", [""])[0]
        return login.casefold() or (path, parsed.query.casefold())
    return path.rsplit("/", 1)[-1]


class AchievementParser(HTMLParser):
    """Collect paragraph/list/definition entries after the achievements heading."""

    SECTION_HEADINGS = {
        "basic information", "responsibilities", "research publications",
        "thesis supervised", "other academic achievements", "footer",
        "education", "courses taught", "research areas", "professional memberships",
    }

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.entries = []
        self.after_heading = False
        self.heading_text = ""
        self.heading_tag = None
        self.capture_tag = None
        self.capture_depth = 0
        self.buffer = []
        self.skip_tags = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in ("script", "style", "nav", "header", "footer"):
            self.skip_tags.append(tag)
            return
        if self.skip_tags:
            return
        if tag in ("h1", "h2", "h3", "h4", "h5"):
            self.heading_text = ""
            self.heading_tag = tag
        if self.after_heading and tag in ("p", "li", "dd"):
            if self.capture_tag is None:
                self.capture_tag = tag
                self.capture_depth = 1
                self.buffer = []
            elif tag == self.capture_tag:
                self.capture_depth += 1
        if self.after_heading and tag == "br" and self.capture_tag:
            self.buffer.append(" ")

    def handle_data(self, data):
        if self.skip_tags:
            return
        text = clean(data)
        if not text:
            return
        if self.heading_tag:
            self.heading_text = f"{self.heading_text} {text}".strip()
        if self.capture_tag:
            self.buffer.append(text)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if self.skip_tags:
            if tag == self.skip_tags[-1]:
                self.skip_tags.pop()
            return
        if self.heading_tag == tag:
            heading = clean(self.heading_text).casefold()
            if heading == "other academic achievements":
                self.after_heading = True
            elif self.after_heading and heading in self.SECTION_HEADINGS:
                self.after_heading = False
            self.heading_text = ""
            self.heading_tag = None
        if self.capture_tag == tag:
            self.capture_depth -= 1
            if self.capture_depth <= 0:
                entry = clean(" ".join(self.buffer))
                if entry and entry.casefold() not in self.SECTION_HEADINGS:
                    self.entries.append(entry)
                self.capture_tag = None
                self.capture_depth = 0
                self.buffer = []


class ThesisParser(HTMLParser):
    """Extract visible HTML table rows, retaining cell text as displayed."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self.current_row = None
        self.current_cell = None
        self.in_cell = False

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == "tr":
            self.current_row = []
        elif tag in ("td", "th") and self.current_row is not None:
            self.current_cell = []
            self.in_cell = True

    def handle_data(self, data):
        if self.in_cell and self.current_cell is not None:
            text = clean(data)
            if text:
                self.current_cell.append(text)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in ("td", "th") and self.in_cell and self.current_row is not None:
            self.current_row.append(clean(" ".join(self.current_cell)))
            self.current_cell = None
            self.in_cell = False
        elif tag == "tr" and self.current_row is not None:
            if any(self.current_row):
                self.rows.append(self.current_row)
            self.current_row = None


def fetch_html(url):
    response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    content = response.content

    # Prefer strict UTF-8 when valid; the source site often serves UTF-8 bytes
    # without a reliable charset declaration, which can make apparent_encoding
    # misdecode quotation marks and apostrophes.
    if content.startswith(b"\\xef\\xbb\\xbf"):
        html = content.decode("utf-8-sig")
    else:
        try:
            html = content.decode("utf-8")
        except UnicodeDecodeError:
            declared = response.encoding
            candidates = [declared, response.apparent_encoding, "cp1252"]
            html = None
            for encoding in candidates:
                if not encoding:
                    continue
                try:
                    html = content.decode(encoding)
                    break
                except (LookupError, UnicodeDecodeError):
                    continue
            if html is None:
                html = content.decode("utf-8", errors="replace")

    # Repair common legacy misdecoding in the HTML text as a safety net.
    return repair_mojibake(html)


def extract_achievements(html):
    parser = AchievementParser()
    parser.feed(html)
    parser.close()
    result, seen = [], set()
    no_data_phrases = {
        "none", "none listed", "nil", "n/a", "na", "not applicable",
        "not available", "no achievements", "no academic achievements",
        "no academic achievements listed", "no record", "no records",
    }
    for entry in parser.entries:
        cleaned = clean(entry)
        key = cleaned.casefold().strip(" .:-")
        # Treat explicit no-data placeholders as an empty section, not a record.
        if not key or key in no_data_phrases:
            continue
        if key not in seen:
            seen.add(key)
            result.append(cleaned)
    return result


def extract_theses(html):
    parser = ThesisParser()
    parser.feed(html)
    parser.close()
    records, seen = [], set()
    for row in parser.rows:
        cells = [clean(cell) for cell in row]
        if len(cells) < 4:
            continue
        serial, topic, student, year_text = cells[:4]
        header = " ".join(cells[:4]).casefold()
        if "research topic" in header or "name of student" in header or serial.casefold() in {
            "s.no", "s.no.", "s no", "serial no", "s. no."
        }:
            continue
        if not topic or not student:
            continue
        key = (topic.casefold(), student.casefold(), year_text.casefold())
        if key in seen:
            continue
        seen.add(key)
        records.append({
            "program_level": "Not specified on source page",
            "student_name": student,
            "research_topic": topic,
            "registration_year": None,
            "completion_year": None,
            "status": None,
            "details": (
                f"Source table year field (Completion/Registration Year): {year_text}"
                if year_text else "Source table did not provide a year"
            ),
            "source_year": year_text,
        })
    return records


def load_faculties(conn):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT f.id, f.full_name, f.profile_url,
                   COALESCE(pub.publication_count, 0) AS publication_count
            FROM m2_faculties f
            LEFT JOIN (
                SELECT faculty_id, COUNT(*) AS publication_count
                FROM m2_faculty_publications
                GROUP BY faculty_id
            ) pub ON pub.faculty_id = f.id
            ORDER BY f.id
        """)
        rows = cur.fetchall()

    # Merge rows only when BOTH profile URL identity and normalized name match.
    # This avoids silently merging different people who happen to share a slug.
    groups = defaultdict(list)
    for faculty_id, name, url, pub_count in rows:
        key = (profile_key(url), normalized_name(name))
        groups[key].append((faculty_id, name, url, pub_count))

    canonical = []
    duplicate_groups = []
    for key, group in groups.items():
        if len(group) > 1:
            duplicate_groups.append((key, [row[0] for row in group]))
        group.sort(key=lambda row: (
            row[3],
            not urlparse(row[2] or "").path.rstrip("/").lower().endswith("/preview.php"),
            row[0],
        ), reverse=True)
        canonical.append(group[0])

    canonical.sort(key=lambda row: row[0])
    return rows, canonical, duplicate_groups


def prepare_records(conn):
    all_rows, faculties, duplicate_groups = load_faculties(conn)
    prepared, errors = [], []
    print(f"Faculty rows in database: {len(all_rows)}", flush=True)
    print(f"Unique faculty profiles selected: {len(faculties)}", flush=True)
    if duplicate_groups:
        print("Duplicate faculty-row groups merged:", duplicate_groups, flush=True)

    for index, (faculty_id, name, profile_url, _) in enumerate(faculties, 1):
        print(f"\n[{index}/{len(faculties)}] Faculty ID {faculty_id}: {name}", flush=True)
        try:
            components = discover_profile_components(name, profile_url)
            if not components.achievements_url:
                raise ValueError("Achievements component URL not found")
            if not components.thesis_url:
                raise ValueError("Thesis component URL not found")

            achievements_html = fetch_html(components.achievements_url)
            thesis_html = fetch_html(components.thesis_url)
            achievements = extract_achievements(achievements_html)
            theses = extract_theses(thesis_html)

            prepared.append({
                "faculty_id": faculty_id,
                "name": name,
                "profile_url": profile_url,
                "achievements_url": components.achievements_url,
                "thesis_url": components.thesis_url,
                "achievements": achievements,
                "theses": theses,
            })
            print(f"  Achievements: {len(achievements)} | Thesis rows: {len(theses)}", flush=True)
            for item in achievements[:2]:
                print("  Achievement sample:", item[:160], flush=True)
            for item in theses[:2]:
                print("  Thesis sample:", item["student_name"], "|", item["research_topic"][:90], "|", item["source_year"], flush=True)
        except Exception as exc:
            errors.append((faculty_id, name, repr(exc)))
            print(f"  ERROR: {type(exc).__name__}: {exc}", flush=True)
    return all_rows, faculties, prepared, errors, duplicate_groups


def validate_prepared_records(all_rows, faculties, prepared, errors, duplicate_groups):
    print("\n" + "=" * 65, flush=True)
    print("FINAL PRE-INSERT VALIDATION", flush=True)
    print("Faculty rows in database:", len(all_rows), flush=True)
    print("Canonical profiles selected:", len(faculties), flush=True)
    print("Profiles successfully fetched and parsed:", len(prepared), flush=True)
    print("Profile errors:", len(errors), flush=True)
    print("Duplicate faculty-row groups merged:", len(duplicate_groups), flush=True)

    total_achievements = sum(len(f["achievements"]) for f in prepared)
    total_theses = sum(len(f["theses"]) for f in prepared)
    # Zero records in a section is valid: newer faculty may have no listed
    # achievements or supervised theses yet. Report these separately, do not fail.
    zero_achievement_profiles = [(f["faculty_id"], f["name"]) for f in prepared
                                 if not f["achievements"]]
    zero_thesis_profiles = [(f["faculty_id"], f["name"]) for f in prepared
                            if not f["theses"]]
    empty_achievements = [(f["faculty_id"], f["name"]) for f in prepared
                          if any(not clean(a) for a in f["achievements"])]
    incomplete_theses = []
    duplicate_theses = []
    for faculty in prepared:
        seen = set()
        for record in faculty["theses"]:
            key = (clean(record["student_name"]).casefold(),
                   clean(record["research_topic"]).casefold(),
                   clean(record["source_year"]).casefold())
            if key in seen:
                duplicate_theses.append((faculty["faculty_id"], faculty["name"], key))
            seen.add(key)
            if not clean(record["student_name"]) or not clean(record["research_topic"]):
                incomplete_theses.append((faculty["faculty_id"], faculty["name"], record))

    print("Achievement records parsed:", total_achievements, flush=True)
    print("Thesis records parsed:", total_theses, flush=True)
    print("Faculty with zero achievement entries (allowed):", len(zero_achievement_profiles), flush=True)
    for faculty_id, name in zero_achievement_profiles:
        print(f"  [no achievements listed] [{faculty_id}] {name}", flush=True)
    print("Faculty with zero thesis entries (allowed):", len(zero_thesis_profiles), flush=True)
    for faculty_id, name in zero_thesis_profiles:
        print(f"  [no theses listed] [{faculty_id}] {name}", flush=True)
    print("Duplicate thesis keys remaining:", len(duplicate_theses), flush=True)
    print("Blank achievement entries:", len(empty_achievements), flush=True)
    print("Theses missing student/topic:", len(incomplete_theses), flush=True)
    if errors:
        print("\nFailed profiles:", flush=True)
        for faculty_id, name, error in errors:
            print(f"  [{faculty_id}] {name}: {error}", flush=True)

    # Empty achievement lists are allowed (some profiles may publish none).
    # Insertion is blocked if any profile failed, or parsing produced invalid rows.
    passed = (
        len(prepared) == len(faculties)
        and not errors
        and not duplicate_theses
        and not empty_achievements
        and not incomplete_theses
    )
    # Do not compare achievement and thesis totals: they represent different
    # sections and naturally have different counts. Completeness is based on
    # successful profile processing, not equal row totals.
    print("Record totals compared for equality: NO (different source sections)", flush=True)
    print("Basic validation:", "PASS" if passed else "REVIEW REQUIRED", flush=True)
    return passed


def persist_records(conn, prepared):
    inserted_achievements = inserted_theses = skipped = 0
    with conn.transaction():
        with conn.cursor() as cur:
            for faculty in prepared:
                faculty_id = faculty["faculty_id"]
                for index, entry in enumerate(faculty["achievements"], 1):
                    cur.execute("""
                        SELECT 1 FROM m2_achievements
                        WHERE faculty_id = %s AND source_url = %s
                          AND COALESCE(description, '') = %s LIMIT 1
                    """, (faculty_id, faculty["achievements_url"], entry))
                    if cur.fetchone():
                        skipped += 1
                        continue
                    cur.execute("""
                        INSERT INTO m2_achievements
                            (faculty_id, category, title, description, source_url, raw_metadata)
                        VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                    """, (
                        faculty_id, "other_academic_achievement", entry[:500], entry,
                        faculty["achievements_url"],
                        json.dumps({"source_entry_number": index,
                                    "extraction_method": "HTML paragraph/list extraction"}),
                    ))
                    inserted_achievements += 1

                for record in faculty["theses"]:
                    cur.execute("""
                        SELECT 1 FROM m2_thesis_supervision
                        WHERE faculty_id = %s AND source_url = %s
                          AND student_name = %s
                          AND COALESCE(research_topic, '') = %s
                          AND COALESCE(details, '') = %s LIMIT 1
                    """, (
                        faculty_id, faculty["thesis_url"], record["student_name"],
                        record["research_topic"], record["details"] or "",
                    ))
                    if cur.fetchone():
                        skipped += 1
                        continue
                    cur.execute("""
                        INSERT INTO m2_thesis_supervision
                            (faculty_id, program_level, student_name, research_topic,
                             registration_year, completion_year, status, details, source_url)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        faculty_id, record["program_level"], record["student_name"],
                        record["research_topic"], record["registration_year"],
                        record["completion_year"], record["status"], record["details"],
                        faculty["thesis_url"],
                    ))
                    inserted_theses += 1
    return inserted_achievements, inserted_theses, skipped


def repair_existing_database_text(conn):
    """Repair only recognized mojibake markers in the two ingestion target tables."""
    changed = {"achievements": 0, "thesis_supervision": 0}
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute("SELECT id, title, description FROM m2_achievements")
            for record_id, title, description in cur.fetchall():
                fixed_title = repair_mojibake(title) if title else title
                fixed_description = repair_mojibake(description) if description else description
                if fixed_title != title or fixed_description != description:
                    cur.execute(
                        "UPDATE m2_achievements SET title = %s, description = %s WHERE id = %s",
                        (fixed_title, fixed_description, record_id),
                    )
                    changed["achievements"] += 1

            cur.execute("""
                SELECT id, student_name, research_topic, details
                FROM m2_thesis_supervision
            """)
            for record_id, student_name, research_topic, details in cur.fetchall():
                fixed_student = repair_mojibake(student_name) if student_name else student_name
                fixed_topic = repair_mojibake(research_topic) if research_topic else research_topic
                fixed_details = repair_mojibake(details) if details else details
                if (fixed_student != student_name or fixed_topic != research_topic
                        or fixed_details != details):
                    cur.execute("""
                        UPDATE m2_thesis_supervision
                        SET student_name = %s, research_topic = %s, details = %s
                        WHERE id = %s
                    """, (fixed_student, fixed_topic, fixed_details, record_id))
                    changed["thesis_supervision"] += 1
    return changed


def main():
    configure_console_encoding()
    parser = argparse.ArgumentParser(description="Ingest faculty achievements and thesis supervision.")
    parser.add_argument("--persist", action="store_true", help="Insert extracted records into PostgreSQL")
    parser.add_argument(
        "--repair-existing-encoding", action="store_true",
        help="Repair recognized mojibake in existing target-table text fields; no new rows are inserted",
    )
    args = parser.parse_args()
    if args.persist and args.repair_existing_encoding:
        parser.error("Choose either --persist or --repair-existing-encoding, not both")
    conn = get_connection()
    try:
        if args.repair_existing_encoding:
            changed = repair_existing_database_text(conn)
            print("Existing-text encoding repair complete.", flush=True)
            print("Achievement rows updated:", changed["achievements"], flush=True)
            print("Thesis-supervision rows updated:", changed["thesis_supervision"], flush=True)
            return
        all_rows, faculties, prepared, errors, duplicate_groups = prepare_records(conn)
        print("\n" + "=" * 65, flush=True)
        print("INGESTION SUMMARY" if args.persist else "DRY-RUN SUMMARY", flush=True)
        print("Faculty rows in database:", len(all_rows), flush=True)
        print("Unique profiles selected:", len(faculties), flush=True)
        print("Profiles parsed successfully:", len(prepared), flush=True)
        print("Faculty errors:", len(errors), flush=True)
        print("Achievement records parsed:", sum(len(f["achievements"]) for f in prepared), flush=True)
        print("Thesis records parsed:", sum(len(f["theses"]) for f in prepared), flush=True)

        validation_passed = validate_prepared_records(
            all_rows, faculties, prepared, errors, duplicate_groups
        )
        if not args.persist:
            print("\nNo database records were changed.", flush=True)
            return
        if not validation_passed:
            print("\nINSERTION BLOCKED: validation did not pass. No records were inserted.", flush=True)
            return

        achievements, theses, skipped = persist_records(conn, prepared)

        # IMPORTANT: prepare_records() queries the database first, which opens
        # psycopg's implicit outer transaction. persist_records() therefore
        # runs its conn.transaction() block as a nested transaction/savepoint.
        # Exiting that block does NOT commit the outer transaction. Commit it
        # explicitly here before verifying counts or closing the connection.
        conn.commit()

        with conn.cursor() as cur:
            cur.execute("SELECT current_database(), current_user, inet_server_addr(), inet_server_port()")
            db_identity = cur.fetchone()
            cur.execute("SELECT COUNT(*) FROM m2_achievements")
            achievement_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM m2_thesis_supervision")
            thesis_count = cur.fetchone()[0]

        if achievement_count < achievements or thesis_count < theses:
            raise RuntimeError(
                "Post-commit verification failed: table counts are lower than "
                "the number of rows reported inserted. Check the database connection."
            )

        print("\nCommitted database:", db_identity, flush=True)
        print("Inserted achievements:", achievements, flush=True)
        print("Inserted thesis records:", theses, flush=True)
        print("Duplicate records skipped:", skipped, flush=True)
        print("Total m2_achievements rows:", achievement_count, flush=True)
        print("Total m2_thesis_supervision rows:", thesis_count, flush=True)
    finally:
        conn.close()


if __name__ == "__main__":
    main()

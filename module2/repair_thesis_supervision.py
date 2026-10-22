"""
Safe reconciliation of Module II thesis records with their official source pages.

Default mode is DRY RUN. Use --apply only after reviewing the report.
This script never deletes records and never touches Module I.
"""
import argparse
import json
import re
from collections import Counter, defaultdict

from module2.database.connection import get_connection
from module2.ingestion.faculty_missing_sections import fetch_html, extract_theses


UNKNOWN_LEVELS = {
    "", "not specified on source page", "not classified from source heading",
    "unknown", "n/a", "none",
}


def normalize_record_text(value, topic=False):
    value = (value or "").casefold().strip()
    if topic:
        value = re.sub(r"^\s*\d+\s*[.)-]\s*", "", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def record_key(student_name, research_topic):
    return (
        normalize_record_text(student_name),
        normalize_record_text(research_topic, topic=True),
    )


def is_unknown_level(level):
    return (level or "").strip().casefold() in UNKNOWN_LEVELS


def load_sources_and_existing(conn):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT f.id, f.full_name, f.profile_url, t.source_url
            FROM m2_faculties f
            JOIN m2_thesis_supervision t ON t.faculty_id = f.id
            WHERE t.source_url IS NOT NULL
              AND BTRIM(t.source_url) <> ''
            ORDER BY f.id, t.source_url
        """)
        sources = cur.fetchall()

        cur.execute("""
            SELECT id, faculty_id, program_level, student_name, research_topic,
                   registration_year, completion_year, status, details, source_url
            FROM m2_thesis_supervision
            ORDER BY id
        """)
        columns = [item.name for item in cur.description]
        existing = [dict(zip(columns, row)) for row in cur.fetchall()]

    return sources, existing


def fetch_and_parse_sources(sources):
    parsed_sources = []
    errors = []
    for faculty_id, faculty_name, profile_url, source_url in sources:
        if "mnnit.ac.in" not in source_url.casefold():
            errors.append({
                "faculty_id": faculty_id,
                "faculty_name": faculty_name,
                "source_url": source_url,
                "error": "Source URL is outside the official mnnit.ac.in domain",
            })
            continue
        try:
            html = fetch_html(source_url)
            records = extract_theses(html)
            if not records:
                raise ValueError("Parser returned zero thesis records for a source with existing DB rows")
            parsed_sources.append({
                "faculty_id": faculty_id,
                "faculty_name": faculty_name,
                "profile_url": profile_url,
                "source_url": source_url,
                "records": records,
            })
        except Exception as exc:
            errors.append({
                "faculty_id": faculty_id,
                "faculty_name": faculty_name,
                "source_url": source_url,
                "error": f"{type(exc).__name__}: {exc}",
            })
    return parsed_sources, errors


def build_plan(existing, parsed_sources):
    """Match source records to existing rows conservatively.

    Exact student+topic matches are preferred. If an official page has a minor
    topic-text change, a unique same-student OR same-topic match can reuse the
    existing ID, but only when that candidate is unique and not already claimed.
    Ambiguous cases are reported rather than silently inserted or overwritten.
    """
    existing_by_source_key = defaultdict(list)
    existing_by_faculty_source = defaultdict(list)
    for row in existing:
        source = row.get("source_url") or ""
        existing_by_faculty_source[(row["faculty_id"], source)].append(row)
        key = (row["faculty_id"], source, *record_key(
            row.get("student_name"), row.get("research_topic")
        ))
        existing_by_source_key[key].append(row)

    plan = []
    ambiguous = []
    source_record_counts = Counter()
    claimed_ids = set()

    for source_group in parsed_sources:
        faculty_id = source_group["faculty_id"]
        source_url = source_group["source_url"]
        rows_for_source = existing_by_faculty_source[(faculty_id, source_url)]

        # First reserve all exact matches, so a fallback cannot steal a row
        # that belongs to a later source record.
        records_with_matches = []
        for record in source_group["records"]:
            source_record_counts[record.get("program_level", "unknown")] += 1
            key = (faculty_id, source_url, *record_key(
                record.get("student_name"), record.get("research_topic")
            ))
            matches = existing_by_source_key.get(key, [])
            if len(matches) > 1:
                ambiguous.append({
                    "faculty_id": faculty_id, "source_url": source_url,
                    "student_name": record["student_name"],
                    "research_topic": record["research_topic"],
                    "matching_db_ids": [row["id"] for row in matches],
                })
                records_with_matches.append((record, None, True))
            elif matches:
                records_with_matches.append((record, matches[0], False))
                claimed_ids.add(matches[0]["id"])
            else:
                records_with_matches.append((record, None, False))

        unmatched_records = [
            record for record, exact_match, already_ambiguous in records_with_matches
            if exact_match is None and not already_ambiguous
        ]
        unmatched_student_counts = Counter(
            record_key(record.get("student_name"), record.get("research_topic"))[0]
            for record in unmatched_records
        )
        unmatched_topic_counts = Counter(
            record_key(record.get("student_name"), record.get("research_topic"))[1]
            for record in unmatched_records
        )

        for record, exact_match, already_ambiguous in records_with_matches:
            if exact_match is not None:
                plan.append({
                    "faculty_id": faculty_id, "faculty_name": source_group["faculty_name"],
                    "source_url": source_url, "record": record, "existing": exact_match,
                })
                continue
            if already_ambiguous:
                continue

            student_key, topic_key = record_key(
                record.get("student_name"), record.get("research_topic")
            )
            # A fallback key must be unique on the source side as well as the
            # database side; repeated student/topic values are not safe to pair.
            student_key_unique = bool(student_key) and unmatched_student_counts[student_key] == 1
            topic_key_unique = bool(topic_key) and unmatched_topic_counts[topic_key] == 1
            if not student_key_unique and not topic_key_unique:
                ambiguous.append({
                    "faculty_id": faculty_id, "source_url": source_url,
                    "student_name": record["student_name"],
                    "research_topic": record["research_topic"],
                    "matching_db_ids": [],
                    "reason": "No unique source-side student/topic key for fallback matching",
                })
                continue

            candidates = []
            for row in rows_for_source:
                if row["id"] in claimed_ids:
                    continue
                old_student, old_topic = record_key(
                    row.get("student_name"), row.get("research_topic")
                )
                if (student_key_unique and student_key == old_student) or (topic_key_unique and topic_key == old_topic):
                    candidates.append(row)

            # Use a fallback only if exactly one row matches and no other
            # unmatched source record has the same fallback key. Otherwise stop.
            if len(candidates) == 1:
                candidate = candidates[0]
                claimed_ids.add(candidate["id"])
                plan.append({
                    "faculty_id": faculty_id, "faculty_name": source_group["faculty_name"],
                    "source_url": source_url, "record": record, "existing": candidate,
                })
            elif len(candidates) > 1:
                ambiguous.append({
                    "faculty_id": faculty_id, "source_url": source_url,
                    "student_name": record["student_name"],
                    "research_topic": record["research_topic"],
                    "matching_db_ids": [row["id"] for row in candidates],
                    "reason": "Fallback student/topic match is not unique",
                })
            else:
                plan.append({
                    "faculty_id": faculty_id, "faculty_name": source_group["faculty_name"],
                    "source_url": source_url, "record": record, "existing": None,
                })
    return plan, ambiguous, source_record_counts



def validate_reference_source_counts(parsed_sources):
    """
    Guard the known reference profile against accidental section loss.
    This is a validation checkpoint, not a hard-coded classification source.
    """
    expected = {
        "Ph.D. Completed": 16,
        "Ph.D. Ongoing": 4,
        "M.Tech Students": 92,
    }
    checks = []
    for group in parsed_sources:
        normalized_name = normalize_record_text(group["faculty_name"])
        if "rama shankar yadav" not in normalized_name:
            continue
        observed = Counter(
            record.get("source_section", "Unclassified source section")
            for record in group["records"]
        )
        checks.append({
            "faculty_id": group["faculty_id"],
            "faculty_name": group["faculty_name"],
            "source_url": group["source_url"],
            "expected": expected,
            "observed": {key: observed.get(key, 0) for key in expected},
            "total_observed": len(group["records"]),
            "passed": all(observed.get(key, 0) == value for key, value in expected.items())
                      and len(group["records"]) == sum(expected.values()),
        })
    return checks

def print_report(existing, parsed_sources, errors, plan, ambiguous, level_counts):
    actions = Counter()
    for item in plan:
        if item["existing"] is None:
            actions["insert"] += 1
        elif is_unknown_level(item["record"].get("program_level")):
            actions["preserve_unclassified"] += 1
        else:
            actions["update"] += 1

    print("THESIS RECONCILIATION REPORT")
    print("Mode: DRY RUN (no database writes)" if not errors else "Mode: VALIDATION FAILED")
    print(f"Existing database thesis rows: {len(existing)}")
    print(f"Official source pages discovered: {len(parsed_sources) + len(errors)}")
    print(f"Official source pages parsed: {len(parsed_sources)}")
    print(f"Source fetch/parse errors: {len(errors)}")
    print(f"Source records parsed: {len(plan) + len(ambiguous)}")
    print("Source record classification counts:")
    for label, count in sorted(level_counts.items()):
        print(f"  {label}: {count}")
    print("Planned actions:")
    for action in ("update", "insert", "preserve_unclassified"):
        print(f"  {action}: {actions[action]}")
    print(f"Ambiguous DB matches: {len(ambiguous)}")
    inserts = [item for item in plan if item["existing"] is None]
    if inserts:
        print("\nSOURCE RECORDS WITH NO SAFE EXISTING-ROW MATCH:")
        for item in inserts[:50]:
            print(json.dumps({
                "faculty_id": item["faculty_id"],
                "faculty_name": item["faculty_name"],
                "source_url": item["source_url"],
                "student_name": item["record"].get("student_name"),
                "research_topic": item["record"].get("research_topic"),
                "source_section": item["record"].get("source_section"),
            }, ensure_ascii=False))
    if errors:
        print("\nERRORS:")
        for item in errors:
            print(json.dumps(item, ensure_ascii=False))
    if ambiguous:
        print("\nAMBIGUOUS MATCHES:")
        for item in ambiguous[:50]:
            print(json.dumps(item, ensure_ascii=False))
    by_faculty = defaultdict(Counter)
    for item in plan:
        record = item["record"]
        section = record.get("source_section") or "Unclassified source section"
        by_faculty[(item["faculty_id"], item["faculty_name"])][section] += 1
    print("\nPER-FACULTY SOURCE SECTION COUNTS:")
    for (faculty_id, name), counts in sorted(by_faculty.items()):
        print(f"  [{faculty_id}] {name}: " + ", ".join(
            f"{key}={value}" for key, value in sorted(counts.items())
        ))
    return actions


def apply_plan(conn, plan):
    updated = inserted = preserved_unknown = 0
    with conn.transaction():
        with conn.cursor() as cur:
            for item in plan:
                record = item["record"]
                old = item["existing"]
                level = record.get("program_level")
                if is_unknown_level(level):
                    # Never replace a known classification with an unknown one.
                    if old is None:
                        cur.execute("""
                            INSERT INTO m2_thesis_supervision
                                (faculty_id, program_level, student_name, research_topic,
                                 registration_year, completion_year, status, details, source_url)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            item["faculty_id"], level, record["student_name"],
                            record.get("research_topic"), record.get("registration_year"),
                            record.get("completion_year"), record.get("status"),
                            record.get("details"), item["source_url"],
                        ))
                        inserted += 1
                    else:
                        preserved_unknown += 1
                    continue

                if old is None:
                    cur.execute("""
                        INSERT INTO m2_thesis_supervision
                            (faculty_id, program_level, student_name, research_topic,
                             registration_year, completion_year, status, details, source_url)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        item["faculty_id"], level, record["student_name"],
                        record.get("research_topic"), record.get("registration_year"),
                        record.get("completion_year"), record.get("status"),
                        record.get("details"), item["source_url"],
                    ))
                    inserted += 1
                    continue

                # Explicit source headings are authoritative for level/status.
                # A source-omitted year does not erase a previously populated year,
                # except Ph.D. Ongoing explicitly means there is no completion year.
                registration_year = record.get("registration_year")
                completion_year = record.get("completion_year")
                status = record.get("status")
                if record.get("source_section") == "Ph.D. Ongoing":
                    completion_year = None

                cur.execute("""
                    UPDATE m2_thesis_supervision
                    SET program_level = %s,
                        registration_year = COALESCE(%s, registration_year),
                        completion_year = CASE
                            WHEN %s = 'Ph.D. Ongoing' THEN NULL
                            ELSE COALESCE(%s, completion_year)
                        END,
                        status = COALESCE(%s, status),
                        details = %s
                    WHERE id = %s
                """, (
                    level, registration_year, record.get("source_section"),
                    completion_year, status, record.get("details"), old["id"],
                ))
                updated += 1
    return {"updated": updated, "inserted": inserted, "preserved_unclassified": preserved_unknown}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true",
        help="Commit the validated reconciliation. Without this flag, no DB writes occur.",
    )
    parser.add_argument(
        "--allow-source-count-drift", action="store_true",
        help="Allow apply if the known R. S. Yadav reference profile no longer has 16/4/92 rows; use only after manual source review.",
    )
    args = parser.parse_args()

    conn = get_connection()
    try:
        sources, existing = load_sources_and_existing(conn)
        parsed_sources, errors = fetch_and_parse_sources(sources)
        plan, ambiguous, level_counts = build_plan(existing, parsed_sources)
        reference_checks = validate_reference_source_counts(parsed_sources)
        actions = print_report(existing, parsed_sources, errors, plan, ambiguous, level_counts)

        reference_failed = any(not item["passed"] for item in reference_checks)
        if reference_checks:
            print("\nR. S. YADAV REFERENCE COUNT CHECK:")
            for item in reference_checks:
                print(json.dumps(item, ensure_ascii=False))
        if errors or ambiguous:
            print("\nAPPLY BLOCKED: fix every source/ambiguity error before writing.")
            return 2
        insert_count = sum(1 for item in plan if item["existing"] is None)
        if args.apply and insert_count and len(plan) == len(existing):
            print(
                "\nAPPLY BLOCKED: source record count equals the current database row count, "
                "but unmatched source records would be inserted. This could create a duplicate "
                "while leaving a database-only row. Review the listed unmatched records first."
            )
            return 2
        if reference_failed and not args.allow_source_count_drift:
            print(
                "\nREFERENCE CHECK FAILED: expected 16 Ph.D. Completed, "
                "4 Ph.D. Ongoing and 92 M.Tech rows for R. S. Yadav. "
                "Review the source/parser output. Apply is blocked unless the "
                "current official page was manually reviewed and "
                "--allow-source-count-drift is supplied."
            )
            if args.apply:
                return 2
        if not args.apply:
            print("\nDRY RUN COMPLETE. Review this report, then rerun with --apply to commit.")
            return 0

        if reference_failed and not args.allow_source_count_drift:
            print("\nAPPLY BLOCKED: R. S. Yadav reference count check failed.")
            return 2

        result = apply_plan(conn, plan)
        conn.commit()
        print("\nAPPLY COMPLETE")
        print(json.dumps(result, indent=2))
        with conn.cursor() as cur:
            cur.execute("""
                SELECT program_level, COALESCE(status, '<NULL>'), COUNT(*),
                       COUNT(registration_year), COUNT(completion_year)
                FROM m2_thesis_supervision
                GROUP BY 1, 2 ORDER BY 1, 2
            """)
            print("\nPOST-APPLY DATABASE DISTRIBUTION")
            for row in cur.fetchall():
                print(row)
        return 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())

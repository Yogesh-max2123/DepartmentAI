"""
Read-only quality audit of Module II thesis-supervision records across CSED faculty.

Run from the DepartmentAI project root:
    python -m module2.ingestion.audit_thesis_supervision

This script never changes database rows. It reports missing fields, duplicate-like
records, and year/program/status quality indicators for every faculty with records.
It cannot detect thesis entries missing entirely from the database unless source
profiles are separately compared with the report.
"""
import csv
import re
from collections import defaultdict
from pathlib import Path

from module2.database.connection import get_connection


def norm(value):
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def main():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT f.id, f.full_name, f.is_active,
                       ts.id, ts.program_level, ts.student_name, ts.research_topic,
                       ts.registration_year, ts.completion_year, ts.status,
                       ts.source_url, ts.details
                FROM m2_faculties f
                JOIN m2_thesis_supervision ts ON ts.faculty_id = f.id
                ORDER BY f.full_name, ts.id
            """)
            rows = cur.fetchall()

    if not rows:
        print("AUDIT STOPPED: no thesis-supervision rows were found in m2_thesis_supervision.")
        return

    grouped = defaultdict(list)
    for row in rows:
        faculty_id, faculty_name, active, thesis_id, program, student, topic, reg_year, comp_year, status, source_url, details = row
        grouped[(faculty_id, faculty_name, active)].append({
            "id": thesis_id,
            "program_level": program,
            "student_name": student,
            "research_topic": topic,
            "registration_year": reg_year,
            "completion_year": comp_year,
            "status": status,
            "source_url": source_url,
            "details": details,
        })

    report = []
    duplicate_rows = []
    for (faculty_id, faculty_name, active), items in grouped.items():
        missing_program = sum(not norm(r["program_level"]) for r in items)
        missing_student = sum(not norm(r["student_name"]) for r in items)
        missing_topic = sum(not norm(r["research_topic"]) for r in items)
        missing_status = sum(not norm(r["status"]) for r in items)
        missing_reg = sum(r["registration_year"] is None for r in items)
        missing_comp = sum(r["completion_year"] is None for r in items)
        missing_both = sum(r["registration_year"] is None and r["completion_year"] is None for r in items)
        missing_source = sum(not (r["source_url"] or "").strip() for r in items)

        seen = {}
        dup_count = 0
        for r in items:
            key = (norm(r["student_name"]), norm(r["research_topic"]), norm(r["program_level"]))
            if key != ("", "", "") and key in seen:
                dup_count += 1
                duplicate_rows.append({
                    "faculty_id": faculty_id,
                    "faculty_name": faculty_name,
                    "first_row_id": seen[key],
                    "possible_duplicate_row_id": r["id"],
                    "student_name": r["student_name"],
                    "research_topic": r["research_topic"],
                    "program_level": r["program_level"],
                })
            else:
                seen[key] = r["id"]

        report.append({
            "faculty_id": faculty_id,
            "faculty_name": faculty_name,
            "is_active": active,
            "thesis_records": len(items),
            "missing_program_level": missing_program,
            "missing_student_name": missing_student,
            "missing_research_topic": missing_topic,
            "missing_status": missing_status,
            "missing_registration_year": missing_reg,
            "missing_completion_year": missing_comp,
            "missing_both_years": missing_both,
            "missing_source_url": missing_source,
            "possible_duplicate_rows": dup_count,
        })

    report.sort(key=lambda r: (-(
        r["missing_program_level"] + r["missing_student_name"] +
        r["missing_research_topic"] + r["missing_status"] +
        r["missing_both_years"] + r["possible_duplicate_rows"]
    ), r["faculty_name"].lower()))

    out_dir = Path("module2") / "exports"
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "thesis_supervision_quality_audit.csv"
    duplicates_path = out_dir / "thesis_supervision_possible_duplicates.csv"

    with report_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(report[0].keys()))
        writer.writeheader()
        writer.writerows(report)

    with duplicates_path.open("w", newline="", encoding="utf-8-sig") as f:
        fields = [
            "faculty_id", "faculty_name", "first_row_id",
            "possible_duplicate_row_id", "student_name", "research_topic",
            "program_level",
        ]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(duplicate_rows)

    print("THESIS-SUPERVISION DATABASE AUDIT (READ-ONLY)")
    print(f"Faculty with at least one stored thesis record: {len(report)}")
    print(f"Total stored thesis-supervision rows: {sum(r['thesis_records'] for r in report)}")
    print(f"Rows with missing both year fields: {sum(r['missing_both_years'] for r in report)}")
    print(f"Possible duplicate rows: {len(duplicate_rows)}")
    print("\nFaculty requiring review (missing core fields, missing both years, or possible duplicates):")
    flagged = [
        r for r in report if (
            r["missing_program_level"] or r["missing_student_name"] or
            r["missing_research_topic"] or r["missing_status"] or
            r["missing_both_years"] or r["possible_duplicate_rows"]
        )
    ]
    if not flagged:
        print("No database-level issues detected by these checks.")
    else:
        for r in flagged:
            print(
                f"- {r['faculty_name']}: records={r['thesis_records']}, "
                f"missing program={r['missing_program_level']}, "
                f"student={r['missing_student_name']}, topic={r['missing_research_topic']}, "
                f"status={r['missing_status']}, both years={r['missing_both_years']}, "
                f"possible duplicates={r['possible_duplicate_rows']}"
            )

    print("\nReports written:")
    print(f"- {report_path.resolve()}")
    print(f"- {duplicates_path.resolve()}")
    print("\nLIMITATION: This is a database quality audit, not a complete source-vs-database reconciliation.")
    print("To detect missing thesis entries, compare each official faculty profile's Thesis Supervised section")
    print("against the corresponding faculty rows before making any bulk corrections.")


if __name__ == "__main__":
    main()

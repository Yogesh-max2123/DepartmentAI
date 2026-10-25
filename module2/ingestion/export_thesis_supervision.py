"""Export all stored Module II thesis-supervision records for manual verification.

Read-only: this script does not modify database rows.

Run from the DepartmentAI project root:
    python -m module2.ingestion.export_thesis_supervision

Creates:
    module2/exports/thesis_supervision_all_faculty.csv
    module2/exports/thesis_supervision_faculty_summary.csv
"""

import csv
from collections import Counter
from pathlib import Path

from module2.database.connection import get_connection


def main():
    query = """
        SELECT
            f.id AS faculty_id,
            f.full_name AS faculty_name,
            f.is_active AS faculty_is_active,
            ts.id AS thesis_record_id,
            ts.program_level,
            ts.status,
            ts.student_name,
            ts.research_topic,
            ts.registration_year,
            ts.completion_year,
            ts.source_url,
            ts.details,
            ts.created_at
        FROM m2_faculties AS f
        JOIN m2_thesis_supervision AS ts
          ON ts.faculty_id = f.id
        ORDER BY LOWER(f.full_name), f.id, ts.id
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            columns = [desc.name if hasattr(desc, "name") else desc[0] for desc in cur.description]
            rows = cur.fetchall()

    out_dir = Path("module2") / "exports"
    out_dir.mkdir(parents=True, exist_ok=True)
    data_path = out_dir / "thesis_supervision_all_faculty.csv"
    summary_path = out_dir / "thesis_supervision_faculty_summary.csv"

    with data_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        writer.writerows(rows)

    counts = Counter((row[1], row[0], row[2]) for row in rows)
    with summary_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["faculty_name", "faculty_id", "faculty_is_active", "stored_thesis_record_count"])
        for (faculty_name, faculty_id, active), count in sorted(
            counts.items(), key=lambda item: (str(item[0][0]).lower(), item[0][1])
        ):
            writer.writerow([faculty_name, faculty_id, active, count])

    faculty_count = len({row[0] for row in rows})
    print("THESIS-SUPERVISION EXPORT (READ-ONLY)")
    print(f"Faculty with stored thesis records: {faculty_count}")
    print(f"Total thesis-supervision records exported: {len(rows)}")
    print("\nFiles created:")
    print(f"- {data_path.resolve()}")
    print(f"- {summary_path.resolve()}")
    print("\nOpen the all-faculty CSV in Excel and filter by faculty_name.")
    print("Compare each faculty's rows with their official MNNIT profile's Thesis Supervised section.")
    print("This export contains database records only; it does not claim the database is complete against the profiles.")


if __name__ == "__main__":
    main()

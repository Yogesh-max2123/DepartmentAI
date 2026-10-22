"""
DepartmentAI Module II — READ-ONLY thesis database diagnostic.

Run from the DepartmentAI project root with the project virtual environment active:
    python module2_thesis_db_diagnostic.py

This script only SELECTs data. It does not modify any database records.
"""
import json
from collections import Counter

from module2.database.connection import get_connection


def main():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT current_database(), current_user,
                       inet_server_addr()::text, inet_server_port()
            """)
            print("DATABASE_IDENTITY")
            print(json.dumps(cur.fetchone(), ensure_ascii=False, default=str))

            cur.execute("""
                SELECT COUNT(*)
                FROM m2_faculties
            """)
            print("\nFACULTY_ROW_COUNT:", cur.fetchone()[0])

            cur.execute("""
                SELECT COUNT(*)
                FROM m2_thesis_supervision
            """)
            print("THESIS_ROW_COUNT:", cur.fetchone()[0])

            cur.execute("""
                SELECT COALESCE(program_level, '<NULL>') AS program_level,
                       COALESCE(status, '<NULL>') AS status,
                       COUNT(*) AS records,
                       COUNT(registration_year) AS rows_with_registration_year,
                       COUNT(completion_year) AS rows_with_completion_year
                FROM m2_thesis_supervision
                GROUP BY 1, 2
                ORDER BY 1, 2
            """)
            print("\nPROGRAM_STATUS_YEAR_DISTRIBUTION")
            for row in cur.fetchall():
                print(json.dumps(row, ensure_ascii=False, default=str))

            cur.execute("""
                SELECT f.id, f.full_name, f.profile_url,
                       COUNT(t.id) AS thesis_rows,
                       COUNT(*) FILTER (
                           WHERE lower(COALESCE(t.program_level, '')) LIKE '%ph.d%'
                              OR lower(COALESCE(t.program_level, '')) LIKE '%phd%'
                       ) AS labelled_phd,
                       COUNT(*) FILTER (
                           WHERE lower(COALESCE(t.program_level, '')) LIKE '%m.tech%'
                       ) AS labelled_mtech,
                       COUNT(*) FILTER (
                           WHERE t.registration_year IS NOT NULL
                       ) AS rows_with_registration_year,
                       COUNT(*) FILTER (
                           WHERE t.completion_year IS NOT NULL
                       ) AS rows_with_completion_year,
                       COUNT(*) FILTER (
                           WHERE t.status IS NOT NULL AND btrim(t.status) <> ''
                       ) AS rows_with_status,
                       COUNT(DISTINCT t.source_url) AS source_url_count
                FROM m2_faculties f
                LEFT JOIN m2_thesis_supervision t ON t.faculty_id = f.id
                WHERE lower(f.full_name) LIKE '%rama shankar yadav%'
                   OR lower(f.full_name) LIKE '%r. s. yadav%'
                   OR lower(f.full_name) LIKE '%r.s. yadav%'
                   OR lower(f.full_name) LIKE '%gore%'
                GROUP BY f.id, f.full_name, f.profile_url
                ORDER BY f.id
            """)
            print("\nFOCUS_FACULTY_SUMMARY")
            for row in cur.fetchall():
                print(json.dumps(row, ensure_ascii=False, default=str))

            cur.execute("""
                SELECT f.id, f.full_name, t.id AS thesis_id,
                       t.program_level, t.student_name, t.research_topic,
                       t.registration_year, t.completion_year, t.status,
                       t.details, t.source_url
                FROM m2_thesis_supervision t
                JOIN m2_faculties f ON f.id = t.faculty_id
                WHERE lower(f.full_name) LIKE '%rama shankar yadav%'
                   OR lower(f.full_name) LIKE '%r. s. yadav%'
                   OR lower(f.full_name) LIKE '%r.s. yadav%'
                   OR lower(f.full_name) LIKE '%gore%'
                ORDER BY f.id, t.id
            """)
            rows = cur.fetchall()
            print("\nFOCUS_FACULTY_RAW_ROWS_JSON")
            columns = [
                "faculty_id", "faculty_name", "thesis_id", "program_level",
                "student_name", "research_topic", "registration_year",
                "completion_year", "status", "details", "source_url"
            ]
            print(json.dumps(
                [dict(zip(columns, row)) for row in rows],
                ensure_ascii=False, indent=2, default=str
            ))

            cur.execute("""
                SELECT f.full_name, t.program_level, t.student_name,
                       t.research_topic, t.details, t.source_url, COUNT(*) AS copies
                FROM m2_thesis_supervision t
                JOIN m2_faculties f ON f.id = t.faculty_id
                GROUP BY f.full_name, t.program_level, t.student_name,
                         t.research_topic, t.details, t.source_url
                HAVING COUNT(*) > 1
                ORDER BY copies DESC, f.full_name
                LIMIT 100
            """)
            print("\nEXACT_DUPLICATE_GROUPS_LIMIT_100")
            for row in cur.fetchall():
                print(json.dumps(row, ensure_ascii=False, default=str))

    finally:
        conn.close()


if __name__ == "__main__":
    main()

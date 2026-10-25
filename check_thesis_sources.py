
from module2.database.connection import get_connection

conn = get_connection()

try:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT source_url, COUNT(*)
            FROM m2_thesis_supervision
            WHERE source_url IS NOT NULL
            GROUP BY source_url
            ORDER BY COUNT(*) DESC
            LIMIT 10
        """)

        rows = cur.fetchall()
        print("Source URLs found:", len(rows))

        for row in rows:
            print(row)

finally:
    conn.close()

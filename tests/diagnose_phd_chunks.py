import os
import psycopg2


password = os.environ["DEPARTMENTAI_DB_PASSWORD"]

connection = psycopg2.connect(
    host="localhost",
    port=5432,
    database="departmentai",
    user="postgres",
    password=password
)

cursor = connection.cursor()

query = """
SELECT
    kc.id,
    kc.chunk_index,
    kc.chunk_type,
    kc.clause_number,
    s.section_number,
    s.title AS section_title,
    kc.page_start,
    kc.page_end,
    kc.chunk_text
FROM knowledge_chunks kc
LEFT JOIN sections s
    ON kc.section_id = s.id
WHERE
    kc.chunk_text ILIKE '%minimum SPI%'
    OR kc.chunk_text ILIKE '%Ph.D.%'
    OR kc.chunk_text ILIKE '%thesis%'
ORDER BY kc.id;
"""

cursor.execute(query)

rows = cursor.fetchall()

for row in rows:
    print("\n" + "=" * 80)
    print(f"ID: {row[0]}")
    print(f"Chunk Index: {row[1]}")
    print(f"Type: {row[2]}")
    print(f"Clause: {row[3]}")
    print(f"Section: {row[4]} - {row[5]}")
    print(f"Pages: {row[6]}-{row[7]}")
    print("-" * 80)
    print(row[8])

cursor.close()
connection.close()

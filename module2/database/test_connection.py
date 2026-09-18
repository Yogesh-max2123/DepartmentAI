from module2.database.connection import get_connection


def main():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name LIKE 'm2_%';
            """)

            count = cur.fetchone()[0]

            print(f"Module II tables found: {count}")


if __name__ == "__main__":
    main()
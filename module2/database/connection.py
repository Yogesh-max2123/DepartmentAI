import os

import psycopg
from dotenv import load_dotenv


load_dotenv()


def get_connection():
    """
    Create and return a PostgreSQL connection for Module II.

    Module II uses the existing 'departmentai' database,
    but accesses only its own m2_* tables.
    """
    return psycopg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "departmentai"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
    )
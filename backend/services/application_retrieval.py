from backend.database.connection import get_connection
from backend.retrieval.semantic_search import semantic_search


def retrieve_ordinance_for_application(application_id):
    """
    Retrieve relevant official ordinance clauses for an application.
    """

    conn = get_connection()

    try:
        # --------------------------------------------------------
        # 1. Get application information
        # --------------------------------------------------------
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    application_type,
                    title,
                    description
                FROM applications
                WHERE id = %s;
                """,
                (application_id,),
            )

            application = cursor.fetchone()

        if application is None:
            raise ValueError(
                f"Application with id {application_id} does not exist."
            )

        application_type = application[1]
        title = application[2] or ""
        description = application[3] or ""

        # --------------------------------------------------------
        # 2. Build retrieval query
        # --------------------------------------------------------
        query_parts = [
            application_type,
            title,
            description,
        ]

        query = " ".join(
            part.strip()
            for part in query_parts
            if part and part.strip()
        )

        if not query:
            raise ValueError(
                "Application does not contain enough information "
                "for ordinance retrieval."
            )

        # --------------------------------------------------------
        # 3. Use existing semantic retrieval system
        # --------------------------------------------------------
        results = semantic_search(query)

        return {
            "application_id": application_id,
            "query": query,
            "results": results,
        }

    finally:
        conn.close()
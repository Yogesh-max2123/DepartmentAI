from backend.database.connection import get_connection
from backend.services.knowledge_retrieval_service import retrieve_knowledge


def retrieve_ordinance_for_application(
    application_id,
    programme,
    source_ids=None,
):
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
        if not programme:
            raise ValueError(
                "An approved policy and verified programme are required for "
                "ordinance retrieval."
            )

        retrieval = retrieve_knowledge(
            query,
            programme,
            source_ids=source_ids,
            source_types=["ORDINANCE"],
            application_scoped=True,
        )

        return {
            "application_id": application_id,
            "programme": programme,
            "query": query,
            "status": retrieval["status"],
            "results": retrieval["results"],
        }

    finally:
        conn.close()
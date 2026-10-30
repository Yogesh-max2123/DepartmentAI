from backend.database.connection import get_connection
from backend.services.application_retrieval import retrieve_ordinance_for_application


def extract_application_requirements(application_id, programme):
    """
    Identify and store applicable ordinance requirements
    for an application.

    The requirements are derived from ordinance retrieval results.
    AI does not make a final academic decision.
    """

    retrieved = retrieve_ordinance_for_application(application_id, programme)
    results = retrieved["results"]

    if not results:
        return {
            "application_id": application_id,
            "requirements_created": 0,
            "requirements": [],
        }

    conn = get_connection()

    try:
        requirements = []

        with conn.cursor() as cursor:

            # Remove previously generated requirements so the
            # operation can safely be executed again.
            cursor.execute(
                """
                DELETE FROM application_requirements
                WHERE application_id = %s;
                """,
                (application_id,),
            )

            for result in results:

                chunk_identifier = result["chunk_id"]

                # The original chunk ID is stored inside
                # knowledge_chunks.metadata.
                #
                # knowledge_chunks.id is the actual integer
                # primary key that application_requirements
                # should reference.
                cursor.execute(
                    """
                    SELECT
                        id,
                        section_id
                    FROM knowledge_chunks
                    WHERE metadata->>'chunk_id' = %s;
                    """,
                    (chunk_identifier,),
                )

                chunk = cursor.fetchone()

                if chunk is None:
                    continue

                knowledge_chunk_id = chunk[0]
                section_id = chunk[1]

                cursor.execute(
                    """
                    INSERT INTO application_requirements (
                        application_id,
                        requirement_description,
                        requirement_type,
                        source_section_id,
                        source_chunk_id
                    )
                    VALUES (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s
                    )
                    RETURNING id;
                    """,
                    (
                        application_id,
                        result["chunk_text"],
                        "ORDINANCE",
                        section_id,
                        knowledge_chunk_id,
                    ),
                )

                requirement_id = cursor.fetchone()[0]

                requirements.append(
                    {
                        "requirement_id": requirement_id,
                        "description": result["chunk_text"],
                        "source_chunk_id": knowledge_chunk_id,
                        "source_section_id": section_id,
                    }
                )

        conn.commit()

        return {
            "application_id": application_id,
            "requirements_created": len(requirements),
            "requirements": requirements,
        }

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()
from backend.database.connection import get_connection


def detect_application_deficiencies(application_id):
    """
    Detect potential deficiencies from eligibility analysis.

    NOT_MET requirements are treated as deficiencies.
    UNCLEAR requirements are treated as requiring additional evidence.

    This module does not make the final academic decision.
    """

    conn = get_connection()

    try:
        with conn.cursor() as cursor:

            # Verify application exists
            cursor.execute(
                """
                SELECT id
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

            # Remove previous deficiencies for this application.
            # This prevents duplicate deficiency records when the
            # detection process is run multiple times.
            cursor.execute(
                """
                DELETE FROM deficiencies
                WHERE application_id = %s;
                """,
                (application_id,),
            )

            # Get eligibility results
            cursor.execute(
                """
                SELECT
                    er.id,
                    er.requirement_id,
                    er.result,
                    er.evidence,
                    ar.requirement_description,
                    ar.source_chunk_id
                FROM eligibility_results er
                JOIN application_requirements ar
                    ON er.requirement_id = ar.id
                WHERE er.application_id = %s
                ORDER BY er.id;
                """,
                (application_id,),
            )

            eligibility_results = cursor.fetchall()

            deficiencies = []

            for result in eligibility_results:

                eligibility_result_id = result[0]
                requirement_id = result[1]
                result_status = result[2]
                evidence = result[3]
                requirement_description = result[4]
                source_chunk_id = result[5]

                if result_status == "NOT_MET":
                    severity = "HIGH"
                    description = (
                        "The submitted evidence does not satisfy "
                        "the applicable ordinance requirement."
                    )

                elif result_status == "UNCLEAR":
                    severity = "MEDIUM"
                    description = (
                        "Additional evidence is required to determine "
                        "whether the applicant satisfies the requirement."
                    )

                else:
                    continue

                cursor.execute(
                    """
                    INSERT INTO deficiencies (
                        application_id,
                        requirement_id,
                        description,
                        evidence,
                        severity,
                        status,
                        source_chunk_id
                    )
                    VALUES (
                        %s,
                        %s,
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
                        requirement_id,
                        description,
                        evidence,
                        severity,
                        "OPEN",
                        source_chunk_id,
                    ),
                )

                deficiency_id = cursor.fetchone()[0]

                deficiencies.append(
                    {
                        "deficiency_id": deficiency_id,
                        "requirement_id": requirement_id,
                        "eligibility_result_id": eligibility_result_id,
                        "status": result_status,
                        "severity": severity,
                        "description": description,
                        "evidence": evidence,
                        "source_chunk_id": source_chunk_id,
                    }
                )

        conn.commit()

        return {
            "application_id": application_id,
            "deficiencies_detected": len(deficiencies),
            "deficiencies": deficiencies,
        }

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

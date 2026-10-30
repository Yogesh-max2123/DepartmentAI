import re

from backend.database.connection import get_connection
from backend.llm.gemini_client import generate_answer


def get_stored_eligibility_results(application_id):
    """Return saved advisory results without triggering analysis or writes."""
    conn = get_connection()

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM applications WHERE id = %s;",
                (application_id,),
            )
            application = cursor.fetchone()
            if application is None:
                raise ValueError(
                    f"Application with id {application_id} does not exist."
                )

            cursor.execute(
                """
                SELECT
                    requirement.id,
                    requirement.requirement_description,
                    result.result,
                    result.evidence,
                    result.confidence,
                    result.created_at
                FROM application_requirements AS requirement
                LEFT JOIN LATERAL (
                    SELECT
                        eligibility.result,
                        eligibility.evidence,
                        eligibility.confidence,
                        eligibility.created_at
                    FROM eligibility_results AS eligibility
                    WHERE eligibility.application_id = requirement.application_id
                      AND eligibility.requirement_id = requirement.id
                    ORDER BY eligibility.created_at DESC, eligibility.id DESC
                    LIMIT 1
                ) AS result ON TRUE
                WHERE requirement.application_id = %s
                ORDER BY requirement.id;
                """,
                (application_id,),
            )
            rows = cursor.fetchall()

        results = [
            {
                "requirement_id": row[0],
                "requirement_description": row[1],
                "result": row[2],
                "evidence": row[3],
                "confidence": float(row[4]) if row[4] is not None else None,
                "created_at": row[5],
            }
            for row in rows
            if row[2] is not None
        ]
        requirements_analyzed = len(rows)
        if not results:
            analysis_status = "NOT_GENERATED"
        elif len(results) < requirements_analyzed:
            analysis_status = "PARTIAL"
        else:
            analysis_status = "AVAILABLE"

        return {
            "application_id": application_id,
            "analysis_status": analysis_status,
            "requirements_analyzed": requirements_analyzed,
            "results_count": len(results),
            "results": results,
            "advisory": True,
        }
    finally:
        conn.close()


def analyze_application_eligibility(application_id):
    """
    Analyze application eligibility against extracted ordinance requirements.

    AI provides an eligibility assessment based on the available evidence.
    Final academic decisions must be made by authorized officials/committees.
    """

    conn = get_connection()

    try:
        with conn.cursor() as cursor:

            # Get application
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

            # Get application documents and extracted text
            cursor.execute(
                """
                SELECT
                    ad.id,
                    ad.file_name,
                    ad.document_type,
                    de.extracted_text
                FROM application_documents ad
                LEFT JOIN document_extractions de
                    ON ad.id = de.application_document_id
                WHERE ad.application_id = %s
                ORDER BY ad.id;
                """,
                (application_id,),
            )

            documents = cursor.fetchall()

            # Build document evidence
            document_evidence_parts = []

            for document in documents:
                document_id = document[0]
                file_name = document[1]
                document_type = document[2]
                extracted_text = document[3]

                if extracted_text:
                    document_evidence_parts.append(
                        f"""
Document ID: {document_id}
File Name: {file_name}
Document Type: {document_type or "UNKNOWN"}

Extracted Text:
{extracted_text}
"""
                    )

            if document_evidence_parts:
                document_context = "\n".join(document_evidence_parts)
            else:
                document_context = "No extracted document evidence is available."

            # Get requirements
            cursor.execute(
                """
                SELECT
                    id,
                    requirement_description,
                    requirement_type,
                    source_chunk_id
                FROM application_requirements
                WHERE application_id = %s
                ORDER BY id;
                """,
                (application_id,),
            )

            requirements = cursor.fetchall()

            if not requirements:
                return {
                    "application_id": application_id,
                    "requirements_analyzed": 0,
                    "results": [],
                }

            # Remove previous eligibility results for this application.
            # This makes repeated analysis runs idempotent and prevents
            # duplicate eligibility records.
            cursor.execute(
                """
                DELETE FROM eligibility_results
                WHERE application_id = %s;
                """,
                (application_id,),
            )

            results = []

            # Analyze every requirement
            for requirement in requirements:

                requirement_id = requirement[0]
                requirement_description = requirement[1]
                source_chunk_id = requirement[3]

                question = f"""
Determine whether the submitted application evidence satisfies the
following academic ordinance requirement.

Requirement:
{requirement_description}

Application:
Application Type: {application[1]}
Title: {application[2] or ""}
Description: {application[3] or ""}

Use ONLY the provided document evidence.

Return the result exactly in this format:

RESULT: MET | NOT_MET | UNCLEAR
CONFIDENCE: <number between 0 and 1>
EVIDENCE: <brief explanation>

Rules:
- MET: the available evidence clearly satisfies the requirement.
- NOT_MET: the available evidence clearly shows that the requirement
  is not satisfied.
- UNCLEAR: the available evidence is insufficient to determine whether
  the requirement is satisfied.
- Do not make a final official academic decision.
"""

                try:
                    analysis = generate_answer(
                        question,
                        requirement_description
                        + "\n\n"
                        + document_context,
                    )

                    # Parse result
                    analysis_upper = analysis.upper()

                    if "RESULT: MET" in analysis_upper:
                        result_status = "MET"
                    elif "RESULT: NOT_MET" in analysis_upper:
                        result_status = "NOT_MET"
                    else:
                        result_status = "UNCLEAR"

                    # Parse confidence
                    confidence_match = re.search(
                        r"CONFIDENCE:\s*([01](?:\.\d+)?)",
                        analysis,
                        re.IGNORECASE,
                    )

                    if confidence_match:
                        confidence = float(confidence_match.group(1))
                        confidence = max(
                            0.0,
                            min(1.0, confidence),
                        )
                    else:
                        confidence = 0.0

                    # Parse evidence
                    evidence_match = re.search(
                        r"EVIDENCE:\s*(.*)",
                        analysis,
                        re.IGNORECASE | re.DOTALL,
                    )

                    if evidence_match:
                        evidence = evidence_match.group(1).strip()
                    else:
                        evidence = analysis.strip()

                except Exception as e:
                    # If the LLM request fails, keep the result as UNCLEAR
                    # rather than treating the requirement as satisfied or
                    # not satisfied.
                    result_status = "UNCLEAR"
                    confidence = 0.0
                    evidence = (
                        "Eligibility analysis could not be completed: "
                        f"{str(e)}"
                    )

                # Store eligibility result
                cursor.execute(
                    """
                    INSERT INTO eligibility_results (
                        application_id,
                        requirement_id,
                        result,
                        evidence,
                        confidence,
                        analysis_reference
                    )
                    VALUES (
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
                        result_status,
                        evidence,
                        confidence,
                        f"knowledge_chunk:{source_chunk_id}",
                    ),
                )

                eligibility_result_id = cursor.fetchone()[0]

                results.append(
                    {
                        "eligibility_result_id": eligibility_result_id,
                        "requirement_id": requirement_id,
                        "result": result_status,
                        "evidence": evidence,
                        "confidence": confidence,
                        "source_chunk_id": source_chunk_id,
                    }
                )

        conn.commit()

        return {
            "application_id": application_id,
            "requirements_analyzed": len(results),
            "results": results,
        }

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

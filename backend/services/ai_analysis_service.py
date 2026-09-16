import json

from backend.database.connection import get_connection
from backend.llm.gemini_client import generate_answer


def generate_application_analysis(application_id):
    """
    Generate an AI-assisted analysis of an application.

    The analysis combines:
    - Application information
    - Uploaded document evidence
    - Application requirements
    - Eligibility results
    - Detected deficiencies
    - Relevant ordinance context

    The result is stored in the ai_analyses table.

    IMPORTANT:
    This service provides an AI-assisted analysis/recommendation only.
    It does not make the final academic decision.
    Final approval/rejection must be made by authorized
    officials or committees.
    """

    conn = get_connection()

    try:
        # ---------------------------------------------------------
        # 1. Get application information
        # ---------------------------------------------------------
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    application_number,
                    applicant_identifier,
                    application_type,
                    title,
                    description,
                    status
                FROM applications
                WHERE id = %s
                """,
                (application_id,),
            )

            application_row = cur.fetchone()

        if application_row is None:
            raise ValueError(
                f"Application with id {application_id} does not exist."
            )

        application = {
            "id": application_row[0],
            "application_number": application_row[1],
            "applicant_identifier": application_row[2],
            "application_type": application_row[3],
            "title": application_row[4],
            "description": application_row[5],
            "status": application_row[6],
        }

        # ---------------------------------------------------------
        # 2. Get uploaded documents and latest extraction
        # ---------------------------------------------------------
        #
        # A document can have multiple extraction records because
        # extraction creates a new record each time it runs.
        #
        # We therefore select only the latest extraction for each
        # uploaded document.
        #
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    ad.id,
                    ad.file_name,
                    ad.document_type,
                    ad.upload_status,
                    de.extracted_text,
                    de.extraction_status,
                    de.confidence
                FROM application_documents ad
                LEFT JOIN LATERAL (
                    SELECT
                        extracted_text,
                        extraction_status,
                        confidence
                    FROM document_extractions
                    WHERE application_document_id = ad.id
                    ORDER BY created_at DESC, id DESC
                    LIMIT 1
                ) de ON TRUE
                WHERE ad.application_id = %s
                ORDER BY ad.id
                """,
                (application_id,),
            )

            document_rows = cur.fetchall()

        document_parts = []

        for row in document_rows:
            document_parts.append(
                {
                    "document_id": row[0],
                    "file_name": row[1],
                    "document_type": row[2],
                    "upload_status": row[3],
                    "extracted_text": row[4],
                    "extraction_status": row[5],
                    "confidence": float(row[6]) if row[6] is not None else None,
                }
            )

        # ---------------------------------------------------------
        # 3. Get application requirements
        # ---------------------------------------------------------
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    requirement_description,
                    requirement_type,
                    source_document_id,
                    source_section_id,
                    source_chunk_id,
                    status
                FROM application_requirements
                WHERE application_id = %s
                ORDER BY id
                """,
                (application_id,),
            )

            requirement_rows = cur.fetchall()

        requirement_parts = []

        for row in requirement_rows:
            requirement_parts.append(
                {
                    "requirement_id": row[0],
                    "requirement_description": row[1],
                    "requirement_type": row[2],
                    "source_document_id": row[3],
                    "source_section_id": row[4],
                    "source_chunk_id": row[5],
                    "status": row[6],
                }
            )

        # ---------------------------------------------------------
        # 4. Get eligibility results
        # ---------------------------------------------------------
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    requirement_id,
                    result,
                    evidence,
                    confidence,
                    analysis_reference
                FROM eligibility_results
                WHERE application_id = %s
                ORDER BY id
                """,
                (application_id,),
            )

            eligibility_rows = cur.fetchall()

        eligibility_parts = []

        for row in eligibility_rows:
            eligibility_parts.append(
                {
                    "eligibility_result_id": row[0],
                    "requirement_id": row[1],
                    "result": row[2],
                    "evidence": row[3],
                    "confidence": (
                        float(row[4]) if row[4] is not None else None
                    ),
                    "analysis_reference": row[5],
                }
            )

        # ---------------------------------------------------------
        # 5. Get detected deficiencies
        # ---------------------------------------------------------
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    requirement_id,
                    description,
                    evidence,
                    severity,
                    status,
                    source_chunk_id
                FROM deficiencies
                WHERE application_id = %s
                ORDER BY id
                """,
                (application_id,),
            )

            deficiency_rows = cur.fetchall()

        deficiency_parts = []

        for row in deficiency_rows:
            deficiency_parts.append(
                {
                    "deficiency_id": row[0],
                    "requirement_id": row[1],
                    "description": row[2],
                    "evidence": row[3],
                    "severity": row[4],
                    "status": row[5],
                    "source_chunk_id": row[6],
                }
            )

        # ---------------------------------------------------------
        # 6. Retrieve relevant ordinance context
        # ---------------------------------------------------------
        ordinance_query_parts = [
            application.get("application_type") or "",
            application.get("title") or "",
            application.get("description") or "",
        ]

        ordinance_query = " ".join(
            part.strip()
            for part in ordinance_query_parts
            if part and part.strip()
        )

        from backend.retrieval.semantic_search import semantic_search

        ordinance_results = semantic_search(ordinance_query)

        ordinance_parts = []

        for result in ordinance_results:
            ordinance_parts.append(result)

        # ---------------------------------------------------------
        # 7. Build AI analysis context
        # ---------------------------------------------------------
        application_context = {
            "application": application,
            "documents": document_parts,
            "requirements": requirement_parts,
            "eligibility_results": eligibility_parts,
            "deficiencies": deficiency_parts,
            "ordinance_results": ordinance_parts,
        }

        context_json = json.dumps(
            application_context,
            ensure_ascii=False,
            default=str,
        )

        # ---------------------------------------------------------
        # 8. Generate AI-assisted analysis
        # ---------------------------------------------------------
        prompt = """
Generate an AI-assisted analysis of the application using ONLY
the supplied application context.

Do not use outside knowledge.
Do not invent missing information.
Preserve all numbers, conditions, requirements, exceptions,
and other details exactly as supported by the supplied context.

Organize the response using these sections:

APPLICATION SUMMARY:
DOCUMENT EVIDENCE:
REQUIREMENT ANALYSIS:
ELIGIBILITY ANALYSIS:
DEFICIENCIES:
ORDINANCE BASIS:
AI-ASSISTED RECOMMENDATION:

The AI-assisted recommendation must remain advisory.
Do NOT make the final academic approval or rejection decision.
Final approval or rejection must be made by authorized officials
or the appropriate committee.
"""

        analysis_result = generate_answer(
            prompt,
            context_json,
        )

        # ---------------------------------------------------------
        # 9. Store analysis
        # ---------------------------------------------------------
        analysis_metadata = {
            "analysis": analysis_result,
            "documents_analyzed": len(document_parts),
            "requirements_analyzed": len(requirement_parts),
            "eligibility_results": len(eligibility_parts),
            "deficiencies": len(deficiency_parts),
            "ordinance_results": len(ordinance_parts),
        }

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ai_analyses (
                    application_id,
                    analysis_type,
                    input_reference,
                    analysis_result,
                    recommendation,
                    model
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                RETURNING id, created_at
                """,
                (
                    application_id,
                    "APPLICATION_ANALYSIS",
                    f"application:{application_id}",
                    json.dumps(
                        analysis_metadata,
                        ensure_ascii=False,
                    ),
                    analysis_result,
                    "gemini-3.5-flash-lite",
                ),
            )

            analysis_row = cur.fetchone()

        conn.commit()

        # ---------------------------------------------------------
        # 10. Return analysis result
        # ---------------------------------------------------------
        return {
            "analysis_id": analysis_row[0],
            "application_id": application_id,
            "analysis_type": "APPLICATION_ANALYSIS",
            "documents_analyzed": len(document_parts),
            "requirements_analyzed": len(requirement_parts),
            "eligibility_results": len(eligibility_parts),
            "deficiencies": len(deficiency_parts),
            "ordinance_results": len(ordinance_parts),
            "analysis": analysis_result,
            "model": "gemini-3.5-flash-lite",
            "created_at": analysis_row[1],
        }

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

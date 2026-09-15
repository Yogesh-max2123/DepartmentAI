from backend.database.connection import get_connection
from backend.llm.gemini_client import generate_answer
import re


def analyze_application_eligibility(application_id):
    """
    Analyze an application's eligibility against its stored
    ordinance requirements and submitted document evidence.

    This module provides an AI-assisted analysis only.
    It does NOT make the final academic decision.
    """

    conn = get_connection()

    try:
        with conn.cursor() as cursor:

            # -------------------------------------------------
            # Get application
            # -------------------------------------------------

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

            # -------------------------------------------------
            # Get extracted document text
            # -------------------------------------------------

            cursor.execute(
                """
                SELECT
                    ad.id,
                    ad.file_name,
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

            # -------------------------------------------------
            # Get application requirements
            # -------------------------------------------------

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

        # -----------------------------------------------------
        # Build document evidence
        # -----------------------------------------------------

        document_parts = []

        for document in documents:
            document_id = document[0]
            file_name = document[1]
            extracted_text = document[2] or ""

            if extracted_text.strip():
                document_parts.append(
                    f"""
DOCUMENT ID: {document_id}
FILE NAME: {file_name}

EXTRACTED TEXT:
{extracted_text}
"""
                )

        document_context = "\n".join(document_parts)

        if not document_context.strip():
            document_context = (
                "No extracted text is currently available "
                "from the submitted application documents."
            )

        results = []

        # -----------------------------------------------------
        # Analyze every requirement
        # -----------------------------------------------------

        for requirement in requirements:

            requirement_id = requirement[0]
            requirement_description = requirement[1]
            requirement_type = requirement[2]
            source_chunk_id = requirement[3]

            question = f"""
Analyze the applicant's eligibility for the following
official academic requirement.

APPLICATION TYPE:
{application[1]}

APPLICATION TITLE:
{application[2] or ""}

APPLICATION DESCRIPTION:
{application[3] or ""}

OFFICIAL ORDINANCE REQUIREMENT:
{requirement_description}

SUBMITTED DOCUMENT EVIDENCE:
{document_context}

Determine whether the available evidence shows that the
requirement is:

MET
NOT_MET
UNCLEAR

Rules:
1. Use only the official requirement and submitted document
   evidence provided above.
2. Do not use outside knowledge.
3. Do not invent missing information.
4. If the documents do not provide enough evidence, return
   UNCLEAR.
5. Do not make a final approval or rejection decision.
6. Briefly explain the evidence supporting the result.
7. Preserve important numbers and conditions from the
   ordinance.

Return the result in this exact format:

RESULT: MET | NOT_MET | UNCLEAR
CONFIDENCE: <number between 0 and 1>
EVIDENCE: <brief explanation>
"""

            try:
                analysis = generate_answer(
                    question,
                    requirement_description
                    + "\n\n"
                    + document_context,
                )

                result = "UNCLEAR"
                confidence = 0.0

                analysis_upper = analysis.upper()

                if "RESULT: MET" in analysis_upper:
                    result = "MET"
                elif "RESULT: NOT_MET" in analysis_upper:
                    result = "NOT_MET"

                confidence_match = re.search(
                    r"CONFIDENCE:\s*([01](?:\.\d+)?)",
                    analysis,
                    re.IGNORECASE,
                )

                if confidence_match:
                    confidence = float(confidence_match.group(1))

                    # Safety check: confidence must remain between 0 and 1.
                    confidence = max(0.0, min(1.0, confidence))

                evidence = analysis.strip()

            except Exception as e:
                result = "UNCLEAR"
                confidence = 0.0
                evidence = (
                    f"Eligibility analysis could not be completed: {e}"
                )

            # -------------------------------------------------
            # Store result
            # -------------------------------------------------

            conn = get_connection()

            try:
                with conn.cursor() as cursor:
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
                            %s, %s, %s, %s, %s, %s
                        )
                        RETURNING id;
                        """,
                        (
                            application_id,
                            requirement_id,
                            result,
                            evidence,
                            confidence,
                            f"knowledge_chunk:{source_chunk_id}",
                        ),
                    )

                conn.commit()

            except Exception:
                conn.rollback()
                raise

            finally:
                conn.close()

            results.append(
                {
                    "requirement_id": requirement_id,
                    "requirement_type": requirement_type,
                    "source_chunk_id": source_chunk_id,
                    "result": result,
                    "confidence": confidence,
                    "evidence": evidence,
                }
            )

        return {
            "application_id": application_id,
            "application_type": application[1],
            "title": application[2],
            "results": results,
        }

    finally:
        conn.close()
from backend.database.connection import get_connection
from backend.services.application_service import get_application
from backend.services.application_policy_registry import (
    load_application_policy_registry,
    resolve_application_policy,
)
from backend.services.document_classifier import DocumentNotFoundError, classify_document
from backend.services.document_extractor import extract_document_text
from backend.services.document_validator import validate_document
from backend.services.application_readiness_service import (
    _load_current_snapshot,
)
from backend.services.programme_identity import resolve_programme_identity


class ApplicationProcessingUnavailable(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def process_application_documents(application_id):
    """Validate, classify, and extract supported uploaded documents."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id
                FROM application_documents
                WHERE application_id = %s
                ORDER BY id;
                """,
                (application_id,),
            )
            documents = cursor.fetchall()
    finally:
        conn.close()

    results = []
    for (document_id,) in documents:
        validation = validate_document(document_id)
        if not validation["valid"]:
            results.append(
                {
                    "document_id": document_id,
                    "valid": False,
                    "classification_status": "NOT_RUN",
                    "extraction_status": "NOT_RUN",
                    "reason": validation["reason"],
                }
            )
            continue

        try:
            classification = classify_document(document_id, application_id)
        except DocumentNotFoundError:
            raise
        except ValueError as error:
            results.append(
                {
                    "document_id": document_id,
                    "valid": False,
                    "classification_status": "NOT_RUN",
                    "extraction_status": "NOT_RUN",
                    "reason": str(error),
                }
            )
            continue

        extraction = (
            extract_document_text(document_id, application_id)
            if classification["classification_method"] == "pdf_text"
            else {
                "document_id": document_id,
                "extraction_status": "NOT_SUPPORTED",
                "text_length": 0,
            }
        )
        results.append(
            {
                "document_id": document_id,
                "valid": True,
                "classification_status": classification[
                    "classification_status"
                ],
                "document_type": classification["document_type"],
                "extraction_status": extraction["extraction_status"],
                "text_length": extraction["text_length"],
                "reason": classification["reason"],
            }
        )

    return {
        "application_id": application_id,
        "documents_processed": len(results),
        "documents": results,
    }


def process_application(application_id, identity_provider=None):
    application = get_application(application_id)
    if application is None:
        raise ValueError(
            f"Application with id {application_id} does not exist."
        )
    snapshot = _load_current_snapshot(
        application_id,
        identity_provider=identity_provider,
    )
    identity = snapshot["programme_identity"]
    if identity["status"] != "VERIFIED":
        raise ApplicationProcessingUnavailable(
            "PROGRAMME_IDENTITY_" + identity["status"],
            "Integrated processing is blocked because trusted programme "
            "identity is not verified. No legacy default-programme retrieval "
            "or analysis was run.",
        )

    registry = load_application_policy_registry()
    policy = resolve_application_policy(
        snapshot["application_type"],
        identity["programme"],
        registry,
    )
    if policy["status"] != "RESOLVED":
        raise ApplicationProcessingUnavailable(
            "APPLICATION_POLICY_" + policy["status"],
            "Integrated processing is blocked because no approved "
            "application-type policy is available for this verified "
            "programme. No legacy default-programme retrieval or analysis "
            "was run.",
        )

    raise ApplicationProcessingUnavailable(
        "UNIFIED_PROCESSING_NOT_AVAILABLE",
        "Official-side reprocessing is disabled until the policy-aware "
        "analysis workflow is approved for this application type. The "
        "Official workspace can read the saved Student readiness analysis "
        "and advisory results without regenerating them.",
    )

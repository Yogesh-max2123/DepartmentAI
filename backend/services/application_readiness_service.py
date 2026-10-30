import hashlib
import json
import logging
from pathlib import Path

import psycopg2

from backend.database.connection import get_connection
from backend.services.application_policy_registry import (
    load_application_policy_registry,
    resolve_application_policy,
)
from backend.services.programme_identity import resolve_programme_identity
from backend.services.knowledge_retrieval_service import retrieve_knowledge


LOGGER = logging.getLogger(__name__)
READINESS_ANALYSIS_TYPE = "APPLICATION_READINESS"
READINESS_STATES = {
    "READY",
    "DEFICIENCIES_FOUND",
    "ANALYSIS_PENDING",
    "ANALYSIS_UNAVAILABLE",
    "RULES_UNRESOLVED",
}


class ReadinessAnalysisStateError(ValueError):
    """Raised when readiness analysis is requested outside an editable draft."""


class ReadinessSubmissionError(ValueError):
    def __init__(self, state, message):
        super().__init__(message)
        self.state = state
        self.message = message


def _hash_file(file_path):
    path = Path(file_path)
    if not path.is_file():
        return None

    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _iso_value(value):
    return value.isoformat() if hasattr(value, "isoformat") else value


def _load_current_snapshot(application_id, cursor=None, identity_provider=None):
    owns_connection = cursor is None
    connection = get_connection() if owns_connection else None
    active_cursor = cursor
    if owns_connection:
        active_cursor = connection.cursor()

    try:
        active_cursor.execute(
            """
            SELECT id, applicant_identifier, status, application_type, title,
                   description, updated_at
            FROM applications
            WHERE id = %s;
            """,
            (application_id,),
        )
        application = active_cursor.fetchone()
        if application is None:
            raise LookupError(
                f"Application with id {application_id} does not exist."
            )

        active_cursor.execute(
            """
            SELECT id, file_name, document_type, file_size, mime_type,
                   uploaded_at, file_path
            FROM application_documents
            WHERE application_id = %s
            ORDER BY id;
            """,
            (application_id,),
        )
        document_rows = active_cursor.fetchall()
        documents = []
        integrity_errors = []
        for row in document_rows:
            try:
                file_digest = _hash_file(row[6])
            except OSError:
                LOGGER.warning(
                    "Unable to hash document %s for application %s.",
                    row[0],
                    application_id,
                    exc_info=True,
                )
                file_digest = None
                integrity_errors.append(
                    {
                        "document_id": row[0],
                        "reason": "Document content could not be read.",
                    }
                )
            if file_digest is None:
                integrity_errors.append(
                    {
                        "document_id": row[0],
                        "reason": "Document file is missing or unreadable.",
                    }
                )
            documents.append(
                {
                    "document_id": row[0],
                    "file_name": row[1],
                    "document_type": row[2],
                    "file_size": row[3],
                    "mime_type": row[4],
                    "uploaded_at": _iso_value(row[5]),
                    "content_sha256": file_digest,
                }
            )

        registry = load_application_policy_registry()
        identity = resolve_programme_identity(
            application[1],
            identity_provider,
        )
        identity_data = {
            "status": identity.status,
            "programme": identity.programme,
            "source_id": identity.source_id,
            "source_version": identity.source_version,
        }
        snapshot = {
            "application_id": application[0],
            "applicant_identifier": application[1],
            "status": application[2],
            "application_type": application[3],
            "title": application[4],
            "description": application[5],
            "updated_at": _iso_value(application[6]),
            "documents": documents,
            "policy_registry": registry,
            "programme_identity": identity_data,
        }
        fingerprint_snapshot = {
            "application_id": snapshot["application_id"],
            "applicant_identifier": snapshot["applicant_identifier"],
            "application_type": snapshot["application_type"],
            "title": snapshot["title"],
            "description": snapshot["description"],
            "policy_registry_status": registry["status"],
            "policy_registry_version": registry["registry_version"],
            "policy_registry_fingerprint": registry["fingerprint"],
            "programme_identity": identity_data,
            "documents": [
                {
                    key: document[key]
                    for key in (
                        "document_id",
                        "file_name",
                        "file_size",
                        "mime_type",
                        "uploaded_at",
                        "content_sha256",
                    )
                }
                for document in documents
            ],
        }
        serialized = json.dumps(
            fingerprint_snapshot,
            sort_keys=True,
            separators=(",", ":"),
        )
        snapshot["input_fingerprint"] = hashlib.sha256(
            serialized.encode("utf-8")
        ).hexdigest()
        snapshot["integrity_errors"] = integrity_errors
        return snapshot
    finally:
        if owns_connection:
            active_cursor.close()
            connection.close()


def _read_latest_analysis(cursor, application_id):
    cursor.execute(
        """
        SELECT id, input_reference, analysis_result, created_at
        FROM ai_analyses
        WHERE application_id = %s AND analysis_type = %s
        ORDER BY id DESC
        LIMIT 1;
        """,
        (application_id, READINESS_ANALYSIS_TYPE),
    )
    return cursor.fetchone()


def _decode_analysis(row):
    if row is None:
        return None
    try:
        reference = json.loads(row[1] or "{}")
        result = json.loads(row[2] or "{}")
    except (TypeError, json.JSONDecodeError):
        reference = {}
        result = {
            "readiness_status": "ANALYSIS_UNAVAILABLE",
            "summary": "The stored readiness analysis is unreadable.",
            "deficiencies": None,
            "blocking_conditions": [
                "The saved analysis record could not be interpreted."
            ],
        }
    if not isinstance(reference, dict) or not isinstance(result, dict):
        reference = {}
        result = {
            "readiness_status": "ANALYSIS_UNAVAILABLE",
            "summary": "The stored readiness analysis has an invalid shape.",
            "deficiencies": None,
            "blocking_conditions": [
                "The saved analysis record could not be interpreted."
            ],
        }

    if result.get("readiness_status") not in READINESS_STATES:
        result["readiness_status"] = "ANALYSIS_UNAVAILABLE"
        result["summary"] = "The saved readiness state is invalid."
        result["blocking_conditions"] = [
            "The saved analysis does not contain a recognized readiness state."
        ]
    result["analysis_id"] = row[0]
    result["created_at"] = _iso_value(row[3])
    result["analyzed_input_fingerprint"] = reference.get("input_fingerprint")
    return result


def _persist_analysis(application_id, snapshot, result):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO ai_analyses (
                    application_id,
                    analysis_type,
                    input_reference,
                    analysis_result,
                    recommendation,
                    model
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id, created_at;
                """,
                (
                    application_id,
                    READINESS_ANALYSIS_TYPE,
                    json.dumps(
                        {
                            "input_fingerprint": snapshot[
                                "input_fingerprint"
                            ],
                        },
                        sort_keys=True,
                    ),
                    json.dumps(result, sort_keys=True),
                    result["summary"],
                    "deterministic-readiness-v1",
                ),
            )
            analysis_id, created_at = cursor.fetchone()
        connection.commit()
        result.setdefault(
            "application_version",
            snapshot["input_fingerprint"],
        )
        result["analysis_id"] = analysis_id
        result["created_at"] = _iso_value(created_at)
        result["analyzed_input_fingerprint"] = snapshot["input_fingerprint"]
        result["current_application_version"] = snapshot["input_fingerprint"]
        result["is_stale"] = False
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _resolve_rules(application, registry, identity):
    mapping = resolve_application_policy(
        application.get("application_type"),
        identity.get("programme")
        if identity.get("status") == "VERIFIED"
        else None,
        registry,
    )
    diagnostics = list(mapping["diagnostics"])
    identity_diagnostics = {
        "NOT_CONFIGURED": (
            "PROGRAMME_IDENTITY_NOT_CONFIGURED",
            "A trusted institutional student-programme identity provider "
            "is not configured.",
        ),
        "UNVERIFIED": (
            "PROGRAMME_IDENTITY_UNVERIFIED",
            "The student's programme identity has not been verified by an "
            "authoritative source.",
        ),
        "UNAVAILABLE": (
            "PROGRAMME_IDENTITY_UNAVAILABLE",
            "The authoritative student-programme identity provider is "
            "unavailable.",
        ),
        "CONFLICT": (
            "PROGRAMME_IDENTITY_CONFLICT",
            "The authoritative programme identity contains conflicting or "
            "invalid data.",
        ),
    }
    if identity.get("status") != "VERIFIED":
        code, message = identity_diagnostics.get(
            identity.get("status"),
            identity_diagnostics["NOT_CONFIGURED"],
        )
        diagnostics.append({"code": code, "message": message})
    policy_type = mapping.get("application_type")
    policy = {
        "status": mapping["status"],
        "registry_version": registry.get("registry_version"),
        "registry_fingerprint": registry.get("fingerprint"),
        "application_type_id": (
            policy_type.get("application_type_id") if policy_type else None
        ),
        "approval_status": (
            policy_type.get("approval_status") if policy_type else None
        ),
        "activation_scope": (
            policy_type.get("activation_scope") if policy_type else None
        ),
        "diagnostics": diagnostics,
    }
    if mapping["status"] != "RESOLVED":
        return {
            "policy": policy,
            "rules": {
                "status": "UNRESOLVED",
                "programme": identity.get("programme"),
                "requirements": None,
                "sources": [],
                "retrieval_status": "NOT_RUN",
                "diagnostics": diagnostics,
            },
            "required_documents": None,
            "blocking_conditions": [
                diagnostic["message"] for diagnostic in diagnostics
            ],
        }

    if policy_type["eligibility_rules"]:
        diagnostics.append(
            {
                "code": "ELIGIBILITY_EVALUATOR_NOT_CONFIGURED",
                "message": (
                    "This policy defines eligibility rules, but no approved "
                    "deterministic evaluator is configured. Eligibility is "
                    "not inferred from AI-generated advisory results."
                ),
            }
        )

    source_by_id = {
        source["source_id"]: source
        for source in registry["sources"]
    }
    query = " ".join(
        value
        for value in (
            application.get("application_type") or "",
            application.get("title") or "",
            application.get("description") or "",
            *(
                rule["description"]
                for rule in policy_type["required_documents"]
            ),
            *(
                rule["description"]
                for rule in policy_type["eligibility_rules"]
            ),
        )
        if value.strip()
    )
    try:
        retrieval_response = retrieve_knowledge(
            query,
            policy_type["programme"],
            source_ids=policy_type["source_ids"],
            source_types=["ORDINANCE"],
            limit=5,
            application_scoped=True,
        )
        retrieval_results = retrieval_response["results"]
    except (ImportError, OSError, RuntimeError, ValueError, psycopg2.Error):
        LOGGER.exception(
            "Policy-source retrieval failed for application %s.",
            application["application_id"],
        )
        diagnostics.append(
            {
                "code": "AUTHORITATIVE_RULE_RETRIEVAL_UNAVAILABLE",
                "message": (
                    "The configured authoritative rule source could not be "
                    "retrieved. No checklist or eligibility result was "
                    "inferred."
                ),
            }
        )
        return {
            "policy": {**policy, "status": "UNAVAILABLE", "diagnostics": diagnostics},
            "rules": {
                "status": "UNRESOLVED",
                "programme": policy_type["programme"],
                "requirements": None,
                "sources": [],
                "retrieval_status": "UNAVAILABLE",
                "diagnostics": diagnostics,
            },
            "required_documents": None,
            "blocking_conditions": [
                diagnostic["message"] for diagnostic in diagnostics
            ],
        }

    if not retrieval_results:
        diagnostics.append(
            {
                "code": "AUTHORITATIVE_RULE_SOURCE_NOT_FOUND",
                "message": (
                    "No applicable source chunks were retrieved. An empty "
                    "search result does not mean that no requirements exist."
                ),
            }
        )
        return {
            "policy": {**policy, "status": "UNAVAILABLE", "diagnostics": diagnostics},
            "rules": {
                "status": "UNRESOLVED",
                "programme": policy_type["programme"],
                "requirements": None,
                "sources": [],
                "retrieval_status": "NO_RESULTS",
                "diagnostics": diagnostics,
            },
            "required_documents": None,
            "blocking_conditions": [
                diagnostic["message"] for diagnostic in diagnostics
            ],
        }

    retrieval_evidence, retrieved_source_ids, retrieval_diagnostics = (
        _validate_retrieval_results(
            policy_type,
            source_by_id,
            retrieval_results,
        )
    )
    diagnostics.extend(retrieval_diagnostics)

    if (
        diagnostics
        or retrieved_source_ids != set(policy_type["source_ids"])
        or policy_type["eligibility_rules"]
    ):
        if not diagnostics and retrieved_source_ids != set(policy_type["source_ids"]):
            diagnostics.append(
                {
                    "code": "POLICY_SOURCE_SCOPE_INCOMPLETE",
                    "message": (
                        "The retrieval results did not include every source "
                        "declared by the approved application policy."
                    ),
                }
            )
        if (
            policy_type["eligibility_rules"]
            and not any(
                item["code"] == "ELIGIBILITY_EVALUATOR_NOT_CONFIGURED"
                for item in diagnostics
            )
        ):
            diagnostics.append(
                {
                    "code": "ELIGIBILITY_EVALUATOR_NOT_CONFIGURED",
                    "message": (
                        "Eligibility rules require an approved evaluator "
                        "before readiness can be resolved."
                    ),
                }
            )
        return {
            "policy": {**policy, "status": "UNAVAILABLE", "diagnostics": diagnostics},
            "rules": {
                "status": "UNRESOLVED",
                "programme": policy_type["programme"],
                "requirements": None,
                "sources": [],
                "retrieval_status": "INCOMPLETE",
                "retrieval_evidence": retrieval_evidence,
                "diagnostics": diagnostics,
            },
            "required_documents": None,
            "blocking_conditions": [
                diagnostic["message"] for diagnostic in diagnostics
            ],
        }

    source_details = [
        {
            "source_id": source_id,
            "source_version": source_by_id[source_id]["source_version"],
            "source_file": source_by_id[source_id]["source_file"],
        }
        for source_id in policy_type["source_ids"]
    ]
    required_documents = [
        {
            **rule,
            "source_version": source_by_id[rule["source_id"]]["source_version"],
        }
        for rule in policy_type["required_documents"]
    ]
    return {
        "policy": {**policy, "status": "RESOLVED", "diagnostics": []},
        "rules": {
            "status": "RESOLVED",
            "programme": policy_type["programme"],
            "provenance_verified": True,
            "requirements": required_documents,
            "sources": source_details,
            "retrieval_status": "COMPLETED",
            "retrieval_evidence": retrieval_evidence,
            "diagnostics": [],
        },
        "required_documents": required_documents,
        "blocking_conditions": [],
    }


def _validate_retrieval_results(policy_type, source_by_id, retrieval_results):
    retrieved_source_ids = set()
    retrieved_sections = set()
    retrieval_evidence = []
    diagnostics = []
    for item in retrieval_results:
        if not isinstance(item, dict):
            diagnostics.append(
                {
                    "code": "AUTHORITATIVE_SOURCE_METADATA_INVALID",
                    "message": (
                        "Retrieved source metadata did not match the approved "
                        "policy registry."
                    ),
                }
            )
            continue
        matching_sources = [
            source_id
            for source_id in policy_type["source_ids"]
            if source_by_id[source_id]["source_file"]
            == item.get("source_file")
        ]
        if (
            len(matching_sources) != 1
            or not isinstance(item.get("chunk_id"), str)
            or not item["chunk_id"].strip()
            or not isinstance(item.get("chunk_text"), str)
            or not item["chunk_text"].strip()
            or item.get("source_metadata_status") != "VERIFIED"
            or item.get("source_id") != matching_sources[0]
            or item.get("source_version")
            != source_by_id[matching_sources[0]]["source_version"]
            or item.get("source_sha256")
            != source_by_id[matching_sources[0]]["source_sha256"]
        ):
            diagnostics.append(
                {
                    "code": "AUTHORITATIVE_SOURCE_METADATA_INVALID",
                    "message": (
                        "Retrieved source metadata did not match the approved "
                        "policy registry."
                    ),
                }
            )
            continue
        source_id = matching_sources[0]
        source = source_by_id[source_id]
        retrieved_source_ids.add(source_id)
        section_number = item.get("section_number")
        if isinstance(section_number, str) and section_number.strip():
            retrieved_sections.add((source_id, section_number.strip()))
        retrieval_evidence.append(
            {
                "source_id": source_id,
                "source_version": source["source_version"],
                "source_file": source["source_file"],
                "chunk_id": item["chunk_id"],
                "section_number": section_number,
                "section_title": item.get("section_title"),
                "page_start": item.get("page_start"),
                "page_end": item.get("page_end"),
            }
        )
    expected_sections = {
        (rule.get("source_id"), section_number.strip())
        for rule in (
            policy_type.get("required_documents", [])
            + policy_type.get("eligibility_rules", [])
        )
        if isinstance(rule, dict)
        and isinstance(rule.get("section_numbers"), list)
        for section_number in rule["section_numbers"]
        if isinstance(section_number, str) and section_number.strip()
    }
    for source_id, section_number in sorted(
        expected_sections - retrieved_sections
    ):
        diagnostics.append(
            {
                "code": "AUTHORITATIVE_RULE_SECTION_NOT_RETRIEVED",
                "message": (
                    f"Policy rule citation section {section_number!r} for "
                    f"source {source_id!r} was not present in retrieval "
                    "evidence."
                ),
            }
        )
    return retrieval_evidence, retrieved_source_ids, diagnostics


def analyze_application_readiness(application_id, identity_provider=None):
    """Persist a fail-closed readiness result against the current draft inputs."""
    snapshot_before = _load_current_snapshot(
        application_id,
        identity_provider=identity_provider,
    )
    if snapshot_before["status"] != "DRAFT":
        raise ReadinessAnalysisStateError(
            "Readiness can only be analyzed while the application is a draft."
        )

    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            latest = _decode_analysis(
                _read_latest_analysis(cursor, application_id)
            )
    finally:
        connection.close()
    if (
        latest
        and latest.get("analyzed_input_fingerprint")
        == snapshot_before["input_fingerprint"]
        and latest.get("readiness_status") != "ANALYSIS_UNAVAILABLE"
    ):
        latest["current_application_version"] = snapshot_before[
            "input_fingerprint"
        ]
        latest["is_stale"] = False
        return latest

    try:
        from backend.services.application_processing_service import (
            process_application_documents,
        )

        document_processing = process_application_documents(application_id)
    except Exception:
        LOGGER.exception(
            "Readiness document processing failed for application %s.",
            application_id,
        )
        snapshot = _load_current_snapshot(
            application_id,
            identity_provider=identity_provider,
        )
        unresolved = _resolve_rules(
            snapshot,
            snapshot["policy_registry"],
            snapshot["programme_identity"],
        )
        result = {
            "application_id": application_id,
            "readiness_status": "ANALYSIS_UNAVAILABLE",
            "application": {
                "application_type": snapshot["application_type"],
                "title": snapshot["title"],
            },
            "required_documents": None,
            "document_processing": [],
            "deficiencies": None,
            "deficiency_count": None,
            "blocking_conditions": unresolved["blocking_conditions"] + [
                "Document processing failed. The service logs contain the "
                "diagnostic details.",
            ],
            "rules": unresolved["rules"],
            "policy": unresolved["policy"],
            "programme_identity": snapshot["programme_identity"],
            "summary": (
                "Readiness analysis could not be completed because document "
                "processing failed."
            ),
        }
        return _persist_analysis(application_id, snapshot, result)

    snapshot = _load_current_snapshot(
        application_id,
        identity_provider=identity_provider,
    )
    start_document_ids = sorted(
        item["document_id"] for item in document_processing["documents"]
    )
    final_document_ids = sorted(
        item["document_id"] for item in snapshot["documents"]
    )
    initial_document_content = [
        (
            item["document_id"],
            item["file_name"],
            item["file_size"],
            item["mime_type"],
            item["content_sha256"],
        )
        for item in snapshot_before["documents"]
    ]
    final_document_content = [
        (
            item["document_id"],
            item["file_name"],
            item["file_size"],
            item["mime_type"],
            item["content_sha256"],
        )
        for item in snapshot["documents"]
    ]
    source_unchanged = (
        snapshot_before["status"] == snapshot["status"] == "DRAFT"
        and snapshot_before["input_fingerprint"] == snapshot["input_fingerprint"]
        and start_document_ids == final_document_ids
        and initial_document_content == final_document_content
    )

    resolved = _resolve_rules(
        snapshot,
        snapshot["policy_registry"],
        snapshot["programme_identity"],
    )
    rules = resolved["rules"]
    required_documents = resolved["required_documents"]
    blocking_conditions = list(resolved["blocking_conditions"])
    if not source_unchanged:
        blocking_conditions.insert(
            0,
            "Application fields or uploaded documents changed during analysis.",
        )
    if snapshot["integrity_errors"]:
        blocking_conditions.extend(
            error["reason"] for error in snapshot["integrity_errors"]
        )
    for document in document_processing["documents"]:
        if not document["valid"]:
            blocking_conditions.append(
                f"Document {document['document_id']} could not be processed: "
                f"{document['reason']}"
            )
        elif document["extraction_status"] == "NOT_SUPPORTED":
            blocking_conditions.append(
                f"Document {document['document_id']} could not be text-extracted "
                "with the configured processors."
            )
        elif document["extraction_status"] == "NO_TEXT":
            blocking_conditions.append(
                f"Document {document['document_id']} contains no extractable "
                "text; OCR is not configured."
            )
        elif document["extraction_status"] != "COMPLETED":
            blocking_conditions.append(
                f"Document {document['document_id']} text extraction did not "
                "complete successfully."
            )
        elif document["classification_status"] == "NEEDS_REVIEW":
            blocking_conditions.append(
                f"Document {document['document_id']} could not be classified "
                "unambiguously."
            )

    document_matches = None
    deficiencies = None
    deficiency_count = None
    if required_documents is not None:
        document_matches = []
        deficiencies = []
        processed_documents = document_processing["documents"]
        for requirement in required_documents:
            matched_document = next(
                (
                    document
                    for document in processed_documents
                    if document["valid"]
                    and document["classification_status"] == "CLASSIFIED"
                    and (document.get("document_type") or "").strip().casefold()
                    == requirement["document_type"].strip().casefold()
                ),
                None,
            )
            if matched_document is None:
                deficiencies.append(
                    {
                        "code": "REQUIRED_DOCUMENT_MISSING",
                        "requirement_id": requirement["requirement_id"],
                        "description": requirement["description"],
                        "evidence": requirement["evidence"],
                        "citation": requirement["citation"],
                    }
                )
                continue
            document_matches.append(
                {
                    "requirement_id": requirement["requirement_id"],
                    "document_id": matched_document["document_id"],
                    "status": "MATCHED",
                }
            )
        deficiency_count = len(deficiencies)

    documents_blocked = (
        snapshot["integrity_errors"]
        or any(
            not item["valid"]
            or item["extraction_status"] != "COMPLETED"
            or item["classification_status"] == "NEEDS_REVIEW"
            for item in document_processing["documents"]
        )
    )
    rules_unresolved = rules["status"] != "RESOLVED"
    if rules_unresolved and not blocking_conditions:
        blocking_conditions.append(
            "Applicable authoritative policy rules remain unresolved."
        )

    if documents_blocked or not source_unchanged:
        readiness_status = "ANALYSIS_UNAVAILABLE"
    elif rules_unresolved:
        readiness_status = (
            "ANALYSIS_UNAVAILABLE"
            if resolved["policy"]["status"] == "UNAVAILABLE"
            else "RULES_UNRESOLVED"
        )
    elif deficiencies:
        readiness_status = "DEFICIENCIES_FOUND"
    else:
        readiness_status = "READY"

    result = {
        "application_id": application_id,
        "readiness_status": readiness_status,
        "application": {
            "application_type": snapshot["application_type"],
            "title": snapshot["title"],
        },
        "application_version": snapshot["input_fingerprint"],
        "policy_version": snapshot["policy_registry"]["registry_version"],
        "policy_fingerprint": snapshot["policy_registry"]["fingerprint"],
        "policy": resolved["policy"],
        "programme_identity": snapshot["programme_identity"],
        "document_versions": [
            {
                "document_id": document["document_id"],
                "content_sha256": document["content_sha256"],
            }
            for document in snapshot["documents"]
        ],
        "required_documents": required_documents,
        "document_processing": document_processing["documents"],
        "document_matches": document_matches,
        "deficiencies": deficiencies,
        "deficiency_count": deficiency_count,
        "blocking_conditions": blocking_conditions,
        "rules": rules,
        "summary": _readiness_summary(readiness_status, deficiency_count),
    }
    return _persist_analysis(application_id, snapshot, result)


def _readiness_summary(readiness_status, deficiency_count):
    if readiness_status == "READY":
        return "The current configured document requirements are satisfied."
    if readiness_status == "DEFICIENCIES_FOUND":
        return (
            f"{deficiency_count} required-document deficiency "
            f"{'was' if deficiency_count == 1 else 'were'} identified."
        )
    if readiness_status == "ANALYSIS_UNAVAILABLE":
        return (
            "Readiness could not be established because required policy, "
            "document, or processing evidence is unavailable."
        )
    return (
        "Applicable authoritative rules could not be established. No "
        "required-document checklist or zero-deficiency result was inferred."
    )


def get_application_readiness(application_id, identity_provider=None):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            snapshot = _load_current_snapshot(
                application_id,
                cursor,
                identity_provider,
            )
            row = _read_latest_analysis(cursor, application_id)
    finally:
        connection.close()

    result = _decode_analysis(row)
    if result is None:
        return {
            "application_id": application_id,
            "readiness_status": "ANALYSIS_PENDING",
            "is_stale": True,
            "analysis_id": None,
            "created_at": None,
            "summary": "Readiness analysis has not been run for this draft.",
            "blocking_conditions": [
                "No saved readiness analysis exists for the current inputs."
            ],
        }

    is_stale = (
        result.get("analyzed_input_fingerprint")
        != snapshot["input_fingerprint"]
    )
    result["is_stale"] = is_stale
    result["current_application_version"] = snapshot["input_fingerprint"]
    if is_stale:
        result["previous_readiness_status"] = result["readiness_status"]
        result["readiness_status"] = "ANALYSIS_PENDING"
        result["summary"] = (
            "The saved analysis does not match the current application or "
            "document versions. Readiness must be recalculated."
        )
        result["blocking_conditions"] = [
            "The latest completed analysis is stale for the current inputs."
        ]
    return result


def _has_complete_ready_evidence(result, snapshot):
    policy = result.get("policy")
    identity = result.get("programme_identity")
    current_identity = snapshot["programme_identity"]
    registry = snapshot["policy_registry"]
    if (
        not isinstance(policy, dict)
        or policy.get("status") != "RESOLVED"
        or policy.get("approval_status") != "APPROVED"
        or policy.get("registry_fingerprint") != registry["fingerprint"]
        or policy.get("registry_version") != registry["registry_version"]
        or not isinstance(identity, dict)
        or identity.get("status") != "VERIFIED"
        or identity.get("programme") != current_identity["programme"]
        or identity.get("source_id") != current_identity["source_id"]
        or identity.get("source_version") != current_identity["source_version"]
    ):
        return False

    rules = result.get("rules")
    if (
        not isinstance(rules, dict)
        or rules.get("status") != "RESOLVED"
        or rules.get("retrieval_status") != "COMPLETED"
    ):
        return False
    sources = rules.get("sources")
    if (
        rules.get("provenance_verified") is not True
        or not isinstance(sources, list)
        or not sources
        or any(
            not isinstance(source, dict)
            or not isinstance(source.get("source_id"), str)
            or not source["source_id"].strip()
            or not isinstance(source.get("source_version"), str)
            or not source["source_version"].strip()
            for source in sources
        )
    ):
        return False

    source_ids = {source["source_id"] for source in sources}
    retrieval_evidence = rules.get("retrieval_evidence")
    if (
        not isinstance(retrieval_evidence, list)
        or not retrieval_evidence
        or any(
            not isinstance(item, dict)
            or item.get("source_id") not in source_ids
            or item.get("source_version")
            != next(
                (
                    source["source_version"]
                    for source in sources
                    if source["source_id"] == item.get("source_id")
                ),
                None,
            )
            or not isinstance(item.get("chunk_id"), str)
            or not item["chunk_id"].strip()
            for item in retrieval_evidence
        )
        or {
            item["source_id"] for item in retrieval_evidence
        } != source_ids
    ):
        return False
    requirements = result.get("required_documents")
    if not isinstance(requirements, list):
        return False
    requirement_ids = []
    for requirement in requirements:
        if (
            not isinstance(requirement, dict)
            or not isinstance(requirement.get("requirement_id"), str)
            or not requirement["requirement_id"].strip()
            or not isinstance(requirement.get("source_id"), str)
            or requirement.get("source_id") not in source_ids
            or not isinstance(requirement.get("source_version"), str)
            or not requirement["source_version"].strip()
            or not isinstance(requirement.get("citation"), str)
            or not requirement["citation"].strip()
            or not isinstance(requirement.get("evidence"), str)
            or not requirement["evidence"].strip()
        ):
            return False
        requirement_ids.append(requirement["requirement_id"])
    if len(requirement_ids) != len(set(requirement_ids)):
        return False

    expected_document_ids = {
        document["document_id"] for document in snapshot["documents"]
    }
    document_processing = result.get("document_processing")
    if (
        not isinstance(document_processing, list)
        or len(
            [
                document
                for document in document_processing
                if isinstance(document, dict)
            ]
        )
        != len(document_processing)
    ):
        return False
    processed_document_ids = [
        document.get("document_id") for document in document_processing
    ]
    if (
        any(
            type(document_id) is not int
            for document_id in processed_document_ids
        )
        or len(processed_document_ids) != len(expected_document_ids)
        or set(processed_document_ids) != expected_document_ids
        or any(
            document.get("valid") is not True
            or document.get("classification_status") != "CLASSIFIED"
            or document.get("extraction_status") != "COMPLETED"
            for document in document_processing
        )
    ):
        return False

    matches = result.get("document_matches")
    if not isinstance(matches, list) or len(matches) != len(requirements):
        return False
    matched_requirement_ids = []
    for match in matches:
        if (
            not isinstance(match, dict)
            or not isinstance(match.get("status"), str)
            or match["status"] not in {"MATCHED", "PRESENT", "SATISFIED"}
            or not isinstance(match.get("requirement_id"), str)
            or match.get("requirement_id") not in requirement_ids
            or type(match.get("document_id")) is not int
            or match["document_id"] not in expected_document_ids
        ):
            return False
        matched_requirement_ids.append(match["requirement_id"])
    if (
        len(matched_requirement_ids) != len(set(matched_requirement_ids))
        or set(matched_requirement_ids) != set(requirement_ids)
    ):
        return False

    deficiencies = result.get("deficiencies")
    blocking_conditions = result.get("blocking_conditions")
    return (
        not snapshot["integrity_errors"]
        and isinstance(deficiencies, list)
        and not deficiencies
        and type(result.get("deficiency_count")) is int
        and result["deficiency_count"] == 0
        and isinstance(blocking_conditions, list)
        and not blocking_conditions
    )


def assert_readiness_allows_submission(
    cursor,
    application_id,
    identity_provider=None,
):
    snapshot = _load_current_snapshot(
        application_id,
        cursor,
        identity_provider,
    )
    row = _read_latest_analysis(cursor, application_id)
    result = _decode_analysis(row)
    if result is None:
        raise ReadinessSubmissionError(
            "ANALYSIS_PENDING",
            "Run readiness analysis before submitting this application.",
        )

    try:
        reference = json.loads(row[1] or "{}")
    except (TypeError, json.JSONDecodeError) as error:
        raise ReadinessSubmissionError(
            "ANALYSIS_UNAVAILABLE",
            "The saved readiness input reference is unreadable.",
        ) from error
    if not isinstance(reference, dict):
        raise ReadinessSubmissionError(
            "ANALYSIS_UNAVAILABLE",
            "The saved readiness input reference has an invalid shape.",
        )
    if reference.get("input_fingerprint") != snapshot["input_fingerprint"]:
        raise ReadinessSubmissionError(
            "ANALYSIS_PENDING",
            "The latest readiness analysis is stale. Reanalyze the current "
            "application and documents before submitting.",
        )
    if result["readiness_status"] != "READY":
        raise ReadinessSubmissionError(
            result["readiness_status"],
            result.get("summary")
            or "The latest readiness analysis does not permit submission.",
        )
    if (
        result.get("application_id") != application_id
        or result.get("application_version")
        != snapshot["input_fingerprint"]
        or not _has_complete_ready_evidence(result, snapshot)
    ):
        raise ReadinessSubmissionError(
            "ANALYSIS_UNAVAILABLE",
            "The saved analysis is incomplete or inconsistent with the "
            "application's current state.",
        )
    return result

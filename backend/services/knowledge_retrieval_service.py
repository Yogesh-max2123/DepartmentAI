from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import psycopg2

from backend.academic_programmes import (
    EMBEDDING_DIMENSION,
    EMBEDDING_MODEL,
    normalize_programme,
)
from backend.services.application_policy_registry import (
    load_application_policy_registry,
)
from backend.services.local_demo import LOCAL_DEMO_SOURCE_ID


class KnowledgeRetrievalUnavailable(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


SUPPORTED_DOMAINS = {"ORDINANCE"}
SUPPORTED_SOURCE_TYPES = {"ORDINANCE"}
MAX_RETRIEVAL_LIMIT = 5


def retrieve_knowledge(
    query: str,
    programme: str,
    *,
    source_ids: list[str] | None = None,
    source_types: list[str] | None = None,
    source_version: str | None = None,
    section_numbers: list[str] | None = None,
    limit: int = MAX_RETRIEVAL_LIMIT,
    application_scoped: bool = False,
) -> dict[str, Any]:
    if not isinstance(query, str) or not query.strip():
        raise ValueError("A non-empty knowledge query is required.")
    if len(query) > 2000:
        raise ValueError("Knowledge queries must not exceed 2000 characters.")
    normalized_programme = normalize_programme(programme)
    if not isinstance(limit, int) or isinstance(limit, bool) or not (
        1 <= limit <= MAX_RETRIEVAL_LIMIT
    ):
        raise ValueError(
            f"Retrieval limit must be between 1 and {MAX_RETRIEVAL_LIMIT}."
        )

    requested_types = source_types or ["ORDINANCE"]
    if not requested_types or set(requested_types) - SUPPORTED_SOURCE_TYPES:
        raise ValueError("Only the ORDINANCE source type is supported.")
    if len(set(requested_types)) != len(requested_types):
        raise ValueError("Duplicate source types are not allowed.")
    if section_numbers is not None and any(
        not isinstance(value, str) or not value.strip()
        for value in section_numbers
    ):
        raise ValueError("Section filters must be non-empty strings.")

    registry = load_application_policy_registry()
    if registry["status"] in {"CONFLICT", "UNAVAILABLE"}:
        raise KnowledgeRetrievalUnavailable(
            "SOURCE_REGISTRY_UNAVAILABLE",
            "The verified knowledge-source registry is unavailable.",
        )

    programme_sources = [
        source
        for source in registry["sources"]
        if source.get("programme") == normalized_programme
        and source.get("approval_status") == "APPROVED"
    ]
    if source_ids is not None:
        if not source_ids or len(set(source_ids)) != len(source_ids):
            raise ValueError("Source IDs must be a non-empty unique list.")
        permitted_ids = {source["source_id"] for source in programme_sources}
        if set(source_ids) - permitted_ids:
            raise ValueError(
                "The requested source filter is not approved for this "
                "programme."
            )
        programme_sources = [
            source for source in programme_sources
            if source["source_id"] in set(source_ids)
        ]
    if source_version is not None:
        version_matches = [
            source
            for source in programme_sources
            if source.get("source_version") == source_version
        ]
        if not version_matches:
            raise ValueError(
                "The requested source version is not registered for this "
                "programme."
            )
        programme_sources = [
            source
            for source in programme_sources
            if source.get("source_version") == source_version
        ]
    if not programme_sources:
        raise KnowledgeRetrievalUnavailable(
            "SOURCE_SCOPE_UNRESOLVED",
            "No approved knowledge source matches the requested scope.",
        )

    try:
        from backend.retrieval.semantic_search import semantic_search

        candidates = semantic_search(
            query.strip(),
            programme=normalized_programme,
            source_ids=[source["source_id"] for source in programme_sources],
        )
    except (
        ImportError,
        OSError,
        RuntimeError,
        psycopg2.Error,
    ) as error:
        raise KnowledgeRetrievalUnavailable(
            "RETRIEVAL_UNAVAILABLE",
            "The local knowledge retrieval service is unavailable.",
        ) from error

    source_by_file = {
        source["source_file"]: source for source in programme_sources
    }
    results = []
    for candidate in candidates:
        source = source_by_file.get(candidate.get("source_file"))
        if source is None:
            continue
        section_number = candidate.get("section_number")
        if section_numbers is not None and section_number not in section_numbers:
            continue
        metadata_verified = (
            candidate.get("source_id") == source["source_id"]
            and candidate.get("source_version") == source["source_version"]
            and candidate.get("source_sha256") == source["source_sha256"]
        )
        results.append(
            {
                **candidate,
                "source_title": source.get("title") or source["source_file"],
                "source_type": "ORDINANCE",
                "programme": candidate.get("programme", normalized_programme),
                "registered_source_id": source["source_id"],
                "registered_source_version": source["source_version"],
                "registered_source_sha256": source["source_sha256"],
                "registered_programme": normalized_programme,
                "source_metadata_status": (
                    "VERIFIED" if metadata_verified else "UNVERIFIED"
                ),
                "applicability": (
                    "POLICY_SCOPED"
                    if application_scoped and metadata_verified
                    else "CANDIDATE"
                ),
                "applicability_note": (
                    "Source selected by the approved application policy."
                    if application_scoped and metadata_verified
                    else (
                        "Retrieved source metadata requires verification. "
                        "This result is a candidate and must not be used as "
                        "an applicable policy rule."
                        if not metadata_verified
                        else (
                            "This source is retrieved for the selected "
                            "programme scope only; it is not an application "
                            "eligibility determination."
                        )
                    )
                ),
                "excerpt": candidate.get("chunk_text", ""),
            }
        )

    results = results[:limit]
    return {
        "status": "COMPLETED" if results else "NO_RESULTS",
        "domain": "ORDINANCE",
        "programme": normalized_programme,
        "results": results,
    }


def list_knowledge_sources() -> dict[str, Any]:
    from backend.database.connection import get_connection
    from backend.academic_programmes import get_programme_corpus

    registry = load_application_policy_registry()
    if registry["status"] in {"CONFLICT", "UNAVAILABLE"}:
        raise KnowledgeRetrievalUnavailable(
            "SOURCE_REGISTRY_UNAVAILABLE",
            "The verified knowledge-source registry is unavailable.",
        )

    connection = None
    try:
        connection = get_connection()
        indexed: dict[str, dict[str, Any]] = {}
        with connection.cursor() as cursor:
            for source in registry["sources"]:
                if source["approval_status"] != "APPROVED":
                    indexed[source["source_id"]] = {
                        "status": "PENDING_SOURCE_REVIEW",
                        "chunk_count": 0,
                        "verified_chunk_count": 0,
                        "expected_chunk_count": 0,
                    }
                    continue
                if source["source_id"] == LOCAL_DEMO_SOURCE_ID:
                    manifest_path = (
                        Path(__file__).resolve().parents[2]
                        / ".local-demo"
                        / "sources"
                        / "manifest.json"
                    )
                else:
                    corpus = get_programme_corpus(source["programme"])
                    manifest_path = Path(corpus["chunks"])
                try:
                    chunk_document = json.loads(
                        manifest_path.read_text(encoding="utf-8")
                    )
                    chunk_entries = chunk_document.get("chunks")
                    if not isinstance(chunk_entries, list) or not chunk_entries:
                        raise ValueError("The chunk manifest is empty.")
                    expected_ids = {
                        item["chunk_id"]
                        for item in chunk_entries
                        if isinstance(item, dict)
                        and isinstance(item.get("chunk_id"), str)
                    }
                    if len(expected_ids) != len(chunk_entries):
                        raise ValueError(
                            "The chunk manifest contains invalid or duplicate IDs."
                        )
                except (
                    OSError,
                    KeyError,
                    TypeError,
                    ValueError,
                    json.JSONDecodeError,
                ) as error:
                    raise KnowledgeRetrievalUnavailable(
                        "SOURCE_MANIFEST_UNAVAILABLE",
                        "The registered knowledge-source manifest is unavailable.",
                    ) from error
                cursor.execute(
                    """
                    SELECT metadata->>'chunk_id',
                           metadata->>'source_sha256',
                           metadata->>'source_version',
                           metadata->>'source_id',
                           metadata->>'approval_status',
                           metadata->>'programme',
                           metadata->>'source_file',
                           metadata->>'embedding_model',
                           metadata->>'embedding_dimension'
                    FROM knowledge_chunks kc
                    JOIN documents d ON d.id = kc.document_id
                    WHERE d.file_name = %s;
                    """,
                    (source["source_file"],),
                )
                indexed_rows = cursor.fetchall()
                indexed_ids = {row[0] for row in indexed_rows if row[0]}
                metadata_verified = all(
                    row[1] == source["source_sha256"]
                    and row[2] == source["source_version"]
                    and row[3] == source["source_id"]
                    and row[4] == "APPROVED"
                    and row[5] == source["programme"]
                    and row[6] == source["source_file"]
                    and row[7] == EMBEDDING_MODEL
                    and row[8] == str(EMBEDDING_DIMENSION)
                    for row in indexed_rows
                )
                if (
                    indexed_ids == expected_ids
                    and len(indexed_rows) == len(expected_ids)
                    and metadata_verified
                ):
                    status = "INDEXED"
                elif indexed_rows:
                    status = "STALE_OR_UNVERIFIED"
                else:
                    status = "DISCOVERED"
                indexed[source["source_id"]] = {
                    "status": status,
                    "chunk_count": len(indexed_rows),
                    "verified_chunk_count": sum(
                        1
                        for row in indexed_rows
                        if row[1] == source["source_sha256"]
                        and row[2] == source["source_version"]
                        and row[3] == source["source_id"]
                        and row[4] == "APPROVED"
                        and row[5] == source["programme"]
                        and row[6] == source["source_file"]
                        and row[7] == EMBEDDING_MODEL
                        and row[8] == str(EMBEDDING_DIMENSION)
                    ),
                    "expected_chunk_count": len(expected_ids),
                }
    except psycopg2.Error as error:
        raise KnowledgeRetrievalUnavailable(
            "KNOWLEDGE_INDEX_UNAVAILABLE",
            "The local knowledge index status could not be checked.",
        ) from error
    finally:
        if connection is not None:
            connection.close()

    sources = []
    for source in registry["sources"]:
        status = indexed[source["source_id"]]
        sources.append(
            {
                "source_id": source["source_id"],
                "source_file": source["source_file"],
                "source_type": "ORDINANCE",
                "programme": source["programme"],
                "source_version": source["source_version"],
                "approval_status": source["approval_status"],
                **status,
            }
        )
    return {
        "status": "AVAILABLE",
        "registry_version": registry["registry_version"],
        "sources": sources,
    }

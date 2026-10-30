import json
from types import SimpleNamespace

import pytest

from backend.academic_programmes import PROGRAMME_CORPORA
from backend.services import knowledge_retrieval_service
from backend.services.application_policy_registry import (
    load_application_policy_registry,
)


def _registry(monkeypatch):
    registry = load_application_policy_registry()
    monkeypatch.setattr(
        knowledge_retrieval_service,
        "load_application_policy_registry",
        lambda: registry,
    )
    return registry


def test_retrieval_marks_unverified_results_as_candidates(monkeypatch):
    registry = _registry(monkeypatch)
    source = next(item for item in registry["sources"] if item["programme"] == "UG")
    candidate = {
        "source_file": source["source_file"],
        "source_id": source["source_id"],
        "source_version": source["source_version"],
        "source_sha256": "wrong-hash",
        "section_number": "1.1",
        "chunk_text": "Synthetic ordinance excerpt.",
    }
    monkeypatch.setattr(
        "backend.retrieval.semantic_search.semantic_search",
        lambda *_args, **_kwargs: [candidate],
    )

    result = knowledge_retrieval_service.retrieve_knowledge(
        "synthetic query",
        "UG",
        source_ids=[source["source_id"]],
        application_scoped=True,
    )

    assert result["status"] == "COMPLETED"
    assert result["results"][0]["source_metadata_status"] == "UNVERIFIED"
    assert result["results"][0]["applicability"] == "CANDIDATE"
    assert result["results"][0]["source_sha256"] == "wrong-hash"
    assert result["results"][0]["registered_source_sha256"] == (
        source["source_sha256"]
    )


def test_retrieval_marks_verified_application_scoped_result(monkeypatch):
    registry = _registry(monkeypatch)
    source = next(item for item in registry["sources"] if item["programme"] == "UG")
    monkeypatch.setattr(
        "backend.retrieval.semantic_search.semantic_search",
        lambda *_args, **_kwargs: [
            {
                "source_file": source["source_file"],
                "source_id": source["source_id"],
                "source_version": source["source_version"],
                "source_sha256": source["source_sha256"],
                "programme": "UG",
                "section_number": "1.1",
                "chunk_text": "Synthetic ordinance excerpt.",
            }
        ],
    )

    result = knowledge_retrieval_service.retrieve_knowledge(
        "synthetic query",
        "UG",
        source_ids=[source["source_id"]],
        source_version=source["source_version"],
        application_scoped=True,
    )

    assert result["results"][0]["source_metadata_status"] == "VERIFIED"
    assert result["results"][0]["applicability"] == "POLICY_SCOPED"
    assert result["results"][0]["source_sha256"] == source["source_sha256"]


def test_retrieval_reports_no_results_and_does_not_hide_failures(monkeypatch):
    _registry(monkeypatch)
    monkeypatch.setattr(
        "backend.retrieval.semantic_search.semantic_search",
        lambda *_args, **_kwargs: [],
    )
    result = knowledge_retrieval_service.retrieve_knowledge(
        "synthetic query",
        "UG",
    )
    assert result["status"] == "NO_RESULTS"

    def fail_search(*_args, **_kwargs):
        raise RuntimeError("index unavailable")

    monkeypatch.setattr(
        "backend.retrieval.semantic_search.semantic_search",
        fail_search,
    )
    with pytest.raises(
        knowledge_retrieval_service.KnowledgeRetrievalUnavailable,
        match="local knowledge retrieval service is unavailable",
    ):
        knowledge_retrieval_service.retrieve_knowledge("synthetic query", "UG")


def test_retrieval_rejects_unregistered_scope_filters(monkeypatch):
    _registry(monkeypatch)
    with pytest.raises(ValueError, match="not approved"):
        knowledge_retrieval_service.retrieve_knowledge(
            "synthetic query",
            "UG",
            source_ids=["UNREGISTERED_SOURCE"],
        )
    with pytest.raises(ValueError, match="Only the ORDINANCE"):
        knowledge_retrieval_service.retrieve_knowledge(
            "synthetic query",
            "UG",
            source_types=["MINUTES"],
        )


def test_source_inventory_reports_verified_index_completeness(
    tmp_path,
    monkeypatch,
):
    registry = _registry(monkeypatch)
    sources_by_file = {
        source["source_file"]: source for source in registry["sources"]
    }
    manifest_by_programme = {}
    for programme in PROGRAMME_CORPORA:
        chunk_id = f"synthetic-{programme}-chunk"
        manifest_path = tmp_path / f"{programme}-chunks.json"
        manifest_path.write_text(
            json.dumps({"chunks": [{"chunk_id": chunk_id}]}),
            encoding="utf-8",
        )
        manifest_by_programme[programme] = (manifest_path, chunk_id)
        monkeypatch.setitem(
            PROGRAMME_CORPORA,
            programme,
            {
                **PROGRAMME_CORPORA[programme],
                "chunks": manifest_path,
            },
        )

    ug_source = next(
        source for source in registry["sources"]
        if source["programme"] == "UG"
    )
    mtech_source = next(
        source for source in registry["sources"]
        if source["programme"] == "MTECH"
    )
    ug_manifest, ug_chunk_id = manifest_by_programme["UG"]
    assert ug_manifest.is_file()

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, _query, params):
            self.source_file = params[0]

        def fetchall(self):
            if self.source_file == ug_source["source_file"]:
                return [(
                    ug_chunk_id,
                    ug_source["source_sha256"],
                    ug_source["source_version"],
                    ug_source["source_id"],
                    "APPROVED",
                    "UG",
                    ug_source["source_file"],
                    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
                    "384",
                )]
            if self.source_file == mtech_source["source_file"]:
                return [(
                    manifest_by_programme["MTECH"][1],
                    "stale-source-hash",
                    mtech_source["source_version"],
                    mtech_source["source_id"],
                    "APPROVED",
                    "MTECH",
                    mtech_source["source_file"],
                    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
                    "384",
                )]
            return []

    class FakeConnection:
        def cursor(self):
            return FakeCursor()

        def close(self):
            pass

    monkeypatch.setattr(
        "backend.database.connection.get_connection",
        FakeConnection,
    )
    result = knowledge_retrieval_service.list_knowledge_sources()
    statuses = {source["programme"]: source for source in result["sources"]}

    assert statuses["UG"]["status"] == "INDEXED"
    assert statuses["UG"]["chunk_count"] == 1
    assert statuses["UG"]["expected_chunk_count"] == 1
    assert statuses["MTECH"]["status"] == "STALE_OR_UNVERIFIED"
    assert statuses["PHD"]["status"] == "DISCOVERED"

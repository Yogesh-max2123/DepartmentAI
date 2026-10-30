from types import SimpleNamespace

import pytest

from backend.academic_programmes import (
    EMBEDDING_DIMENSION,
    EMBEDDING_MODEL,
    PROGRAMME_CORPORA,
    get_programme_corpus,
)
from backend.ingest_knowledge_base import (
    build_embedding_lookup,
    connect_database,
    load_json_files,
    verify_registered_source,
)


@pytest.mark.parametrize("programme", tuple(PROGRAMME_CORPORA))
def test_supported_ordinance_assets_match_current_embedding_contract(programme):
    corpus = get_programme_corpus(programme)
    chunks, embeddings, model, dimension = load_json_files(programme)

    assert corpus["pdf"].is_file()
    assert model == EMBEDDING_MODEL
    assert dimension == EMBEDDING_DIMENSION == 384
    assert len(chunks) == len(embeddings)
    assert all(
        chunk["source_file"] == corpus["source_file"]
        for chunk in chunks
    )
    assert len(build_embedding_lookup(embeddings)) == len(chunks)


def test_pg_diploma_has_no_configured_ordinance_corpus():
    with pytest.raises(ValueError, match="Unsupported ordinance programme"):
        get_programme_corpus("PGD")


@pytest.mark.parametrize("programme", tuple(PROGRAMME_CORPORA))
def test_ingestion_requires_the_registered_ordinance_hash(programme, tmp_path):
    corpus = get_programme_corpus(programme)
    source = verify_registered_source(
        programme,
        corpus["source_file"],
        corpus["pdf"],
    )
    assert source["approval_status"] == "APPROVED"
    assert source["source_sha256"]

    modified_pdf = tmp_path / corpus["pdf"].name
    modified_pdf.write_bytes(corpus["pdf"].read_bytes() + b"unapproved change")
    with pytest.raises(ValueError, match="approved registry hash"):
        verify_registered_source(
            programme,
            corpus["source_file"],
            modified_pdf,
        )


def test_ingestion_allows_only_explicit_local_database_profiles(monkeypatch):
    settings = SimpleNamespace(
        environment="test",
        database="departmentai_test",
        user="synthetic-test-user",
        host="127.0.0.1",
        port=5432,
        password="test-only",
    )
    calls = []
    monkeypatch.setattr(
        "backend.ingest_knowledge_base.get_database_settings",
        lambda: settings,
    )
    monkeypatch.setattr(
        "backend.ingest_knowledge_base.psycopg2.connect",
        lambda **kwargs: calls.append(kwargs) or "test-connection",
    )
    assert connect_database() == "test-connection"
    assert calls[0]["dbname"] == "departmentai_test"
    assert calls[0]["host"] == "127.0.0.1"

    settings.environment = "institutional"
    with pytest.raises(RuntimeError, match="loopback development or test"):
        connect_database()
    assert len(calls) == 1

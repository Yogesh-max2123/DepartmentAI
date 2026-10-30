import importlib

import pytest
from pydantic import ValidationError

from backend.api.routes import AskRequest


def test_assistant_retrieves_only_selected_programme_corpus(monkeypatch):
    pipeline = importlib.import_module("backend.rag.qa_pipeline")
    retrieval_calls = []
    generated_contexts = []

    monkeypatch.setattr(
        pipeline,
        "validate_question",
        lambda _question: {"allowed": True, "reason": ""},
    )
    monkeypatch.setattr(
        pipeline,
        "expand_ordinance_query",
        lambda question: question,
    )
    monkeypatch.setattr(
        pipeline,
        "retrieve_knowledge",
        lambda question, programme, **filters: (
            retrieval_calls.append((question, programme, filters))
            or {
                "status": "COMPLETED",
                "results": [
                    {
                        "section_number": "1",
                        "section_title": "Introduction",
                        "clause_number": "1.1",
                        "page_start": 1,
                        "page_end": 2,
                        "source_file": (
                            "Ordinances for Masters Programme 2023.pdf"
                        ),
                        "chunk_text": "Masters ordinance test clause.",
                    }
                ],
            }
        ),
    )
    monkeypatch.setattr(
        pipeline,
        "generate_answer",
        lambda _question, context: (
            generated_contexts.append(context) or "Grounded test response."
        ),
    )

    answer, results = pipeline.answer_question(
        "What does the ordinance say about registration?",
        programme="MTECH",
    )

    assert answer == "Grounded test response."
    assert results[0]["source_file"] == (
        "Ordinances for Masters Programme 2023.pdf"
    )
    assert retrieval_calls == [
        (
            "What does the ordinance say about registration?",
            "MTECH",
            {"source_types": ["ORDINANCE"]},
        )
    ]
    assert "Source: Ordinances for Masters Programme 2023.pdf" in (
        generated_contexts[0]
    )


def test_assistant_rejects_unconfigured_programme_before_retrieval(monkeypatch):
    pipeline = importlib.import_module("backend.rag.qa_pipeline")
    retrieval_called = False

    def fail_if_retrieved(*_args, **_kwargs):
        nonlocal retrieval_called
        retrieval_called = True
        raise AssertionError("Retrieval must not run for an unsupported track.")

    monkeypatch.setattr(pipeline, "retrieve_knowledge", fail_if_retrieved)

    with pytest.raises(ValueError, match="Unsupported ordinance programme"):
        pipeline.answer_question(
            "What are the application rules?",
            programme="PGD",
        )
    assert retrieval_called is False


@pytest.mark.parametrize("programme", ("UG", "MTECH", "PHD"))
def test_ask_request_accepts_supported_ordinance_scopes(programme):
    request = AskRequest(
        question="What does the ordinance say about registration?",
        programme=programme,
    )

    assert request.programme == programme


def test_ask_request_rejects_pg_diploma_scope():
    with pytest.raises(ValidationError):
        AskRequest(
            question="What are the PG Diploma rules?",
            programme="PGD",
        )

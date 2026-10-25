"""Tests Gemini prompt grounding and source-link instructions without making API calls."""

from types import SimpleNamespace
import json

from module2.retrieval import faculty_gemini


class _FakeModels:
    def __init__(self, response_text="Dr. Test Faculty supervises 2 ongoing Ph.D. students.\nSource: https://mnnit.ac.in/profile/test"):
        self.response_text = response_text
        self.last_call = None

    def generate_content(self, **kwargs):
        self.last_call = kwargs
        return SimpleNamespace(text=self.response_text)


class _FakeClient:
    def __init__(self, models):
        self.models = models


def test_gemini_receives_original_question_and_database_evidence(monkeypatch):
    fake_models = _FakeModels()
    monkeypatch.setattr(faculty_gemini, "_get_client", lambda: _FakeClient(fake_models))

    question = "How many ongoing PhD students does Dr. Test Faculty supervise?"
    evidence = [
        {
            "type": "authoritative_database_thesis_analytics",
            "database_result": "Ongoing Ph.D. students: 2",
            "source_urls": ["https://mnnit.ac.in/profile/test"],
        }
    ]

    answer = faculty_gemini.generate_faculty_answer(
        question, evidence, faculty_name="Dr. Test Faculty"
    )

    prompt = fake_models.last_call["contents"]
    assert question in prompt
    assert "authoritative_database_thesis_analytics" in prompt
    assert "https://mnnit.ac.in/profile/test" in prompt
    assert "Do not fabricate citations or URLs" in prompt
    assert "only the information requested" in prompt
    assert "2 ongoing Ph.D. students" in answer


def test_gemini_does_not_call_api_for_empty_evidence(monkeypatch):
    def should_not_be_called():
        raise AssertionError("Gemini API should not be called when evidence is empty")

    monkeypatch.setattr(faculty_gemini, "_get_client", should_not_be_called)
    answer = faculty_gemini.generate_faculty_answer(
        "What are the qualifications of Dr. Test Faculty?", []
    )
    assert "couldn't retrieve sufficient evidence" in answer


def test_gemini_rejects_empty_question():
    import pytest

    with pytest.raises(ValueError, match="Question cannot be empty"):
        faculty_gemini.generate_faculty_answer("   ", [{"content": "irrelevant"}])

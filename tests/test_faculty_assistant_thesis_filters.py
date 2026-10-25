"""Regression tests for Module II thesis programme-aware retrieval."""
import pytest

from module2.retrieval.faculty_assistant import (
    _thesis_scope_sql,
    asks_thesis_classification,
    asks_thesis_count,
    asks_thesis_list,
    requested_thesis_programme,
)


@pytest.mark.parametrize("question", [
    "How many completed Ph.D. students has Professor X supervised?",
    "List doctoral students supervised by Professor X",
    "Show PhD students",
])
def test_explicit_phd_request_uses_phd_programme_filter(question):
    assert requested_thesis_programme(question) == "Ph.D."
    conditions, _ = _thesis_scope_sql(faculty_id=7, phd_only=True)
    assert any("ts.program_level" in condition and "'phd'" in condition for condition in conditions)


@pytest.mark.parametrize("question", [
    "List the M.Tech students supervised by Professor X",
    "How many M.Tech students has Professor X supervised?",
    "Show M Tech students",
])
def test_mtech_request_uses_mtech_programme_filter(question):
    assert requested_thesis_programme(question) == "M.Tech"
    assert asks_thesis_list(question) or asks_thesis_count(question)
    conditions, _ = _thesis_scope_sql(faculty_id=7, program_level="M.Tech")
    assert any("ts.program_level" in condition and "'mtech'" in condition for condition in conditions)


def test_generic_thesis_question_does_not_invent_programme():
    assert requested_thesis_programme("List thesis-supervision records for Professor X") is None
    conditions, _ = _thesis_scope_sql(faculty_id=7)
    assert not any("ts.program_level" in condition for condition in conditions)


def test_unclassified_question_is_recognized_as_diagnostic():
    assert asks_thesis_classification("How many thesis-supervision records are still unclassified?")

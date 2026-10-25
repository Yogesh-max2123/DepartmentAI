"""Regression tests for Module II department-wide analytics routing."""
import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "module2" / "retrieval" / "faculty_assistant.py"


def load_assistant_isolated():
    """Load the target source with import stubs without polluting project modules."""
    module2 = types.ModuleType("module2")
    module2.__path__ = [str(ROOT / "module2")]

    database = types.ModuleType("module2.database")
    database.__path__ = []
    connection = types.ModuleType("module2.database.connection")
    connection.get_connection = lambda: None

    retrieval = types.ModuleType("module2.retrieval")
    retrieval.__path__ = [str(ROOT / "module2" / "retrieval")]
    search = types.ModuleType("module2.retrieval.faculty_search")
    search.TOP_K = 8
    search.detect_requested_sections = lambda question: []
    search.display_results = lambda *args, **kwargs: None
    search.ensure_corpus_loaded = lambda: None
    search.faculty_search = lambda *args, **kwargs: []
    search.resolve_faculty = lambda *args, **kwargs: (set(), None, "none")

    gemini = types.ModuleType("module2.retrieval.faculty_gemini")
    gemini.generate_faculty_answer = lambda *args, **kwargs: "test answer"

    modules = {
        "module2": module2,
        "module2.database": database,
        "module2.database.connection": connection,
        "module2.retrieval": retrieval,
        "module2.retrieval.faculty_search": search,
        "module2.retrieval.faculty_gemini": gemini,
    }
    name = "module2.retrieval.faculty_assistant"
    with patch.dict(sys.modules, modules):
        spec = importlib.util.spec_from_file_location(name, SOURCE)
        assistant = importlib.util.module_from_spec(spec)
        sys.modules[name] = assistant
        spec.loader.exec_module(assistant)
    return assistant


@pytest.mark.parametrize("question", [
    "Give me the total number of faculties under CSED of MNNIT.",
    "How many faculty members are in CSED?",
    "What is the number of professors in the department?",
    "Count the faculty.",
])
def test_department_faculty_count_intent(question):
    assistant = load_assistant_isolated()
    assert assistant.asks_faculty_count(question)


@pytest.mark.parametrize("question", [
    "Give me the count of total publications published under CSED between 2000 and 2020.",
    "How many papers did CSED faculty publish?",
    "How many thesis records are there?",
])
def test_non_faculty_entity_count_is_not_faculty_count(question):
    assistant = load_assistant_isolated()
    assert not assistant.asks_faculty_count(question)




def test_faculty_count_question_passes_csed_scope_guard():
    assistant = load_assistant_isolated()
    question = "Give me the total number of faculties under CSED of MNNIT."
    assert assistant.is_csed_faculty_related_question(question)


def test_publication_count_intent_remains_supported():
    assistant = load_assistant_isolated()
    question = "Give me the count of total publications under CSED between 2000 and 2020."
    assert assistant.asks_publication_count(question)


def test_faculty_count_routes_to_database_analytics(monkeypatch, capsys):
    assistant = load_assistant_isolated()
    monkeypatch.setattr(
        assistant, "faculty_count",
        lambda: {"active_faculty": 42, "total_records": 45, "inactive_records": 3},
    )
    handled = assistant.run_analytics(
        "Give me the total number of faculties under CSED of MNNIT.",
        department_wide=True,
    )
    output = capsys.readouterr().out
    assert handled is True
    assert "42" in output
    assert "45 total" in output
    assert "not a fresh live count" in output


def test_department_publication_count_routes_with_inclusive_year_range(monkeypatch, capsys):
    assistant = load_assistant_isolated()
    captured = {}

    def fake_publication_count(**kwargs):
        captured.update(kwargs)
        return {
            "unique_publications": 123,
            "faculty_publication_associations": 158,
            "publications_without_known_year": 7,
        }

    monkeypatch.setattr(assistant, "publication_count", fake_publication_count)
    handled = assistant.run_analytics(
        "Give me the count of total publications published under CSED of MNNIT between 2000 and 2020.",
        department_wide=True,
    )
    output = capsys.readouterr().out
    assert handled is True
    assert captured["year_range"] == (2000, 2020)
    assert captured["faculty_id"] is None
    assert captured["faculty_ids"] is None
    assert "123 unique publication records" in output
    assert "158" in output


def test_faculty_count_executes_database_count_sql(monkeypatch):
    assistant = load_assistant_isolated()

    class Cursor:
        def __init__(self):
            self.sql = None

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, sql, params=None):
            self.sql = sql

        def fetchone(self):
            return (42, 45, 3)

    class Connection:
        def __init__(self):
            self.cursor_instance = Cursor()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def cursor(self):
            return self.cursor_instance

    connection = Connection()
    monkeypatch.setattr(assistant, "get_connection", lambda: connection)
    result = assistant.faculty_count()
    assert result == {
        "active_faculty": 42,
        "total_records": 45,
        "inactive_records": 3,
    }
    assert "FROM m2_faculties" in connection.cursor_instance.sql
    assert "is_active IS DISTINCT FROM FALSE" in connection.cursor_instance.sql

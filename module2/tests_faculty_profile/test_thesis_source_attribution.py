"""Tests for thesis count/list source attribution without connecting to PostgreSQL."""

from contextlib import redirect_stdout
from io import StringIO

import pytest

from module2.retrieval import faculty_assistant as assistant


def _fake_counts(**kwargs):
    return {
        "total_records": 5,
        "unique_students": 5,
        "completed_records": 2,
        "completed_students": 2,
        "ongoing_records": 2,
        "ongoing_students": 2,
        "status_unspecified_records": 1,
        "status_unspecified_students": 1,
        "records_without_registration_year": 1,
        "records_without_completion_year": 3,
    }


def test_thesis_count_prints_database_recorded_source_urls(monkeypatch):
    source_urls = [
        "https://mnnit.ac.in/profile/preview.php?login=faculty-test",
        "https://mnnit.ac.in/userprofile/pdf/uploads/faculty-test-cv.pdf",
    ]
    monkeypatch.setattr(assistant, "thesis_counts", _fake_counts)
    monkeypatch.setattr(assistant, "fetch_thesis_source_urls", lambda **kwargs: source_urls)

    output = StringIO()
    with redirect_stdout(output):
        handled = assistant.run_thesis_analytics(
            "How many ongoing PhD students does Dr. Test Faculty supervise?",
            faculty_id=17,
            faculty_name="Dr. Test Faculty",
        )

    text = output.getvalue()
    assert handled is True
    assert "Official source URL(s) recorded in the database:" in text
    for url in source_urls:
        assert url in text


def test_thesis_count_reports_missing_source_url_without_inventing_one(monkeypatch):
    monkeypatch.setattr(assistant, "thesis_counts", _fake_counts)
    monkeypatch.setattr(assistant, "fetch_thesis_source_urls", lambda **kwargs: [])

    output = StringIO()
    with redirect_stdout(output):
        assistant.run_thesis_analytics(
            "How many ongoing PhD students does Dr. Test Faculty supervise?",
            faculty_id=17,
            faculty_name="Dr. Test Faculty",
        )

    text = output.getvalue()
    assert "No source URL is recorded for this scope in the database." in text
    assert "https://mnnit.ac.in/" not in text


def test_thesis_list_prints_record_source_url(monkeypatch):
    source_url = "https://mnnit.ac.in/profile/preview.php?login=faculty-test"
    monkeypatch.setattr(
        assistant,
        "fetch_thesis_rows",
        lambda **kwargs: [
            {
                "student_name": "Student Example",
                "research_topic": "Example research topic",
                "program_level": "Ph.D.",
                "registration_year": 2022,
                "completion_year": None,
                "status": "Ongoing",
                "details": None,
                "source_url": source_url,
            }
        ],
    )

    output = StringIO()
    with redirect_stdout(output):
        handled = assistant.run_thesis_analytics(
            "List PhD students supervised by Dr. Test Faculty",
            faculty_id=17,
            faculty_name="Dr. Test Faculty",
        )

    text = output.getvalue()
    assert handled is True
    assert "Student Example" in text
    assert "Example research topic" in text
    assert source_url in text


def test_explicit_programme_is_forwarded_to_source_lookup(monkeypatch):
    monkeypatch.setattr(assistant, "thesis_counts", _fake_counts)
    captured = {}

    def fake_sources(**kwargs):
        captured.update(kwargs)
        return ["https://mnnit.ac.in/profile/test"]

    monkeypatch.setattr(assistant, "fetch_thesis_source_urls", fake_sources)
    with redirect_stdout(StringIO()):
        assistant.run_thesis_analytics(
            "How many completed PhD students does Dr. Test Faculty supervise?",
            faculty_id=17,
            faculty_name="Dr. Test Faculty",
        )

    assert captured["faculty_id"] == 17
    assert captured["program_level"] == "Ph.D."
    assert captured["phd_only"] is True

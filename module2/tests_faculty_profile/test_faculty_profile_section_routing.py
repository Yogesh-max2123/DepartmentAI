"""Regression tests for the five faculty-profile information areas and section routing."""

import pytest

from module2.retrieval.faculty_search import detect_requested_sections
from module2.retrieval.faculty_assistant import (
    is_csed_faculty_related_question,
    asks_publication_count,
    asks_latest_publications,
    asks_publication_list,
    asks_thesis_count,
    asks_thesis_list,
    requested_thesis_programme,
)


@pytest.mark.parametrize(
    ("question", "expected_section"),
    [
        ("What is Dr. Abhimanyu Sahu's designation and official profile?", "basic_information"),
        ("What are Dr. Abhimanyu Sahu's educational qualifications?", "education"),
        ("What are his research interests?", "research_areas"),
        ("What are his latest five research publications?", "publications"),
        ("How many ongoing PhD students does he supervise?", "thesis_supervision"),
        ("What academic achievements and awards are listed?", "achievements"),
    ],
)
def test_question_routes_to_expected_profile_section(question, expected_section):
    assert expected_section in detect_requested_sections(question)


@pytest.mark.parametrize(
    "question",
    [
        "What is Dr. Abhimanyu Sahu's designation?",
        "What are his educational qualifications?",
        "What are his research interests?",
        "What are his latest research publications?",
        "How many ongoing PhD students does he supervise?",
        "What academic achievements and awards are listed?",
        "What research projects are listed?",
    ],
)
def test_faculty_profile_questions_are_recognized_as_in_scope(question):
    assert is_csed_faculty_related_question(question)


def test_publication_question_intents_are_distinguished():
    assert asks_publication_count("How many publications does Dr. Sahu have?")
    assert asks_latest_publications("What are his latest five research publications?")
    assert asks_publication_list("List the research publications of Dr. Sahu.")
    assert not asks_publication_count("List the research publications of Dr. Sahu.")


def test_thesis_question_intents_and_programme_filters():
    assert asks_thesis_count("How many ongoing PhD students does Dr. Sahu supervise?")
    assert asks_thesis_list("List the M.Tech students supervised by Dr. Sahu.")
    assert requested_thesis_programme("How many PhD students?") == "Ph.D."
    assert requested_thesis_programme("List M.Tech students") == "M.Tech"


def test_unrelated_question_is_not_mistaken_for_faculty_question():
    assert not is_csed_faculty_related_question("How do I bake a chocolate cake?")

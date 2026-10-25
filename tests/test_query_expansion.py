from backend.rag.query_expansion import expand_ordinance_query


def test_academic_probation_uses_ordinance_term():
    expanded = expand_ordinance_query(
        "What does the ordinance say about academic probation?"
    )

    assert "academic deficiency ACD" in expanded
    assert "academic probation" not in expanded.lower()


def test_degree_extension_uses_programme_duration_terms():
    expanded = expand_ordinance_query(
        "What are the requirements to apply for a degree extension?"
    )

    assert "maximum permissible duration" in expanded


def test_paces_of_study_uses_semester_load_terms():
    expanded = expand_ordinance_query(
        "What are the normal and slow paces of study?"
    )

    assert "semester load requirements" in expanded
    assert "normal pace" in expanded
    assert "slow pace" in expanded


def test_unmatched_query_is_unchanged():
    question = "How are SPI and CPI calculated?"

    assert expand_ordinance_query(question) == question

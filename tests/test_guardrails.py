from backend.rag.guardrails import validate_question


def test_valid_academic_question():
    result = validate_question(
        "What are the requirements for a B.Tech Honours degree?"
    )

    assert result["allowed"] is True
    assert result["reason"] == ""


def test_valid_follow_up_question():
    result = validate_question(
        "What is the CPI requirement?"
    )

    assert result["allowed"] is True
    assert result["reason"] == ""


def test_valid_broad_academic_question():
    result = validate_question(
        "What are the rules for registration?"
    )

    assert result["allowed"] is True
    assert result["reason"] == ""


def test_valid_admission_question():
    result = validate_question(
        "What documents are required for admission?"
    )

    assert result["allowed"] is True
    assert result["reason"] == ""


def test_valid_deficiency_question():
    result = validate_question(
        "What happens if a student has a deficiency?"
    )

    assert result["allowed"] is True
    assert result["reason"] == ""


def test_valid_pace_of_study_question():
    result = validate_question(
        "What are the normal and slow paces of study?"
    )

    assert result["allowed"] is True
    assert result["reason"] == ""


def test_official_decision_request():
    result = validate_question(
        "Should my application be approved?"
    )

    assert result["allowed"] is False
    assert "final academic approval" in result["reason"]


def test_out_of_scope_question():
    result = validate_question(
        "Tell me a joke"
    )

    assert result["allowed"] is False
    assert "outside the academic ordinance scope" in result["reason"]


def test_weather_question():
    result = validate_question(
        "What is the weather today?"
    )

    assert result["allowed"] is False
    assert "outside the academic ordinance scope" in result["reason"]


def test_empty_question():
    result = validate_question("")

    assert result["allowed"] is False
    assert result["reason"] == "Please enter a question."


def test_whitespace_question():
    result = validate_question("   ")

    assert result["allowed"] is False
    assert result["reason"] == "Please enter a question."


if __name__ == "__main__":
    print("Running guardrail tests...")

    test_valid_academic_question()
    test_valid_follow_up_question()
    test_valid_broad_academic_question()
    test_valid_admission_question()
    test_valid_deficiency_question()
    test_valid_pace_of_study_question()
    test_official_decision_request()
    test_out_of_scope_question()
    test_weather_question()
    test_empty_question()
    test_whitespace_question()

    print("All guardrail tests passed.")
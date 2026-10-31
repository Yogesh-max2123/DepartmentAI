import re

from backend.retrieval.semantic_search import retrieve_for_recommendation
from backend.llm.gemini_client import generate_answer
from backend.rag.conversation_manager import resolve_follow_up
from backend.rag.guardrails import validate_question
from backend.rag.programme import normalize_programme
from backend.rag.source_formatter import build_context


_STUDENT_LEAK_PATTERNS = (
    r"(?im)^\s*\*?\*?relevant ordinance clauses\*?\*?\s*$",
    r"(?im)^\s*\*?\*?similar previous cases[^\n]*$",
    r"(?im)^\s*\*?\*?identified deficiencies\*?\*?\s*$",
    r"(?im)^\s*\*?\*?possible course of action\*?\*?\s*$",
    r"(?im)^\s*\*?\*?initial draft resolution\*?\*?\s*$",
    r"(?i)\bsynthetic\b",
    r"(?i)\bcase[_ ]?id\b",
    r"(?i)\bminute[_ ]?id\b",
    r"(?i)\bcircular[_ ]?id\b",
    r"(?i)\bchunk[_ ]?id\b",
    r"(?i)\bpast cases?\b",
    r"(?i)\bmeeting minutes?\b",
    r"(?i)\boffice order\b",
)


def _sanitize_student_answer(answer: str) -> str:
    if not answer:
        return answer
    text = answer.strip()
    for pattern in _STUDENT_LEAK_PATTERNS:
        if re.search(pattern, text):
            lines = []
            for line in text.splitlines():
                if re.search(
                    r"(?i)(relevant ordinance|similar previous|identified deficienc|"
                    r"possible course|initial draft|synthetic|case id|minute id|"
                    r"circular id|chunk id|past case|meeting minute|office order|"
                    r"clause\s+\d|form\s+(dp|mp|bp|gl)-)",
                    line,
                ):
                    continue
                lines.append(line)
            text = "\n".join(lines).strip()
            break
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text or (
        "I can help with the ordinance in plain language. "
        "Please rephrase your question, or speak with a departmental official."
    )


def answer_question(question, conversation_history=None, role=None, programme=None):
    # Role ko ekdum top par resolve kar lo taki guardrail check me use ho sake
    role_key = (role or "OFFICIAL").strip().upper()

    # ---------------------------------------------------------
    # 1. Basic question validation
    # ---------------------------------------------------------
    if not question or not question.strip():
        return (
            "Please enter a question.",
            []
        )

    # ---------------------------------------------------------
    # 2. Validate ORIGINAL user question BEFORE
    #    conversation resolution.
    #
    #    This guarantees irrelevant questions such as
    #    "Tell me a joke" or "How are you?" are blocked
    #    without entering conversation resolution or RAG.
    # ---------------------------------------------------------
    if role_key != "OFFICIAL":
        guardrail_result = validate_question(question)

        if not guardrail_result["allowed"]:
            return (
                guardrail_result["reason"],
                []
            )

    if conversation_history is None:
        conversation_history = []

    # ---------------------------------------------------------
    # 3. Resolve follow-up question if conversation exists
    # ---------------------------------------------------------
    if conversation_history:
        search_query = resolve_follow_up(
            question,
            conversation_history,
            programme=programme,
        )
    else:
        search_query = question

    # ---------------------------------------------------------
    # 4. Validate resolved standalone question
    # ---------------------------------------------------------
    if role_key != "OFFICIAL":
        guardrail_result = validate_question(search_query)

        if not guardrail_result["allowed"]:
            return (
                guardrail_result["reason"],
                []
            )

    # ---------------------------------------------------------
    # 5. Mixed retrieval for the Recommendation Agent
    # ---------------------------------------------------------
    programme_key = normalize_programme(programme)
    results = retrieve_for_recommendation(
        search_query,
        programme=programme_key,
        include_synthetic=(role_key != "STUDENT"),
    )

    # ---------------------------------------------------------
    # 6. Context construction across ordinance + synthetic sources
    # ---------------------------------------------------------
    if role_key == "STUDENT":
        student_results = [
            item
            for item in results
            if (item.get("chunk_type") or "ordinance_clause")
            in ("ordinance_clause", "form")
        ]
        ordinance_context = build_context(student_results or results)
    else:
        student_results = results
        ordinance_context = build_context(results)

    # ---------------------------------------------------------
    # 7. Recommendation Agent draft generation
    # ---------------------------------------------------------
    answer = generate_answer(
        search_query,
        ordinance_context,
        role=role,
        programme=programme_key,
    )

    if role_key == "STUDENT":
        answer = _sanitize_student_answer(answer)
        return answer, []

    return answer, results
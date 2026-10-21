from backend.retrieval.semantic_search import retrieve_for_recommendation
from backend.llm.gemini_client import generate_answer
from backend.rag.conversation_manager import resolve_follow_up
from backend.rag.guardrails import validate_question
from backend.rag.source_formatter import build_context


def answer_question(question, conversation_history=None):

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
            conversation_history
        )
    else:
        search_query = question

    # ---------------------------------------------------------
    # 4. Validate resolved standalone question
    # ---------------------------------------------------------
    guardrail_result = validate_question(search_query)

    if not guardrail_result["allowed"]:
        return (
            guardrail_result["reason"],
            []
        )

    # ---------------------------------------------------------
    # 5. Mixed retrieval for the Recommendation Agent
    # ---------------------------------------------------------
    results = retrieve_for_recommendation(search_query)

    # ---------------------------------------------------------
    # 6. Context construction across ordinance + synthetic sources
    # ---------------------------------------------------------
    ordinance_context = build_context(results)

    # ---------------------------------------------------------
    # 7. Recommendation Agent draft generation
    # ---------------------------------------------------------
    answer = generate_answer(
        search_query,
        ordinance_context
    )

    return answer, results

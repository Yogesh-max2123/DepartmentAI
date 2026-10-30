from backend.llm.gemini_client import generate_answer
from backend.rag.conversation_manager import resolve_follow_up
from backend.rag.guardrails import validate_question
from backend.rag.query_expansion import expand_ordinance_query
from backend.academic_programmes import get_programme_corpus
from backend.services.knowledge_retrieval_service import retrieve_knowledge


def build_context(results, source_file=""):
    context_parts = []

    for result in results:
        context_parts.append(
            f"""
Section {result.get('section_number')}: {result.get('section_title')}
Clause: {result.get('clause_number')}
Pages: {result.get('page_start')}-{result.get('page_end')}
Source: {source_file or result.get('source_file', '')}

{result.get('chunk_text')}
"""
        )

    return "\n---\n".join(context_parts)


def answer_question(question, conversation_history=None, programme="UG"):

    # ---------------------------------------------------------
    # 1. Basic question validation
    # ---------------------------------------------------------
    if not question or not question.strip():
        return (
            "Please enter a question.",
            []
        )

    corpus = get_programme_corpus(programme)

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
    # 5. EXISTING RAG RETRIEVAL — unchanged
    # ---------------------------------------------------------
    retrieval_query = expand_ordinance_query(search_query)
    retrieval = retrieve_knowledge(
        retrieval_query,
        programme,
        source_types=["ORDINANCE"],
    )
    results = retrieval["results"]
    if not results:
        return (
            "No relevant source passages were found in the selected "
            "ordinance corpus.",
            [],
        )

    # ---------------------------------------------------------
    # 6. EXISTING ordinance context construction — unchanged
    # ---------------------------------------------------------
    ordinance_context = build_context(
        results,
        source_file=str(corpus["source_file"]),
    )

    # ---------------------------------------------------------
    # 7. EXISTING Gemini answer generation — unchanged
    # ---------------------------------------------------------
    answer = generate_answer(
        search_query,
        ordinance_context
    )

    return answer, results

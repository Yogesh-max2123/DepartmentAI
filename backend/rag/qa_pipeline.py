from backend.retrieval.semantic_search import semantic_search
from backend.llm.gemini_client import generate_answer
from backend.rag.conversation_manager import resolve_follow_up


def build_context(results):
    context_parts = []

    for result in results:
        context_parts.append(
            f"""
Section {result.get('section_number')}: {result.get('section_title')}
Clause: {result.get('clause_number')}
Pages: {result.get('page_start')}-{result.get('page_end')}

{result.get('chunk_text')}
"""
        )

    return "\n---\n".join(context_parts)


def answer_question(question, conversation_history=None):

    if not question or not question.strip():
        raise ValueError("Question cannot be empty.")

    if conversation_history is None:
        conversation_history = []

    # Resolve only the current follow-up question.
    if conversation_history:
        search_query = resolve_follow_up(
            question,
            conversation_history
        )
    else:
        search_query = question

    # EXISTING RAG RETRIEVAL — unchanged.
    results = semantic_search(search_query)

    # EXISTING ordinance context construction — unchanged.
    ordinance_context = build_context(results)

    # IMPORTANT:
    # Only the resolved standalone question and official ordinance
    # context are sent to the final answer generator.
    #
    # Conversation history is NOT included here.
    answer = generate_answer(
        search_query,
        ordinance_context
    )

    return answer, results
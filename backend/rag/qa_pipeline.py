from backend.retrieval.semantic_search import semantic_search
from backend.llm.gemini_client import generate_answer


def build_context(results):
    """
    Convert retrieved ordinance chunks into context
    that can be provided to the LLM.
    """

    if not results:
        return ""

    context_parts = []

    for i, result in enumerate(results, start=1):

        section_number = result.get("section_number") or "N/A"
        section_title = result.get("section_title") or "N/A"
        clause_number = result.get("clause_number") or "N/A"
        page_start = result.get("page_start") or "N/A"
        page_end = result.get("page_end") or "N/A"
        chunk_text = result.get("chunk_text") or ""

        context_parts.append(
            f"[Context {i}]\n"
            f"Section: {section_number} - {section_title}\n"
            f"Clause: {clause_number}\n"
            f"Pages: {page_start}-{page_end}\n"
            f"Text:\n{chunk_text}"
        )

    return "\n\n".join(context_parts)


def answer_question(question):
    """
    Complete RAG pipeline:

    Question
       ↓
    Semantic + keyword retrieval
       ↓
    Top 5 chunks
       ↓
    Context construction
       ↓
    Gemini
       ↓
    Answer
    """

    if not question.strip():
        raise ValueError("Question cannot be empty.")

    # Step 1: Retrieve relevant ordinance chunks
    results = semantic_search(question)

    # Step 2: Build LLM context
    context = build_context(results)

    # Step 3: Generate grounded answer
    answer = generate_answer(
        question=question,
        context=context
    )

    return answer, results
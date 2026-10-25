import re
from collections import Counter

import psycopg2
from sentence_transformers import SentenceTransformer

from backend.database.connection import get_database_settings

# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

MODEL_NAME = (
    "sentence-transformers/"
    "paraphrase-multilingual-MiniLM-L12-v2"
)

# Number of candidates retrieved from pgvector
# before lexical reranking.
CANDIDATE_K = 50

# Number of final results returned.
TOP_K = 5

def get_db_connection():
    """Return a fresh PostgreSQL connection for each retrieval request."""
    settings = get_database_settings()
    return psycopg2.connect(**settings.connection_kwargs())



# ---------------------------------------------------------
# Load embedding model ONCE
# ---------------------------------------------------------

print("Loading embedding model...")

model = SentenceTransformer(
    MODEL_NAME,
    local_files_only=True
)

print("Embedding model loaded.")
print(
    f"Embedding dimension: "
    f"{model.get_embedding_dimension()}"
)



# ---------------------------------------------------------
# Text Processing
# ---------------------------------------------------------

def tokenize(text: str):
    """
    Convert text into normalized tokens.

    Example:
        "B.Tech. Degree requirements"

    becomes approximately:

        ["b", "tech", "degree", "requirements"]
    """

    if not text:
        return []

    text = text.lower()

    return re.findall(
        r"[a-z0-9]+",
        text
    )


# ---------------------------------------------------------
# Keyword / Lexical Scoring
# ---------------------------------------------------------

def calculate_keyword_score(
    question: str,
    chunk_text: str,
    section_title: str = "",
    clause_title: str = "",
):
    """
    Calculate lexical relevance between the question
    and retrieved chunk.

    Improvements:
    - Considers section title.
    - Removes common question words.
    - Rewards query-term coverage.
    - Rewards exact two-word phrase matches.
    - Applies a small penalty when a generic question
      is matched by strongly branch-specific content.
    """

    question_tokens = tokenize(question)
    chunk_tokens = tokenize(chunk_text)
    section_tokens = tokenize(f"{section_title} {clause_title}")

    if not question_tokens or not chunk_tokens:
        return 0.0

    # -----------------------------------------------------
    # Stop words
    # -----------------------------------------------------

    stop_words = {
        "what",
        "are",
        "is",
        "the",
        "a",
        "an",
        "of",
        "for",
        "to",
        "in",
        "on",
        "and",
        "or",
        "how",
        "does",
        "do",
        "can",
        "be",
        "under",
        "with",
        "from",
        "about",
        "regarding",
        "regard",
        "student",
        "students"
    }

    meaningful_question_tokens = [
        token
        for token in question_tokens
        if token not in stop_words
    ]

    if not meaningful_question_tokens:
        return 0.0

    # -----------------------------------------------------
    # Sets for efficient matching
    # -----------------------------------------------------

    question_set = set(
        meaningful_question_tokens
    )

    chunk_set = set(
        chunk_tokens
    )

    section_set = set(
        section_tokens
    )

    # -----------------------------------------------------
    # Query-term coverage
    # -----------------------------------------------------

    matched_terms = 0

    for token in question_set:

        if (
            token in chunk_set
            or token in section_set
        ):
            matched_terms += 1

    coverage_score = (
        matched_terms /
        len(question_set)
    )

    # -----------------------------------------------------
    # Exact phrase bonus
    # -----------------------------------------------------

    normalized_chunk = " ".join(
        chunk_tokens
    )

    normalized_section = " ".join(
        section_tokens
    )

    phrase_bonus = 0.0

    for i in range(
        len(meaningful_question_tokens) - 1
    ):

        phrase = (
            meaningful_question_tokens[i]
            + " "
            + meaningful_question_tokens[i + 1]
        )

        if (
            phrase in normalized_chunk
            or phrase in normalized_section
        ):
            phrase_bonus += 0.10

    # Do not allow phrase bonuses to dominate
    # the lexical score.
    phrase_bonus = min(
        phrase_bonus,
        0.30
    )

    score = (
        coverage_score
        + phrase_bonus
    )

    # -----------------------------------------------------
    # Generic-vs-specific penalty
    # -----------------------------------------------------
    #
    # If the user asks a generic question such as:
    #
    # "What are the requirements for a B.Tech degree?"
    #
    # a chunk containing only branch-specific information
    # such as ECE should receive a small penalty when the
    # branch was not mentioned in the question.
    #
    # This penalty is intentionally small.
    # -----------------------------------------------------

    branch_terms = {
        "ece",
        "cse",
        "biotechnology",
        "chemical",
        "civil",
        "electrical",
        "mechanical",
        "production",
        "industrial"
    }

    question_all_tokens = set(
        question_tokens
    )

    unspecified_branch_terms = (
        branch_terms
        - question_all_tokens
    )

    branch_matches = (
        unspecified_branch_terms
        & chunk_set
    )

    if branch_matches:
        score -= 0.10

    return max(
        0.0,
        min(1.0, score)
    )


# ---------------------------------------------------------
# Semantic Search
# ---------------------------------------------------------

def semantic_search(question: str):
    """
    Hybrid retrieval:

    1. Generate question embedding.
    2. Retrieve CANDIDATE_K semantically similar chunks.
    3. Calculate lexical relevance.
    4. Combine semantic + lexical scores.
    5. Return the highest-ranked TOP_K results.
    """

    if not question.strip():
        raise ValueError(
            "Question cannot be empty."
        )

    # -----------------------------------------------------
    # Generate question embedding
    # -----------------------------------------------------

    query_embedding = model.encode(
        question,
        normalize_embeddings=True
    )

    embedding_string = "[" + ",".join(
        str(float(value))
        for value in query_embedding
    ) + "]"

    # -----------------------------------------------------
    # Retrieve semantic candidates
    # -----------------------------------------------------

    conn = get_db_connection()
    cursor = conn.cursor()

    try:

        query = """
        SELECT
            kc.metadata->>'chunk_id' AS chunk_id,
            kc.chunk_index,
            kc.chunk_type,
            kc.clause_number,
            kc.chunk_text,
            kc.page_start,
            kc.page_end,
            s.section_number,
            s.title AS section_title,
            kc.metadata->>'source_file' AS source_file,
            kc.metadata->>'clause_title' AS clause_title,
            1 - (kc.embedding <=> %s::vector)
                AS similarity

        FROM knowledge_chunks kc

        LEFT JOIN sections s
            ON kc.section_id = s.id

        WHERE kc.embedding IS NOT NULL

        ORDER BY kc.embedding <=> %s::vector

        LIMIT %s;
        """

        cursor.execute(
            query,
            (
                embedding_string,
                embedding_string,
                CANDIDATE_K
            )
        )

        candidates = cursor.fetchall()

    finally:

        cursor.close()
        conn.close()

    if not candidates:
        return []

    # -----------------------------------------------------
    # Rerank candidates
    # -----------------------------------------------------

    reranked_results = []

    for result in candidates:

        (
            chunk_id,
            chunk_index,
            chunk_type,
            clause_number,
            chunk_text,
            page_start,
            page_end,
            section_number,
            section_title,
            source_file,
            clause_title,
            semantic_score
        ) = result

        keyword_score = (
            calculate_keyword_score(
                question,
                chunk_text,
                section_title,
                clause_title or "",
            )
        )
        title_score = calculate_keyword_score(
            question,
            clause_title or "",
        )

        # -------------------------------------------------
        # Combined relevance score
        # -------------------------------------------------
        #
        # Semantic similarity remains dominant.
        #
        # Semantic relevance, body-term overlap, and exact clause-title match.
        # -------------------------------------------------

        combined_score = (
            0.65 * float(semantic_score)
            +
            0.20 * float(keyword_score)
            +
            0.15 * float(title_score)
        )

        reranked_results.append(
            {
                "chunk_id": chunk_id,
                "chunk_index": chunk_index,
                "chunk_type": chunk_type,
                "clause_number": clause_number,
                "chunk_text": chunk_text,
                "page_start": page_start,
                "page_end": page_end,
                "section_number": section_number,
                "section_title": section_title,
                "source_file": source_file,
                "clause_title": clause_title,
                "semantic_score": float(
                    semantic_score
                ),
                "keyword_score": float(
                    keyword_score
                ),
                "combined_score": float(
                    combined_score
                )
            }
        )

    # -----------------------------------------------------
    # Sort by combined relevance
    # -----------------------------------------------------

    reranked_results.sort(
        key=lambda x: x["combined_score"],
        reverse=True
    )

    return reranked_results[:TOP_K]


# ---------------------------------------------------------
# Display Search Result
# ---------------------------------------------------------

def display_result(results):
    """
    Display all final retrieved results.
    """

    if not results:
        print(
            "\nNo relevant information found."
        )
        return

    print(
        "\n"
        + "=" * 70
    )

    print(
        f"TOP {len(results)} RETRIEVED RESULTS"
    )

    print(
        "=" * 70
    )

    for index, result in enumerate(
        results,
        start=1
    ):

        print()
        print(
            f"[{index}] "
            f"Chunk ID: {result['chunk_id']}"
        )

        print(
            f"Section: "
            f"{result['section_number']} - "
            f"{result['section_title']}"
        )

        print(
            f"Clause: "
            f"{result['clause_number']}"
        )

        print(
            f"Pages: "
            f"{result['page_start']}-"
            f"{result['page_end']}"
        )

        print(
            f"Semantic similarity: "
            f"{result['semantic_score']:.4f}"
        )

        print(
            f"Keyword relevance: "
            f"{result['keyword_score']:.4f}"
        )

        print(
            f"Combined relevance: "
            f"{result['combined_score']:.4f}"
        )

        print(
            "\nRetrieved Text:"
        )

        print(
            "-" * 70
        )

        print(
            result["chunk_text"]
        )

        print(
            "-" * 70
        )


# ---------------------------------------------------------
# Main Interactive Loop
# ---------------------------------------------------------

def main():

    print(
        "\n"
        + "=" * 70
    )

    print(
        "DepartmentAI Semantic Retrieval"
    )

    print(
        "=" * 70
    )

    print(
        "\nEmbedding model loaded once."
        "\nPostgreSQL connection established once."
        f"\nSemantic candidates: Top {CANDIDATE_K}"
        f"\nFinal results: Top {TOP_K}"
    )

    print(
        "\nAsk multiple questions without "
        "reloading the model or reconnecting."
        "\nType 'exit' or 'quit' to stop.\n"
    )

    try:

        while True:

            question = input(
                "Question: "
            ).strip()

            if not question:
                continue

            if question.lower() in {
                "exit",
                "quit"
            }:
                break

            try:

                results = semantic_search(
                    question
                )

                display_result(
                    results
                )

            except Exception as e:

                print(
                    "\nError while performing "
                    f"semantic search: {e}"
                )

    finally:

        print(
            "DepartmentAI semantic retrieval stopped."
        )


# ---------------------------------------------------------
# Program Entry Point
# ---------------------------------------------------------

if __name__ == "__main__":
    main()

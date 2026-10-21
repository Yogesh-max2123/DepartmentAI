import os
import re
from collections import Counter

import psycopg2
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

load_dotenv()

MODEL_NAME = (
    "sentence-transformers/"
    "paraphrase-multilingual-MiniLM-L12-v2"
)

# UPGRADE 1: Increased candidate pool from 50 to 100 for better recall
CANDIDATE_K = 100

# UPGRADE 2: Increased final results from 5 to 8 to give LLM broader context
TOP_K = 8

DB_HOST = os.getenv("DEPARTMENTAI_DB_HOST", "localhost")
DB_PORT = int(os.getenv("DEPARTMENTAI_DB_PORT", 5432))
DB_NAME = os.getenv("DEPARTMENTAI_DB_NAME", "departmentai")
DB_USER = os.getenv("DEPARTMENTAI_DB_USER", "postgres")

DB_PASSWORD = os.getenv(
    "DEPARTMENTAI_DB_PASSWORD"
)


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
# Create PostgreSQL connection ONCE
# ---------------------------------------------------------

if not DB_PASSWORD:
    raise RuntimeError(
        "DEPARTMENTAI_DB_PASSWORD "
        "environment variable is not set."
    )

print("Connecting to PostgreSQL...")

conn = psycopg2.connect(
    host=DB_HOST,
    port=DB_PORT,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)

print("Database connection established.")


# ---------------------------------------------------------
# Text Processing
# ---------------------------------------------------------

def tokenize(text: str):
    """
    Convert text into normalized tokens.

    Example:
        "M.Tech. Degree requirements"

    becomes approximately:

        ["m", "tech", "degree", "requirements"]
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
    section_title: str = ""
):
    """
    Calculate lexical relevance between the question
    and retrieved chunk.

    Improvements:
    - Considers section title.
    - Removes common question words AND generic academic words.
    - Rewards query-term coverage.
    - Rewards exact two-word phrase matches.
    - Applies a small penalty when a generic question
      is matched by strongly programme-specific content.
    """

    question_tokens = tokenize(question)
    chunk_tokens = tokenize(chunk_text)
    section_tokens = tokenize(section_title)

    if not question_tokens or not chunk_tokens:
        return 0.0

    # -----------------------------------------------------
    # Stop words (UPGRADE 3: Added more generic academic words)
    # -----------------------------------------------------

    stop_words = {
        "what", "are", "is", "the", "a", "an", "of", "for", "to",
        "in", "on", "and", "or", "how", "does", "do", "can", "be",
        "under", "with", "from", "about", "regarding", "regard",
        "student", "students", "programme", "program", "semester",
        "year", "course", "institute", "department"
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
            phrase_bonus += 0.15  # Slightly increased bonus for exact phrase match

    # Do not allow phrase bonuses to dominate
    # the lexical score.
    phrase_bonus = min(
        phrase_bonus,
        0.35
    )

    score = (
        coverage_score
        + phrase_bonus
    )

    # -----------------------------------------------------
    # Generic-vs-specific penalty
    # -----------------------------------------------------

    programme_terms = {
        "m.tech", "mtech", "mba", "mca", "m.sc", "msc", "msw"
    }

    question_all_tokens = set(
        question_tokens
    )

    unspecified_programme_terms = (
        programme_terms
        - question_all_tokens
    )

    programme_matches = (
        unspecified_programme_terms
        & chunk_set
    )

    if programme_matches:
        score -= 0.10

    return max(
        0.0,
        min(1.0, score)
    )


# ---------------------------------------------------------
# Semantic Search
# ---------------------------------------------------------

def semantic_search(
    question: str,
    top_k: int = TOP_K,
    candidate_k: int = CANDIDATE_K,
    chunk_types=None,
):
    """
    Hybrid retrieval:

    1. Generate question embedding.
    2. Retrieve candidate_k semantically similar chunks.
    3. Optionally restrict by chunk_type (ordinance, past_case, etc.).
    4. Calculate lexical relevance.
    5. Combine semantic + lexical scores.
    6. Return the highest-ranked top_k results.
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

    cursor = conn.cursor()

    try:

        type_filter = ""
        params = [embedding_string]

        if chunk_types:
            type_filter = "AND kc.chunk_type = ANY(%s)"
            params.append(list(chunk_types))

        params.extend([embedding_string, candidate_k])

        query = f"""
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
            kc.metadata->>'subject' AS subject,
            kc.metadata->>'source_file' AS source_file,
            kc.metadata->>'document' AS document_title,
            1 - (kc.embedding <=> %s::vector)
                AS similarity

        FROM knowledge_chunks kc

        LEFT JOIN sections s
            ON kc.section_id = s.id

        WHERE kc.embedding IS NOT NULL
        {type_filter}

        ORDER BY kc.embedding <=> %s::vector

        LIMIT %s;
        """

        cursor.execute(query, tuple(params))

        candidates = cursor.fetchall()

    finally:

        # Cursor is temporary.
        # Database connection remains open.
        cursor.close()

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
            subject,
            source_file,
            document_title,
            semantic_score
        ) = result

        keyword_score = (
            calculate_keyword_score(
                question,
                chunk_text,
                section_title
            )
        )

        # -------------------------------------------------
        # Combined relevance score (UPGRADE 4: Re-balanced)
        # -------------------------------------------------
        #
        # Increased Keyword importance to 30% so exact matching
        # words like "part-time" or "F grade" aren't lost.
        #
        # 70% semantic
        # 30% lexical
        # -------------------------------------------------

        combined_score = (
            0.70 * float(semantic_score)
            +
            0.30 * float(keyword_score)
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
                "subject": subject,
                "source_file": source_file,
                "document_title": document_title,
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

    return reranked_results[:top_k]


# ---------------------------------------------------------
# Recommendation-agent retrieval
# ---------------------------------------------------------

ORDINANCE_CHUNK_TYPES = (
    "ordinance_clause",
    "form",
)

PAST_CASE_CHUNK_TYPES = (
    "past_case",
)

MINUTE_CHUNK_TYPES = (
    "meeting_minute",
)

CIRCULAR_CHUNK_TYPES = (
    "circular",
)


def retrieve_for_recommendation(question: str):
    """
    Retrieve a mixed evidence set for the Recommendation Agent:

    ordinance clauses, similar previous cases, DMPC minutes,
    and office orders / circulars.
    """

    groups = [
        semantic_search(
            question,
            top_k=6,
            candidate_k=80,
            chunk_types=ORDINANCE_CHUNK_TYPES,
        ),
        semantic_search(
            question,
            top_k=3,
            candidate_k=40,
            chunk_types=PAST_CASE_CHUNK_TYPES,
        ),
        semantic_search(
            question,
            top_k=2,
            candidate_k=30,
            chunk_types=MINUTE_CHUNK_TYPES,
        ),
        semantic_search(
            question,
            top_k=2,
            candidate_k=30,
            chunk_types=CIRCULAR_CHUNK_TYPES,
        ),
    ]

    combined = []
    seen = set()

    for group in groups:
        for result in group:
            chunk_id = result.get("chunk_id")
            if chunk_id and chunk_id in seen:
                continue
            if chunk_id:
                seen.add(chunk_id)
            combined.append(result)

    if combined:
        return combined

    return semantic_search(question)


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
        "DepartmentAI (M.Tech.) Semantic Retrieval"
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

        # -------------------------------------------------
        # Close PostgreSQL ONLY when application exits.
        # -------------------------------------------------

        if conn and not conn.closed:

            conn.close()

            print(
                "\nDatabase connection closed."
            )

        print(
            "DepartmentAI semantic retrieval stopped."
        )


# ---------------------------------------------------------
# Program Entry Point
# ---------------------------------------------------------

if __name__ == "__main__":
    main()
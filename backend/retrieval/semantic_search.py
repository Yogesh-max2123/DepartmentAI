import os
import re
import math
import psycopg2
from collections import Counter
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

load_dotenv()

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# Number of candidates retrieved from pgvector before reranking.
CANDIDATE_K = 15

# Number of final results returned.
TOP_K = 1

DB_HOST = "localhost"
DB_PORT = 5432
DB_NAME = "departmentai"
DB_USER = "postgres"

DB_PASSWORD = os.getenv("DEPARTMENTAI_DB_PASSWORD")


# ---------------------------------------------------------
# Load embedding model ONCE
# ---------------------------------------------------------

print("Loading embedding model...")

model = SentenceTransformer(
    MODEL_NAME,
    local_files_only=True
)

print("Embedding model loaded.")
print(f"Embedding dimension: {model.get_embedding_dimension()}")


# ---------------------------------------------------------
# Create PostgreSQL connection ONCE
# ---------------------------------------------------------

if not DB_PASSWORD:
    raise RuntimeError(
        "DEPARTMENTAI_DB_PASSWORD environment variable is not set."
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
        "B.Tech. Degree requirements"
        ->
        ["b", "tech", "degree", "requirements"]
    """

    text = text.lower()

    # Keep alphanumeric words.
    tokens = re.findall(r"[a-z0-9]+", text)

    return tokens


def calculate_keyword_score(question: str, chunk_text: str):
    """
    Calculate lexical overlap between the question and chunk.

    Gives more importance to:
    - words appearing in both question and chunk
    - repeated matching terms
    - exact phrase matches
    """

    question_tokens = tokenize(question)
    chunk_tokens = tokenize(chunk_text)

    if not question_tokens or not chunk_tokens:
        return 0.0

    question_counter = Counter(question_tokens)
    chunk_counter = Counter(chunk_tokens)

    # Remove extremely common English question words.
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

    # Count how many meaningful question terms occur in the chunk.
    matched_terms = 0

    for token in set(meaningful_question_tokens):
        if token in chunk_counter:
            matched_terms += 1

    coverage_score = (
        matched_terms / len(set(meaningful_question_tokens))
    )

    # -----------------------------------------------------
    # Exact phrase bonus
    # -----------------------------------------------------

    normalized_question = " ".join(question_tokens)
    normalized_chunk = " ".join(chunk_tokens)

    phrase_bonus = 0.0

    # Look for meaningful two-word combinations.
    for i in range(len(meaningful_question_tokens) - 1):
        phrase = (
            meaningful_question_tokens[i]
            + " "
            + meaningful_question_tokens[i + 1]
        )

        if phrase in normalized_chunk:
            phrase_bonus += 0.1

    phrase_bonus = min(phrase_bonus, 0.3)

    score = min(1.0, coverage_score + phrase_bonus)

    return score


# ---------------------------------------------------------
# Semantic Search
# ---------------------------------------------------------

def semantic_search(question: str):
    """
    Hybrid retrieval:

    1. Generate question embedding.
    2. Retrieve CANDIDATE_K semantically similar chunks.
    3. Calculate keyword relevance.
    4. Combine semantic + lexical scores.
    5. Return the best result.
    """

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
            1 - (kc.embedding <=> %s::vector) AS similarity
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
            semantic_score
        ) = result

        keyword_score = calculate_keyword_score(
            question,
            chunk_text
        )

        # -------------------------------------------------
        # Combined relevance score
        # -------------------------------------------------
        #
        # Semantic similarity gets the larger weight.
        # Keyword matching provides an additional signal.
        #
        # 80% semantic
        # 20% lexical
        # -------------------------------------------------

        combined_score = (
            0.80 * float(semantic_score)
            +
            0.20 * keyword_score
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
                "semantic_score": float(semantic_score),
                "keyword_score": keyword_score,
                "combined_score": combined_score
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
    Display the highest-ranked retrieved chunk.
    """

    if not results:
        print("\nNo relevant information found.")
        return

    result = results[0]

    print("\n" + "=" * 70)
    print("TOP RETRIEVED RESULT")
    print("=" * 70)

    print(
        f"\nSemantic similarity: "
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

    print("\nRetrieved Text:")
    print("-" * 70)
    print(result["chunk_text"])
    print("-" * 70)


# ---------------------------------------------------------
# Main Interactive Loop
# ---------------------------------------------------------

def main():

    print("\n" + "=" * 70)
    print("DepartmentAI Semantic Retrieval")
    print("=" * 70)

    print(
        "\nEmbedding model loaded once."
        "\nPostgreSQL connection established once."
        f"\nSemantic candidates: Top {CANDIDATE_K}"
        f"\nFinal result: Top {TOP_K}"
    )

    print(
        "\nAsk multiple questions without reconnecting."
        "\nType 'exit' or 'quit' to stop.\n"
    )

    try:

        while True:

            question = input("Question: ").strip()

            if not question:
                continue

            if question.lower() in {"exit", "quit"}:
                break

            try:

                results = semantic_search(question)

                display_result(results)

            except Exception as e:

                print(
                    f"\nError while performing semantic search: {e}"
                )

    finally:

        # -------------------------------------------------
        # Close PostgreSQL ONLY when application exits.
        # -------------------------------------------------

        if conn and not conn.closed:

            conn.close()

            print("\nDatabase connection closed.")

        print("DepartmentAI semantic retrieval stopped.")


# ---------------------------------------------------------
# Program Entry Point
# ---------------------------------------------------------

if __name__ == "__main__":
    main()

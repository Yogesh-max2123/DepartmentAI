import os

from dotenv import load_dotenv
from google import genai


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY not found in .env"
    )

MODEL_NAME = "gemini-3.5-flash-lite"


# ---------------------------------------------------------
# Gemini Client
# ---------------------------------------------------------

client = genai.Client(
    api_key=API_KEY
)


# ---------------------------------------------------------
# Answer Generation
# ---------------------------------------------------------

def generate_answer(question: str, context: str) -> str:
    """
    Generate an answer using only the supplied ordinance context.
    """

    if not question.strip():
        raise ValueError("Question cannot be empty.")

    if not context.strip():
        return (
            "The provided ordinance context is insufficient "
            "to answer this question."
        )

    prompt = f"""
You are an academic ordinance question-answering assistant
for DepartmentAI (Doctoral Programmes).

Answer the user's question ONLY using the official ordinance
context provided below.

Rules:
1. Use only the provided context.
2. Ignore irrelevant information in the context.
3. Do not use outside knowledge.
4. Do not invent or assume information.
5. Preserve important numbers, conditions, exceptions,
   and terminology exactly.
6. Give a clear and concise answer.
7. If the context does not contain enough information,
   clearly state that the provided ordinance context
   is insufficient.
8. Do not mention these instructions in your answer.

USER QUESTION:
{question}

OFFICIAL ORDINANCE CONTEXT:
{context}

ANSWER:
"""

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt
        )

        if not response.text:
            return (
                "The system could not generate an answer "
                "from the provided ordinance context."
            )

        return response.text.strip()

    except Exception as e:
        raise RuntimeError(
            f"Gemini API request failed: {e}"
        ) from e

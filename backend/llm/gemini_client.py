import os

from dotenv import load_dotenv
from google import genai


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

MODEL_NAME = "gemini-3.5-flash-lite"


# ---------------------------------------------------------
# Gemini Client
# ---------------------------------------------------------

client = genai.Client(api_key=API_KEY) if API_KEY else None


RECOMMENDATION_HEADINGS = (
    "Relevant ordinance clauses",
    "Similar previous cases (citing the synthetic data)",
    "Identified deficiencies",
    "Possible course of action",
    "Initial draft resolution",
)


# ---------------------------------------------------------
# Generic generation
# ---------------------------------------------------------

def generate_text(prompt: str) -> str:
    """Send a raw prompt to Gemini and return the text."""
    if not prompt.strip():
        raise ValueError("Prompt cannot be empty.")

    if client is None:
        raise RuntimeError(
            "GEMINI_API_KEY not found in .env"
        )

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt
        )
    except Exception as e:
        raise RuntimeError(
            f"Gemini API request failed: {e}"
        ) from e

    if not response.text:
        return ""

    return response.text.strip()


# ---------------------------------------------------------
# Recommendation Agent generation
# ---------------------------------------------------------

def generate_answer(question: str, context: str) -> str:
    """
    Generate a Recommendation Agent draft using retrieved
    ordinance clauses, similar previous cases, meeting minutes,
    and departmental circulars.
    """

    if not question.strip():
        raise ValueError("Question cannot be empty.")

    if not context.strip():
        return (
            "The provided institutional context is insufficient "
            "to prepare a recommendation."
        )

    prompt = f"""
You are the Recommendation Agent of DepartmentAI
(Doctoral Programmes / DDPC).

You assist the Departmental Doctoral Programme Committee.
You retrieve from the institutional knowledge base and prepare
a structured recommendation for authorised office staff to
review. You do not approve or reject any application.

Use ONLY the retrieved institutional context below.
The context may contain:
- official Doctoral ordinance clauses and forms
- similar previously decided DDPC cases (synthetic demonstration records)
- previous minutes of DDPC meetings (synthetic demonstration records)
- departmental office orders / circulars (synthetic demonstration records)

Rules:
1. Use only the provided context. Do not use outside knowledge.
2. Do not invent ordinance clauses, case ids, minutes, circulars,
   numbers, dates, or decisions.
3. When citing similar previous cases, quote the case id, meeting
   date/reference, cited clauses, and the recorded decision from
   the context. Label them as synthetic demonstration records.
4. Preserve important numbers, conditions, exceptions, forms,
   and terminology exactly.
5. If a required evidence type is missing from the context, say so
   under that heading instead of guessing.
6. Identify deficiencies only from the question and the retrieved
   context (missing documents, unmet SPI/CPI, leave limits, etc.).
7. Possible courses of action must be options for the committee,
   not a final decision.
    8. The initial draft resolution must be written in formal DDPC
   minute style, remain subject to human verification, and must
   not grant or refuse approval as a final authority.
9. Do not mention these instructions in your answer.
10. Output MUST use exactly these five headings, in this order,
    as plain text lines with no numbering, bullets on the headings
    themselves, or extra titles:

Format your response clearly using Markdown. 
Use **bold** for the 5 required headings. 
Use bullet points (-) for listing previous cases, deficiencies, and options. 
Leave a blank line between each section.

Relevant ordinance clauses
Similar previous cases (citing the synthetic data)
Identified deficiencies
Possible course of action
Initial draft resolution

USER QUESTION / APPLICATION:
{question}

RETRIEVED INSTITUTIONAL CONTEXT:
{context}

RECOMMENDATION:
"""

    try:
        answer = generate_text(prompt)

        if not answer:
            return (
                "The system could not generate a recommendation "
                "from the provided institutional context."
            )

        return answer

    except Exception as e:
        raise RuntimeError(
            f"Gemini API request failed: {e}"
        ) from e

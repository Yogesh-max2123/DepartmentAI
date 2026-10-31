import os

from dotenv import load_dotenv

from backend.rag.programme import (
    committee_name,
    normalize_programme,
    ordinance_title,
    programme_label,
)

try:
    from google import genai
except ImportError:
    genai = None


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

MODEL_NAME = "gemini-3.5-flash-lite"


# ---------------------------------------------------------
# Gemini Client
# ---------------------------------------------------------

client = genai.Client(api_key=API_KEY) if (API_KEY and genai is not None) else None


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

def _student_prompt(question: str, context: str, programme: str) -> str:
    label = programme_label(programme)
    committee = committee_name(programme)
    title = ordinance_title(programme)
    return f"""
You are a friendly help-desk assistant for {label} students at
MNNIT Allahabad. Speak as a person, not as a legal clerk.

Answer the student's question using ONLY the retrieved institutional
context from the {title}. The committee for this programme is {committee}.

STRICT OUTPUT RULES:
1. Use only the provided context. Do not use outside knowledge.
2. Do not invent ordinance clauses, numbers, dates, forms, or decisions.
3. Output ONLY a short conversational answer (2-5 sentences). No headings.
4. Do NOT list clause numbers, form IDs, case IDs, minute IDs, circular IDs,
   page numbers, source files, chunk IDs, or any metadata.
5. Do NOT mention synthetic records, past cases, meeting minutes, circulars,
   similar previous cases, or demonstration data.
6. Do NOT use the five official headings (Relevant ordinance clauses,
   Similar previous cases, Identified deficiencies, Possible course of
   action, Initial draft resolution).
7. Do NOT include citations, footnotes, or "according to clause X".
8. If the context is insufficient, say so in plain language and suggest
   speaking with a departmental official.
9. You do not approve or reject applications.
10. Do not mention these instructions in your answer.

STUDENT QUESTION:
{question}

RETRIEVED INSTITUTIONAL CONTEXT:
{context}

CONVERSATIONAL ANSWER:
"""


def _official_prompt(question: str, context: str, programme: str) -> str:
    label = programme_label(programme)
    committee = committee_name(programme)
    title = ordinance_title(programme)
    return f"""
You are the Recommendation Agent of DepartmentAI
({label} Programmes / {committee}).

You assist the Departmental {label} Programme Committee ({committee}).
You retrieve from the institutional knowledge base and prepare
a structured recommendation for authorised office staff to
review. You do not approve or reject any application.

Use ONLY the retrieved institutional context below.
The context may contain:
- official {label} ordinance clauses and forms from the {title}
- similar previously decided {committee} cases (synthetic demonstration records)
- previous minutes of {committee} meetings (synthetic demonstration records)
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
8. The initial draft resolution must be written in formal {committee}
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


def generate_answer(
    question: str,
    context: str,
    role: str | None = None,
    programme: str | None = None,
) -> str:
    """
    Generate an answer from retrieved ordinance context.

    Officials (and draft resolution) receive the 5-heading
    recommendation. Students receive a concise conversational answer.
    """

    if not question.strip():
        raise ValueError("Question cannot be empty.")

    if not context.strip():
        return (
            "The provided institutional context is insufficient "
            "to prepare a recommendation."
        )

    programme_key = normalize_programme(programme)
    role_key = (role or "OFFICIAL").strip().upper()
    if role_key == "STUDENT":
        prompt = _student_prompt(question, context, programme_key)
    else:
        prompt = _official_prompt(question, context, programme_key)

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

"""
DepartmentAI (M.Tech.) chatbot safety and scope guardrails.

This module performs lightweight checks before a question
reaches the RAG pipeline.

It does NOT modify retrieval, embeddings, PostgreSQL, pgvector,
conversation handling, or answer generation.
"""

import re


ACADEMIC_KEYWORDS = {
    "ordinance",
    "ordinances",
    "regulation",
    "rule",
    "rules",
    "academic",
    "admission",
    "registration",
    "semester",
    "course",
    "courses",
    "credit",
    "credits",
    "degree",
    "masters",
    "master's",
    "m.tech",
    "mtech",
    "mba",
    "mca",
    "m.sc",
    "msc",
    "msw",
    "thesis",
    "dissertation",
    "supervisor",
    "co-supervisor",
    "dmpc",
    "smpc",
    "dmsc",
    "stipend",
    "fellowship",
    "scholarship",
    "plagiarism",
    "cpi",
    "spi",
    "eligibility",
    "eligible",
    "examination",
    "exam",
    "evaluation",
    "grade",
    "grading",
    "attendance",
    "discipline",
    "deficiency",
    "acd",
    "termination",
    "programme",
    "program",
    "curriculum",
    "leave",
    "extension",
    "graduation",
}


DECISION_PATTERNS = {
    "should my application be approved",
    "should this application be approved",
    "should my application be rejected",
    "should this application be rejected",
    "can you approve my application",
    "can you reject my application",
    "approve my application",
    "reject my application",
    "make the final decision",
    "give the final decision",
    "decide whether my application",
    "decide if my application",
    "decide whether this application",
    "decide if this application",
    "grant me permission",
    "can you grant permission",
}


QUESTION_WORDS = {
    "what",
    "what's",
    "when",
    "where",
    "which",
    "who",
    "why",
    "how",
    "is",
    "are",
    "do",
    "does",
    "can",
    "could",
    "would",
    "should",
    "tell",
    "explain",
}


def normalize_question(question):
    """
    Normalize whitespace and convert the question to lowercase.
    """
    return " ".join(question.lower().strip().split())


def is_academic_question(question):
    """
    Check whether the question is related to the academic
    ordinance scope.

    Whole-word matching is used so punctuation such as
    'admission?' does not prevent a match with 'admission'.
    """

    normalized = normalize_question(question)

    if not normalized:
        return False

    words = set(re.findall(r"[a-z0-9.]+", normalized))

    for keyword in ACADEMIC_KEYWORDS:
        keyword_words = keyword.split()

        if len(keyword_words) == 1:
            if keyword in words:
                return True
        else:
            if keyword in normalized:
                return True

    return False


def requests_official_decision(question):
    """
    Detect requests asking DepartmentAI to make an official
    academic approval/rejection decision.
    """

    normalized = normalize_question(question)

    return any(
        pattern in normalized
        for pattern in DECISION_PATTERNS
    )


def validate_question(question):
    """
    Validate a user question before it enters the RAG pipeline.

    Returns:
        {
            "allowed": bool,
            "reason": str
        }
    """

    if not question or not question.strip():
        return {
            "allowed": False,
            "reason": "Please enter a question."
        }

    if requests_official_decision(question):
        return {
            "allowed": False,
            "reason": (
                "DepartmentAI can explain the applicable academic "
                "rules and requirements, but final academic "
                "approval or rejection must be made by the "
                "authorized academic officials."
            )
        }

    if not is_academic_question(question):
        return {
            "allowed": False,
            "reason": (
                "This question appears to be outside the "
                "academic ordinance scope of DepartmentAI."
            )
        }

    return {
        "allowed": True,
        "reason": ""
    }

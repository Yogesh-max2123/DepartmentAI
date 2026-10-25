import re


ORDINANCE_TERM_EXPANSIONS = (
    (
        "normal and slow paces of study",
        "semester load requirements normal pace slow pace of study",
    ),
    (
        "academic probation",
        "academic deficiency ACD minimum performance requirement",
    ),
    (
        "degree extension",
        "undergraduate programme maximum permissible duration",
    ),
    (
        "normal pace of study",
        "semester load requirements normal pace",
    ),
    (
        "slow pace of study",
        "semester load requirements slow pace",
    ),
)


def expand_ordinance_query(question: str) -> str:
    """Map common user phrasing to terminology used by the ordinance."""
    normalized = " ".join(question.casefold().split())
    for phrase, canonical_terms in ORDINANCE_TERM_EXPANSIONS:
        if phrase in normalized:
            return re.sub(
                re.escape(phrase),
                canonical_terms,
                question,
                count=1,
                flags=re.IGNORECASE,
            )
    return question

from __future__ import annotations

import json
import re
from pathlib import Path

import pymupdf


REQUIRED_DOCUMENTS = {
    "comprehensive_exam": [
        "SRC recommendation / comprehensive exam form (DP-related)",
        "grade sheet or CPI record",
        "supervisor consent",
    ],
    "thesis_extension": [
        "progress report",
        "supervisor recommendation",
        "justification for extension",
    ],
    "supervisor_allocation": [
        "research proposal",
        "consent of proposed supervisor",
    ],
    "supervisor_change": [
        "current supervisor NOC",
        "proposed supervisor consent",
        "justification for change",
    ],
    "semester_leave": [
        "leave application or medical certificate",
        "supervisor recommendation",
    ],
    "thesis_submission": [
        "open seminar completion record",
        "thesis synopsis",
        "plagiarism / similarity report",
    ],
    "dissertation_extension": [
        "progress report",
        "supervisor recommendation",
        "justification for extension",
    ],
    "conversion_full_part": [
        "MP-01 conversion form or equivalent",
        "supervisor recommendation",
        "justification for conversion",
    ],
    "general": [
        "supporting document related to the request",
    ],
    "slow_pace": [
        "BP-04 slow pace form or equivalent",
        "justification for slow pace of study",
    ],
    "make_up_exam": [
        "BP-10 make-up examination form or equivalent",
        "medical certificate or supporting reason",
    ],
    "back_paper": [
        "BP-11 back paper / grade improvement form",
        "grade sheet",
    ],
    "minor_honours": [
        "BP-05 / BP-07 registration form",
        "supervisor or coordinator consent",
    ],
}

KEYWORD_HINTS = {
    "comprehensive_exam": ["comprehensive", "src", "cpi", "spi", "grade", "supervisor", "exam"],
    "thesis_extension": ["extension", "progress", "thesis", "supervisor", "duration"],
    "supervisor_allocation": ["supervisor", "allocation", "research", "proposal", "consent"],
    "supervisor_change": ["supervisor", "change", "noc", "consent", "allocation"],
    "semester_leave": ["leave", "medical", "semester", "absence", "certificate"],
    "thesis_submission": ["thesis", "open seminar", "synopsis", "plagiarism", "similarity", "submission"],
    "dissertation_extension": ["extension", "progress", "dissertation", "thesis", "supervisor"],
    "conversion_full_part": ["conversion", "full time", "part time", "mp-01", "supervisor"],
    "general": ["application", "request", "student", "phd", "ph.d", "mtech", "m.tech", "masters", "btech", "b.tech", "ordinance"],
    "slow_pace": ["slow", "pace", "bp-04", "study"],
    "make_up_exam": ["make-up", "makeup", "examination", "medical", "bp-10"],
    "back_paper": ["back", "paper", "grade", "improvement", "bp-11"],
    "minor_honours": ["minor", "honours", "honors", "research", "bp-05", "bp-07"],
}


def extract_pdf_text(path: str | Path, max_chars: int = 12000) -> str:
    pdf_path = Path(path)
    if not pdf_path.exists():
        return ""
    pages = []
    try:
        with pymupdf.open(pdf_path) as doc:
            for page in doc:
                pages.append(page.get_text("text") or "")
    except Exception as exc:
        return f"[PDF extraction failed: {exc}]"
    text = "\n".join(pages)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) > max_chars:
        return text[:max_chars] + "\n...[truncated]..."
    return text


def _fallback_verify(application_type: str, description: str, extracted_text: str, filenames: list[str]) -> dict:
    required = REQUIRED_DOCUMENTS.get(application_type, REQUIRED_DOCUMENTS["general"])
    blob = f"{description}\n{extracted_text}\n{' '.join(filenames)}".lower()
    if not extracted_text.strip() and not filenames:
        return {
            "valid": False,
            "missing_documents": required,
            "matched_documents": [],
            "notes": "No supporting PDF was uploaded. Attach the required documents and resubmit.",
            "method": "fallback",
        }
    if not extracted_text.strip():
        return {
            "valid": False,
            "missing_documents": required,
            "matched_documents": [],
            "notes": "Uploaded files contained no extractable text. Use a text-based PDF.",
            "method": "fallback",
        }
    hints = KEYWORD_HINTS.get(application_type, KEYWORD_HINTS["general"])
    hits = [word for word in hints if word in blob]
    matched = []
    missing = []
    for item in required:
        tokens = [tok for tok in re.split(r"[^a-z0-9]+", item.lower()) if len(tok) > 3]
        if any(tok in blob for tok in tokens):
            matched.append(item)
        else:
            missing.append(item)
    valid = len(missing) == 0 or (len(hits) >= 2 and len(matched) >= 1)
    if valid:
        missing = []
    notes = (
        "Documents appear consistent with the application type."
        if valid
        else "Some required evidence was not detected in the uploaded PDFs."
    )
    return {
        "valid": valid,
        "missing_documents": missing,
        "matched_documents": matched,
        "notes": notes,
        "method": "fallback",
        "keyword_hits": hits,
    }


def _parse_llm_json(raw: str) -> dict | None:
    if not raw:
        return None
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        return None
    return None


def verify_documents(application_type: str, description: str, extracted_text: str, filenames: list[str]) -> dict:
    required = REQUIRED_DOCUMENTS.get(application_type, REQUIRED_DOCUMENTS["general"])
    fallback = _fallback_verify(application_type, description, extracted_text, filenames)
    try:
        from backend.llm.gemini_client import generate_text

        prompt = f"""
You are the document-verification officer for DDPC / DMPC at MNNIT Allahabad.
Decide whether uploaded PDFs match the application type.

Application type: {application_type}
Student description:
{description}

Uploaded filenames: {", ".join(filenames) or "(none)"}
Required documents:
{json.dumps(required)}

Extracted PDF text:
{extracted_text[:8000] or "(empty)"}

Return ONLY JSON with this shape:
{{
  "valid": true or false,
  "missing_documents": ["..."],
  "matched_documents": ["..."],
  "notes": "one short paragraph"
}}
If the text reasonably covers the required evidence, set valid=true and missing_documents=[].
Do not invent extra bureaucratic requirements.
"""
        raw = generate_text(prompt)
        parsed = _parse_llm_json(raw)
        if not parsed:
            return fallback
        valid = bool(parsed.get("valid"))
        missing = parsed.get("missing_documents") or []
        if not isinstance(missing, list):
            missing = [str(missing)]
        missing = [str(item) for item in missing if str(item).strip()]
        matched = parsed.get("matched_documents") or []
        if not isinstance(matched, list):
            matched = [str(matched)]
        if valid:
            missing = []
        return {
            "valid": valid,
            "missing_documents": missing,
            "matched_documents": [str(item) for item in matched],
            "notes": str(parsed.get("notes") or fallback["notes"]),
            "method": "gemini",
        }
    except Exception:
        return fallback

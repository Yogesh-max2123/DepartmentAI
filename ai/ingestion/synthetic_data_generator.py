"""
DepartmentAI (Ph.D.) - Synthetic Institutional Knowledge Generator

Reads the existing Doctoral ordinance chunks and uses the Gemini API to
generate realistic, ordinance-grounded JSON datasets for:

    * similar previously decided DDPC cases
    * previous minutes of DDPC meetings
    * departmental office orders / circulars

These records fill knowledge-base gaps that are specified in the project
proposal but are not available as real institutional archives.

Input:
    documents/phd/processed/phd_ordinance_chunks.json

Output:
    documents/phd/processed/synthetic_past_cases.json
    documents/phd/processed/synthetic_ddpc_minutes.json
    documents/phd/processed/synthetic_circulars.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_env():
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")

CHUNKS_FILE = (
    PROJECT_ROOT
    / "documents"
    / "phd"
    / "processed"
    / "phd_ordinance_chunks.json"
)

OUTPUT_DIR = PROJECT_ROOT / "documents" / "phd" / "processed"

PAST_CASES_FILE = OUTPUT_DIR / "synthetic_past_cases.json"
MINUTES_FILE = OUTPUT_DIR / "synthetic_ddpc_minutes.json"
CIRCULARS_FILE = OUTPUT_DIR / "synthetic_circulars.json"

MODEL_NAME = "gemini-3.5-flash-lite"

DOCUMENT_NAME = "MNNIT Doctoral Ordinance"
SOURCE_ORDINANCE = "Ordinances_for_Doctoral_Programm2023.pdf"
INSTITUTE = (
    "Motilal Nehru National Institute of Technology Allahabad"
)

DEFAULT_CASES = 12
DEFAULT_MINUTES = 10
DEFAULT_CIRCULARS = 10
MAX_GROUND_TRUTH_CLAUSES = 24
MAX_CHARS_PER_CLAUSE = 700

PRIORITY_KEYWORDS = (
    "admission",
    "registration",
    "late registration",
    "leave",
    "semester leave",
    "spi",
    "cpi",
    "acd",
    "deficiency",
    "termination",
    "thesis",
    "supervisor",
    "co-supervisor",
    "comprehensive examination",
    "state-of-the-art",
    "open seminar",
    "src",
    "oral board",
    "stipend",
    "fellowship",
    "waiver",
    "duration",
    "part-time",
    "full-time",
    "plagiarism",
    "attendance",
    "credit",
    "degree",
    "extension",
)


DATASET_SPECS = {
    "past_case": {
        "title": "Synthetic Previously Decided DDPC Cases",
        "file_name": PAST_CASES_FILE.name,
        "chunk_type": "past_case",
        "output_path": PAST_CASES_FILE,
        "record_key": "records",
        "id_field": "case_id",
    },
    "meeting_minute": {
        "title": "Synthetic Previous Minutes of DDPC Meetings",
        "file_name": MINUTES_FILE.name,
        "chunk_type": "meeting_minute",
        "output_path": MINUTES_FILE,
        "record_key": "records",
        "id_field": "minute_id",
    },
    "circular": {
        "title": "Synthetic Departmental Office Orders and Circulars",
        "file_name": CIRCULARS_FILE.name,
        "chunk_type": "circular",
        "output_path": CIRCULARS_FILE,
        "record_key": "records",
        "id_field": "circular_id",
    },
}


def load_json(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def extract_json_payload(text: str):
    """Parse a JSON object or array from a Gemini response."""
    if not text or not text.strip():
        raise ValueError("Empty model response.")

    cleaned = text.strip()

    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"(\{.*\}|\[.*\])", cleaned, flags=re.DOTALL)
        if not match:
            raise ValueError("Could not parse JSON from model response.")
        return json.loads(match.group(1))


def clause_priority(chunk: dict) -> int:
    text = " ".join(
        [
            str(chunk.get("clause_title") or ""),
            str(chunk.get("section_title") or ""),
            str(chunk.get("text") or ""),
        ]
    ).lower()

    score = 0
    for keyword in PRIORITY_KEYWORDS:
        if keyword in text:
            score += 1
    return score


def select_ground_truth_clauses(chunks, limit=MAX_GROUND_TRUTH_CLAUSES):
    """Pick representative ordinance clauses as generation ground truth."""
    seen = set()
    ranked = []

    for chunk in chunks:
        if chunk.get("content_type") != "ordinance_clause":
            continue

        clause = chunk.get("clause")
        if not clause or clause in seen:
            continue

        seen.add(clause)
        ranked.append(chunk)

    ranked.sort(key=clause_priority, reverse=True)
    selected = ranked[:limit]
    selected.sort(
        key=lambda item: tuple(
            int(part) if part.isdigit() else 0
            for part in str(item.get("clause", "0")).split(".")
        )
    )
    return selected


def build_ordinance_ground_truth(chunks) -> str:
    selected = select_ground_truth_clauses(chunks)
    if not selected:
        raise ValueError(
            "No ordinance_clause chunks found in phd_ordinance_chunks.json."
        )

    parts = []
    for chunk in selected:
        text = (chunk.get("text") or "").strip()
        if len(text) > MAX_CHARS_PER_CLAUSE:
            text = text[:MAX_CHARS_PER_CLAUSE].rstrip() + "..."

        parts.append(
            "\n".join(
                [
                    f"Clause {chunk.get('clause')}: {chunk.get('clause_title') or ''}".strip(),
                    f"Section {chunk.get('section')}: {chunk.get('section_title') or ''}".strip(),
                    f"Forms: {', '.join(chunk.get('forms_referenced') or []) or 'None'}",
                    text,
                ]
            )
        )

    return "\n\n---\n\n".join(parts)


def build_gemini_client():
    _load_env()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY not found in .env. "
            "Set it before generating synthetic datasets."
        )

    from google import genai

    return genai.Client(api_key=api_key)


def generate_json_with_gemini(client, prompt: str):
    from google.genai import types

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.65,
        ),
    )

    if not response.text:
        raise RuntimeError("Gemini returned an empty response.")

    return extract_json_payload(response.text)


def past_cases_prompt(ordinance_context: str, count: int) -> str:
    return f"""
You are generating SYNTHETIC but highly realistic academic-governance records
for {INSTITUTE}.

These records will be used only as demonstration knowledge-base content for
the Departmental Doctoral Programme Committee (DDPC). They must be grounded
in the official Doctoral ordinance clauses supplied below. Do not invent
ordinance rules. Every decision must cite one or more real clause numbers
from the ground truth.

Write {count} previously decided DDPC cases covering a diverse mix of:
comprehensive examination failure / second attempt, doctoral supervisor
allocation, change of supervisor / co-supervisor, SRC constitution,
state-of-the-art seminar, open seminar, Ph.D. thesis extension, late
registration, semester leave, academic deficiency (SPI/CPI below 6.5),
stipend or fellowship issues, full-time to part-time conversion, maximum
duration, plagiarism / similarity index, waiver in special cases, and
missing-document deficiencies.

Rules:
1. Use only the supplied ordinance clauses as legal ground truth.
2. Students must be anonymized (e.g. "Ph.D./CSE/2022/014"). No real people.
3. Departments may include CSE, ECE, ME, EE, CE, and similar MNNIT departments.
4. Dates should fall in academic years 2022-23 through 2024-25.
5. Decisions must be plausible committee outcomes: recommended, deferred,
   recommended subject to compliance, or not recommended.
6. Include at least two cases that were deferred or not recommended because
   of identified deficiencies.
7. Return ONLY a JSON array. No markdown.

Each object MUST contain:
- case_id (string, e.g. "DDPC/2024/CSE/014")
- meeting_date (YYYY-MM-DD)
- meeting_reference (string, e.g. "DDPC/CSE/2023-24/07")
- department (string)
- programme (string)
- subject (string)
- student_ref (anonymized string)
- applicable_clauses (array of clause-number strings from the ground truth)
- applicable_forms (array of form ids such as "DP-02", or empty)
- facts (string)
- deficiencies (string; use "None recorded." if none)
- discussion_summary (string)
- decision (string)
- resolution (string; official-looking DDPC resolution wording)
- text (string; a single searchable narrative that includes the case id,
  date, subject, clauses, facts, deficiencies, decision and resolution)

ORDINANCE GROUND TRUTH:
{ordinance_context}
"""


def minutes_prompt(ordinance_context: str, count: int) -> str:
    return f"""
You are generating SYNTHETIC but highly realistic minutes of the Departmental
Doctoral Programme Committee (DDPC) of {INSTITUTE}.

Ground every agenda item and resolution in the official Doctoral ordinance
clauses supplied below. Do not invent ordinance rules.

Write {count} meeting-minute records. Each record is ONE agenda item extracted
from a DDPC meeting, written in formal academic-committee style.

Cover a mix of: confirmation of previous minutes, comprehensive examination
failure, doctoral supervisor allocation, SRC constitution, state-of-the-art
seminar, open seminar, Ph.D. thesis extension, leave, academic deficiency,
stipend/fellowship, oral board, and any-other-item circular implementation.

Rules:
1. Cite only clause numbers that appear in the ground truth.
2. Anonymize students.
3. Include chair (Head of the Department), convener (DDPC Convener), and
   two or three faculty members in attendance.
4. Dates in academic years 2022-23 through 2024-25.
5. Return ONLY a JSON array. No markdown.

Each object MUST contain:
- minute_id (string, e.g. "DDPC/MIN/2024/05-03")
- meeting_number (string, e.g. "7th DDPC meeting, AY 2023-24")
- meeting_date (YYYY-MM-DD)
- department (string)
- agenda_item_number (string)
- agenda_item (string)
- attendance (array of role/name strings; names may be generic titles)
- applicable_clauses (array of clause-number strings)
- discussion (string)
- resolution (string)
- action_by (string)
- text (string; a searchable minutes excerpt including minute_id, date,
  agenda item, discussion, cited clauses, and the resolution)

ORDINANCE GROUND TRUTH:
{ordinance_context}
"""


def circulars_prompt(ordinance_context: str, count: int) -> str:
    return f"""
You are generating SYNTHETIC but highly realistic departmental office orders
and circulars for {INSTITUTE}, issued by a Head of Department / DDPC Convener
to implement the official Doctoral Programme ordinances.

Ground every circular in the supplied ordinance clauses. Do not invent rules.

Write {count} records mixing office orders and circulars on:
academic calendar and registration, late registration, leave rules, Ph.D.
thesis submission deadlines, plagiarism / similarity checks (15% limit),
stipend/fellowship release, doctoral supervisor allocation, comprehensive
examination notices, DDPC meeting notices, and waiver procedure.

Rules:
1. Cite only clause numbers from the ground truth.
2. Use realistic file numbers such as "CSED/DDPC/OO/2024/07".
3. Dates in academic years 2022-23 through 2024-25.
4. Tone must be formal institutional English.
5. Return ONLY a JSON array. No markdown.

Each object MUST contain:
- circular_id (string)
- circular_type (either "office_order" or "circular")
- file_number (string)
- issue_date (YYYY-MM-DD)
- issuing_authority (string)
- department (string)
- subject (string)
- applicable_clauses (array of clause-number strings)
- content (string; the body of the order/circular)
- text (string; a searchable version including circular_id, file number,
  date, subject, cited clauses, and the full content)

ORDINANCE GROUND TRUTH:
{ordinance_context}
"""


REQUIRED_FIELDS = {
    "past_case": [
        "case_id",
        "meeting_date",
        "subject",
        "applicable_clauses",
        "facts",
        "deficiencies",
        "decision",
        "resolution",
        "text",
    ],
    "meeting_minute": [
        "minute_id",
        "meeting_number",
        "meeting_date",
        "agenda_item",
        "applicable_clauses",
        "discussion",
        "resolution",
        "text",
    ],
    "circular": [
        "circular_id",
        "circular_type",
        "issue_date",
        "subject",
        "applicable_clauses",
        "content",
        "text",
    ],
}


def normalize_records(dataset_type: str, payload, expected_count: int):
    if isinstance(payload, dict):
        for key in ("records", "cases", "minutes", "circulars", "items", "data"):
            if isinstance(payload.get(key), list):
                payload = payload[key]
                break
        else:
            payload = [payload]

    if not isinstance(payload, list):
        raise ValueError(f"{dataset_type}: model did not return a JSON array.")

    required = REQUIRED_FIELDS[dataset_type]
    cleaned = []

    for index, record in enumerate(payload, start=1):
        if not isinstance(record, dict):
            continue

        missing = [field for field in required if not record.get(field)]
        if missing:
            continue

        clauses = record.get("applicable_clauses") or []
        if isinstance(clauses, str):
            clauses = [part.strip() for part in re.split(r"[;,]", clauses) if part.strip()]
        record["applicable_clauses"] = [str(item) for item in clauses]

        text = str(record.get("text") or "").strip()
        if not text:
            continue

        record["synthetic"] = True
        record["record_index"] = index
        cleaned.append(record)

    minimum_accepted = min(expected_count, max(1, expected_count // 2))
    if len(cleaned) < minimum_accepted:
        raise ValueError(
            f"{dataset_type}: only {len(cleaned)} valid records were generated."
        )

    return cleaned[:expected_count]


def wrap_dataset(dataset_type: str, records: list[dict], ordinance_clause_count: int):
    spec = DATASET_SPECS[dataset_type]
    generated_at = datetime.now(timezone.utc).isoformat()

    return {
        "document": spec["title"],
        "source_file": spec["file_name"],
        "chunk_type": spec["chunk_type"],
        "synthetic": True,
        "disclaimer": (
            "Synthetic demonstration data generated from the official "
            "Doctoral Programme ordinance. Not real institutional records."
        ),
        "grounded_in": DOCUMENT_NAME,
        "source_ordinance": SOURCE_ORDINANCE,
        "institute": INSTITUTE,
        "embedding_hint": (
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        ),
        "ordinance_clauses_used": ordinance_clause_count,
        "generated_at": generated_at,
        "total_records": len(records),
        "records": records,
    }


def generate_dataset(client, dataset_type: str, ordinance_context: str, count: int):
    prompt_builders = {
        "past_case": past_cases_prompt,
        "meeting_minute": minutes_prompt,
        "circular": circulars_prompt,
    }

    print(f"Generating {count} synthetic {dataset_type} records via Gemini...")
    payload = generate_json_with_gemini(
        client,
        prompt_builders[dataset_type](ordinance_context, count),
    )
    records = normalize_records(dataset_type, payload, count)
    print(f"Accepted {len(records)} {dataset_type} records.")
    return records


def run_generator(cases: int, minutes: int, circulars: int):
    print("========================================")
    print("DepartmentAI Synthetic Data Generator")
    print("========================================")

    chunks_data = load_json(CHUNKS_FILE)
    chunks = chunks_data.get("chunks", [])
    if not chunks:
        raise ValueError("phd_ordinance_chunks.json contains 0 chunks.")

    print(f"Ordinance chunks loaded: {len(chunks)}")
    ordinance_context = build_ordinance_ground_truth(chunks)
    clause_count = ordinance_context.count("\n\n---\n\n") + 1
    print(f"Ground-truth clauses : {clause_count}")

    client = build_gemini_client()

    datasets = {
        "past_case": generate_dataset(client, "past_case", ordinance_context, cases),
        "meeting_minute": generate_dataset(
            client, "meeting_minute", ordinance_context, minutes
        ),
        "circular": generate_dataset(client, "circular", ordinance_context, circulars),
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for dataset_type, records in datasets.items():
        wrapped = wrap_dataset(dataset_type, records, clause_count)
        output_path = DATASET_SPECS[dataset_type]["output_path"]
        save_json(output_path, wrapped)
        print(f"Wrote {len(records):>2} records -> {output_path}")

    print("\n========================================")
    print("Synthetic data generation complete.")
    print("========================================")
    print(f"Past cases : {len(datasets['past_case'])}")
    print(f"Minutes    : {len(datasets['meeting_minute'])}")
    print(f"Circulars  : {len(datasets['circular'])}")
    print("Next: python backend/ingest_knowledge_base.py")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "Generate synthetic DDPC cases, meeting minutes, and circulars "
            "from the Doctoral ordinance chunks using the Gemini API."
        )
    )
    parser.add_argument("--cases", type=int, default=DEFAULT_CASES)
    parser.add_argument("--minutes", type=int, default=DEFAULT_MINUTES)
    parser.add_argument("--circulars", type=int, default=DEFAULT_CIRCULARS)
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        run_generator(args.cases, args.minutes, args.circulars)
    except Exception as exc:
        print("\nERROR: Synthetic data generation failed.")
        print(exc)
        sys.exit(1)


if __name__ == "__main__":
    main()

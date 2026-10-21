import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "ai" / "ingestion"))

from synthetic_data_generator import (  # noqa: E402
    extract_json_payload,
    normalize_records,
    wrap_dataset,
    select_ground_truth_clauses,
    clause_priority,
)


def test_extract_json_payload_from_fenced_block():
    payload = extract_json_payload(
        '```json\n[{"case_id": "DMPC/2024/001"}]\n```'
    )
    assert payload[0]["case_id"] == "DMPC/2024/001"


def test_normalize_records_keeps_valid_past_cases():
    records = normalize_records(
        "past_case",
        [
            {
                "case_id": "DMPC/2024/CSE/014",
                "meeting_date": "2024-03-12",
                "subject": "Late registration",
                "applicable_clauses": "4.2, 4.3",
                "facts": "The student applied after the deadline.",
                "deficiencies": "Form MP-02 not attached.",
                "decision": "Deferred",
                "resolution": "The case is deferred pending Form MP-02.",
                "text": "Case DMPC/2024/CSE/014 deferred for missing Form MP-02.",
            }
        ],
        expected_count=1,
    )

    assert len(records) == 1
    assert records[0]["applicable_clauses"] == ["4.2", "4.3"]
    assert records[0]["synthetic"] is True


def test_wrap_dataset_sets_chunk_type():
    wrapped = wrap_dataset(
        "meeting_minute",
        [{"minute_id": "DMPC/MIN/2024/01", "text": "Minutes excerpt."}],
        ordinance_clause_count=8,
    )

    assert wrapped["chunk_type"] == "meeting_minute"
    assert wrapped["synthetic"] is True
    assert wrapped["total_records"] == 1
    json.dumps(wrapped)


def test_select_ground_truth_prefers_priority_clauses():
    chunks = [
        {
            "content_type": "ordinance_clause",
            "clause": "1.1",
            "clause_title": "Introduction",
            "section_title": "Introduction",
            "text": "This ordinance introduces the programmes.",
        },
        {
            "content_type": "ordinance_clause",
            "clause": "9.2",
            "clause_title": "Academic deficiency",
            "section_title": "Academic Performance Requirements",
            "text": "A student with SPI below 5.5 shall be called ACD.",
        },
        {
            "content_type": "form",
            "clause": None,
            "text": "Form MP-02",
        },
    ]

    selected = select_ground_truth_clauses(chunks, limit=1)
    assert selected[0]["clause"] == "9.2"
    assert clause_priority(chunks[1]) > clause_priority(chunks[0])

from backend.rag.source_formatter import build_context, format_sources


RECOMMENDATION_HEADINGS = (
    "Relevant ordinance clauses",
    "Similar previous cases (citing the synthetic data)",
    "Identified deficiencies",
    "Possible course of action",
    "Initial draft resolution",
)


def test_recommendation_headings_are_exact():
    assert RECOMMENDATION_HEADINGS == (
        "Relevant ordinance clauses",
        "Similar previous cases (citing the synthetic data)",
        "Identified deficiencies",
        "Possible course of action",
        "Initial draft resolution",
    )


def test_build_context_labels_synthetic_sources():
    context = build_context(
        [
            {
                "chunk_id": "mtech_9_9_2_001",
                "chunk_type": "ordinance_clause",
                "section_number": "9",
                "section_title": "Academic Performance Requirements",
                "clause_number": "9.2",
                "page_start": 24,
                "page_end": 24,
                "chunk_text": "The minimum SPI/CPI requirement is 5.5.",
            },
            {
                "chunk_id": "DMPC/2024/CSE/014",
                "chunk_type": "past_case",
                "subject": "Late registration",
                "source_file": "synthetic_past_cases.json",
                "chunk_text": "The DMPC deferred the late-registration request.",
            },
        ]
    )

    assert "[ORDINANCE CLAUSE]" in context
    assert "[SIMILAR PREVIOUS CASE (synthetic)]" in context
    assert "DMPC/2024/CSE/014" in context
    assert "Clause: 9.2" in context


def test_format_sources_includes_chunk_type():
    sources = format_sources(
        [
            {
                "chunk_id": "CSED/DMPC/OO/2024/07",
                "chunk_type": "circular",
                "subject": "Thesis submission deadline",
                "source_file": "synthetic_circulars.json",
            }
        ]
    )

    assert sources[0]["chunk_type"] == "circular"
    assert sources[0]["chunk_id"] == "CSED/DMPC/OO/2024/07"
    assert sources[0]["pages"] is None

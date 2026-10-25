from backend.rag.source_formatter import format_sources


def test_source_formatter_matches_assistant_response_contract():
    sources = format_sources(
        [
            {
                "source_file": "UG Ordinance.pdf",
                "clause_title": "Late Registration",
                "section_number": "5",
                "clause_number": "5.1",
                "page_start": 6,
                "page_end": 7,
                "combined_score": 0.82,
            }
        ]
    )

    assert sources == [
        {
            "source": "UG Ordinance.pdf",
            "title": "Late Registration",
            "page": 6,
            "section": "5",
            "relevance": 0.82,
            "citation": "Section 5, clause 5.1, pages 6-7",
        }
    ]

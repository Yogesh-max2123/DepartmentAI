from backend.rag.source_formatter import format_sources


def test_source_formatter_matches_assistant_response_contract():
    sources = format_sources(
        [
            {
                "source_file": "UG Ordinance.pdf",
                "source_id": "UG_ORDINANCE_2023",
                "source_type": "ORDINANCE",
                "programme": "UG",
                "source_version": "BOG-73.13(A)-2023-08-10",
                "chunk_id": "ug-ordinance-5-1",
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
            "source_id": "UG_ORDINANCE_2023",
            "source_type": "ORDINANCE",
            "programme": "UG",
            "source_version": "BOG-73.13(A)-2023-08-10",
            "chunk_id": "ug-ordinance-5-1",
            "title": "Late Registration",
            "page": 6,
            "section": "5",
            "relevance": 0.82,
            "citation": "Section 5, clause 5.1, pages 6-7",
        }
    ]

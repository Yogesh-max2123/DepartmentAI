def format_sources(results):
    sources = []

    for result in results:
        section = result.get("section_number")
        clause = result.get("clause_number")
        page_start = result.get("page_start")
        page_end = result.get("page_end")
        citation_parts = []
        if section:
            citation_parts.append(f"Section {section}")
        if clause:
            citation_parts.append(f"clause {clause}")
        if page_start is not None:
            page_range = (
                f"{page_start}-{page_end}"
                if page_end is not None and page_end != page_start
                else str(page_start)
            )
            citation_parts.append(f"pages {page_range}")

        sources.append({
            "source": result.get("source_file") or "UG Ordinance",
            "source_id": result.get("source_id"),
            "source_type": result.get("source_type", "ORDINANCE"),
            "programme": result.get("programme"),
            "source_version": result.get("source_version"),
            "chunk_id": result.get("chunk_id"),
            "title": (
                result.get("clause_title")
                or result.get("section_title")
                or result.get("source_title")
                or "Ordinance"
            ),
            "page": page_start,
            "section": section,
            "relevance": result.get("combined_score"),
            "citation": ", ".join(citation_parts),
        })

    return sources
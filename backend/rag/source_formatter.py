def format_sources(results):
    sources = []

    for result in results:
        sources.append({
            "chunk_id": result.get("chunk_id"),
            "section": result.get("section_number"),
            "section_title": result.get("section_title"),
            "clause": result.get("clause_number"),
            "pages": f"{result.get('page_start')}-{result.get('page_end')}",
        })

    return sources

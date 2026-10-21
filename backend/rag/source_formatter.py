CHUNK_TYPE_LABELS = {
    "ordinance_clause": "ORDINANCE CLAUSE",
    "form": "ORDINANCE FORM",
    "past_case": "SIMILAR PREVIOUS CASE (synthetic)",
    "meeting_minute": "PREVIOUS DMPC MINUTES (synthetic)",
    "circular": "OFFICE ORDER / CIRCULAR (synthetic)",
}


def format_chunk(result):
    chunk_type = result.get("chunk_type") or "ordinance_clause"
    label = CHUNK_TYPE_LABELS.get(chunk_type, chunk_type.upper())
    chunk_id = result.get("chunk_id") or "unknown"
    header = [f"[{label}] ID: {chunk_id}"]

    section_number = result.get("section_number")
    section_title = result.get("section_title")
    if section_number or section_title:
        header.append(
            f"Section {section_number}: {section_title}".strip()
        )

    if result.get("clause_number"):
        header.append(f"Clause: {result.get('clause_number')}")

    subject = result.get("subject")
    if subject:
        header.append(f"Subject: {subject}")

    page_start = result.get("page_start")
    page_end = result.get("page_end")
    if page_start is not None:
        header.append(f"Pages: {page_start}-{page_end}")

    source_file = result.get("source_file")
    if source_file:
        header.append(f"Source: {source_file}")

    header.append("")
    header.append(result.get("chunk_text") or "")
    return "\n".join(header)


def build_context(results):
    if not results:
        return ""

    return "\n---\n".join(format_chunk(result) for result in results)


def format_sources(results):
    sources = []

    for result in results:
        pages = None
        page_start = result.get("page_start")
        page_end = result.get("page_end")
        if page_start is not None:
            pages = f"{page_start}-{page_end}"

        sources.append({
            "chunk_id": result.get("chunk_id"),
            "chunk_type": result.get("chunk_type"),
            "section": result.get("section_number"),
            "section_title": result.get("section_title"),
            "clause": result.get("clause_number"),
            "subject": result.get("subject"),
            "source_file": result.get("source_file"),
            "pages": pages,
        })

    return sources

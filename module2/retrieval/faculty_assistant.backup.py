"""
Interactive Module II faculty assistant.

Run from the DepartmentAI project root:
    python -m module2.retrieval.faculty_assistant

This module reuses faculty_search.py and Module II's existing database.
It does not modify Module I or create a second embedding cache.
"""

import re
from collections import deque

from module2.database.connection import get_connection
from module2.retrieval.faculty_search import (
    TOP_K,
    detect_requested_sections,
    display_results,
    ensure_corpus_loaded,
    faculty_search,
    resolve_faculty,
)
from module2.retrieval.faculty_gemini import generate_faculty_answer

HISTORY_LIMIT = 8
DEFAULT_LIST_LIMIT = 5
MAX_LIST_LIMIT = 20


def is_department_wide_question(question):
    q = (question or "").lower()
    phrases = (
        "csed", "cse department", "department-wide", "department wide",
        "all faculty", "all professors", "every faculty", "each professor",
        "department publications", "faculty publications",
    )
    return any(phrase in q for phrase in phrases)


def extract_year_range(question):
    """Return an explicitly stated two-year range, or None."""
    years = re.findall(r"\b(?:19|20)\d{2}\b", question or "")
    if len(years) < 2:
        return None
    start, end = int(years[0]), int(years[1])
    if start > end:
        start, end = end, start
    if start < 1900 or end > 2100:
        return None
    return start, end


def requested_limit(question, default=DEFAULT_LIST_LIMIT):
    q = (question or "").lower()
    match = re.search(r"\b(?:top|first|last|latest|recent)\s+(\d{1,2})\b", q)
    if not match:
        match = re.search(r"\b(\d{1,2})\s+(?:latest|recent|newest)\b", q)
    if not match:
        return default
    return max(1, min(int(match.group(1)), MAX_LIST_LIMIT))


def asks_publication_count(question):
    q = (question or "").lower()
    count_intent = any(
        phrase in q
        for phrase in (
            "how many", "number of", "count of", "count the",
            "total number", "total publications",
        )
    )
    return count_intent and any(
        word in q for word in ("publication", "publications", "papers", "paper")
    )


def asks_latest_publications(question):
    q = (question or "").lower()
    publication_intent = any(
        word in q
        for word in ("publication", "publications", "paper", "papers")
    )
    return publication_intent and any(
        word in q for word in ("latest", "recent", "newest", "most recent")
    )


def asks_publication_list(question):
    q = (question or "").lower()
    return any(
        phrase in q
        for phrase in ("list publications", "list the publications",
                       "show publications", "show the publications",
                       "mention publications", "mention the publications")
    )


def _year_sql(expression="p.publication_year"):
    """Return a usable publication year without trusting malformed values.

    Prefer the structured publication_year when it is a four-digit year;
    otherwise fall back to the year of publication_date. This lets date-range
    queries use available structured evidence without guessing from titles.
    """
    return (
        "COALESCE("
        f"CASE WHEN ({expression})::text ~ '^(19|20)[0-9]{{2}}$' "
        f"THEN ({expression})::text::integer ELSE NULL END, "
        "EXTRACT(YEAR FROM p.publication_date)::integer"
        ")"
    )


def publication_count(faculty_id=None, faculty_ids=None, year_range=None):
    """
    Count distinct publication records and faculty-publication links.

    Unique publications count each publication once, even if several CSED
    faculty co-authored it. Association count counts each faculty link.
    """
    year_expr = _year_sql("p.publication_year")
    where = ["f.is_active IS DISTINCT FROM FALSE"]
    params = []

    # A total count includes records with an unrecorded year. A bounded
    # year-range query can only include records with a valid structured year.
    if year_range:
        where.append(f"{year_expr} BETWEEN %s AND %s")
        params.extend(year_range)

    if faculty_ids:
        where.append("fp.faculty_id = ANY(%s)")
        params.append(list(faculty_ids))
    elif faculty_id is not None:
        where.append("fp.faculty_id = %s")
        params.append(faculty_id)

    sql = f"""
        SELECT COUNT(DISTINCT p.id) AS unique_publications,
               COUNT(*) AS faculty_publication_associations,
               COUNT(DISTINCT p.id) FILTER (
                   WHERE {year_expr} IS NULL
               ) AS publications_without_known_year
        FROM m2_publications p
        JOIN m2_faculty_publications fp ON fp.publication_id = p.id
        JOIN m2_faculties f ON f.id = fp.faculty_id
        WHERE {' AND '.join(where)}
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()

    return {
        "unique_publications": row[0],
        "faculty_publication_associations": row[1],
        "publications_without_known_year": row[2],
    }


def fetch_publication_list(faculty_id=None, faculty_ids=None, year_range=None,
                           limit=5, recent_year_window=False):
    """
    Fetch publication records directly from PostgreSQL.

    If recent_year_window=True, use the five latest distinct publication years
    represented in the selected scope. Rows with missing/invalid years are
    not silently classified as recent.
    """
    year_expr = _year_sql("p.publication_year")
    conditions = ["f.is_active IS DISTINCT FROM FALSE"]
    params = []

    scope_ids = list(faculty_ids) if faculty_ids else (
        [faculty_id] if faculty_id is not None else None
    )
    if scope_ids:
        conditions.append("fp.faculty_id = ANY(%s)")
        params.append(scope_ids)

    if year_range:
        conditions.append(f"{year_expr} BETWEEN %s AND %s")
        params.extend(year_range)

    recent_cte = ""
    recent_join = ""

    if recent_year_window and not year_range:
        recent_cte = f"""
            WITH selected_years AS (
                SELECT DISTINCT {year_expr} AS pub_year
                FROM m2_publications p
                JOIN m2_faculty_publications fp
                    ON fp.publication_id = p.id
                JOIN m2_faculties f ON f.id = fp.faculty_id
                WHERE f.is_active IS DISTINCT FROM FALSE
                  AND {year_expr} IS NOT NULL
                  {"AND fp.faculty_id = ANY(%s)" if scope_ids else ""}
                ORDER BY pub_year DESC
                LIMIT 5
            )
        """
        if scope_ids:
            # The CTE placeholder appears before main-query placeholders.
            params = [scope_ids] + params
        recent_join = (
            f"JOIN selected_years sy ON sy.pub_year = {year_expr}"
        )
        conditions.append(f"{year_expr} IS NOT NULL")

    sql = f"""
        {recent_cte}
        SELECT DISTINCT
               p.id,
               p.title,
               p.publication_type,
               p.journal_or_conference,
               p.publisher,
               {year_expr} AS publication_year,
               p.publication_date,
               p.volume,
               p.issue,
               p.pages,
               p.doi,
               p.authors,
               p.source_url,
               p.source_document
        FROM m2_publications p
        JOIN m2_faculty_publications fp ON fp.publication_id = p.id
        JOIN m2_faculties f ON f.id = fp.faculty_id
        {recent_join}
        WHERE {' AND '.join(conditions)}
        ORDER BY publication_year DESC NULLS LAST,
                 p.publication_date DESC NULLS LAST,
                 p.id DESC
        LIMIT %s
    """
    params.append(limit)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    results = []
    for row in rows:
        (pub_id, title, pub_type, venue, publisher, year, publication_date,
         volume, issue, pages, doi, authors, source_url, source_document) = row
        results.append({
            "id": pub_id,
            "title": title or "(Untitled publication)",
            "publication_type": pub_type,
            "venue": venue,
            "publisher": publisher,
            "year": year,
            "publication_date": publication_date,
            "volume": volume,
            "issue": issue,
            "pages": pages,
            "doi": doi,
            "authors": authors,
            "source_url": source_url,
            "source_document": source_document,
            "faculty_name": None,
        })
    return results


def print_publications(publications):
    if not publications:
        print("No publication records matched that request.")
        return

    for index, item in enumerate(publications, start=1):
        print(f"\n{index}. {item['title']}")
        details = []
        if item["publication_date"] is not None:
            details.append(f"Published: {item['publication_date']}")
        elif item["year"] is not None:
            details.append(f"Publication year: {item['year']} (exact date not recorded)")
        if item["venue"]:
            details.append(str(item["venue"]))
        if item["publication_type"]:
            details.append(str(item["publication_type"]))
        if details:
            print("   " + " | ".join(details))
        if item["authors"]:
            print(f"   Authors: {item['authors']}")
        if item["doi"]:
            print(f"   DOI: {item['doi']}")
        source = item["source_url"] or item["source_document"]
        if source:
            print(f"   Source: {source}")


def run_analytics(question, faculty_id=None, faculty_ids=None,
                  faculty_name=None, department_wide=False):
    """Handle exact publication counts and ordered publication lists."""
    year_range = extract_year_range(question)
    q = question.lower()
    is_count = asks_publication_count(question)
    is_latest = asks_latest_publications(question)
    is_list = asks_publication_list(question)

    if not (is_count or is_latest or is_list):
        return False

    if is_count:
        counts = publication_count(
            faculty_id=None if department_wide else faculty_id,
            faculty_ids=None if department_wide else faculty_ids,
            year_range=year_range,
        )
        scope = (
            "active CSED faculty profiles"
            if department_wide
            else faculty_name
            if faculty_name
            else "CSED faculty profiles"
        )
        period = (
            f" from {year_range[0]} to {year_range[1]}"
            if year_range else ""
        )
        if department_wide:
            range_label = (
                f"the period {year_range[0]}–{year_range[1]}"
                if year_range else "the available database period"
            )
            print(
                f"\nFor {range_label}, the database does not independently "
                "verify publications published by CSED itself. The count below "
                "covers publication records linked to active CSED faculty profiles."
            )
        print(
            f"Publication count associated with {scope}{period}: "
            f"{counts['unique_publications']} unique publication records."
        )
        print(
            "- Faculty-publication associations: "
            f"{counts['faculty_publication_associations']}"
        )
        if not year_range:
            print(
                "- Records without a usable publication year/date: "
                f"{counts['publications_without_known_year']}"
            )
        print(
            "Unique publication records count each database record once; "
            "faculty-publication associations count faculty-to-publication links. "
            "A co-authored paper may have multiple faculty associations. "
            "Year-range counts use a valid structured year, falling back to "
            "publication_date when available. "
            + (
                "Records without a usable year/date are excluded from this range."
                if year_range
                else "The total includes records with unknown years."
            )
        )
        return True

    asks_for_one_latest = (
        bool(re.search(r"\b(latest|newest|most recent)\s+one\b", q))
        or ("latest publication" in q and "publications" not in q)
    )
    limit = 1 if asks_for_one_latest else requested_limit(question, default=5)
    use_recent_window = (
        any(word in q for word in ("recent", "latest", "newest"))
        and year_range is None
    )

    publications = fetch_publication_list(
        faculty_id=None if department_wide else faculty_id,
        faculty_ids=None if department_wide else faculty_ids,
        year_range=year_range,
        limit=limit,
        recent_year_window=use_recent_window,
    )

    if department_wide:
        print("\nPublication records associated with active CSED faculty:")
    elif faculty_name:
        print(f"\nPublications for {faculty_name}:")

    if use_recent_window:
        print(
            "Sorted by recorded publication year, then exact publication date "
            "where available. Records without an exact date are shown with "
            "their year only; their order within that year cannot be confirmed."
        )
    if year_range:
        print(f"Publication-year range requested: {year_range[0]}–{year_range[1]}.")
    print_publications(publications)
    return True



def run_combined_recent_query(question, faculty_name=None, faculty_ids=None,
                              faculty_id=None):
    """
    For mixed requests such as "research areas and recent publications",
    fetch recent publications by structured year and retrieve other sections
    separately so the publication list does not crowd out the other section.
    """
    q = question.lower()
    requested = detect_requested_sections(question)
    has_recent_intent = any(
        term in q for term in ("recent", "latest", "newest", "most recent")
    )
    if (
        not has_recent_intent
        or "publications" not in requested
        or not any(section != "publications" for section in requested)
    ):
        return False

    other_sections = [section for section in requested if section != "publications"]
    other_results = faculty_search(
        question,
        top_k=TOP_K,
        faculty_name=faculty_name,
        sections=other_sections,
    )

    publications = fetch_publication_list(
        faculty_id=faculty_id,
        faculty_ids=faculty_ids,
        limit=requested_limit(question, default=5),
        recent_year_window=True,
    )

    evidence = []
    for item in other_results:
        evidence.append({
            "faculty": item.get("faculty_name") or faculty_name,
            "section": item.get("section"),
            "title": item.get("title"),
            "information": (
                item.get("content") or item.get("text")
                or item.get("information") or item.get("details")
            ),
            "source_url": (
                item.get("source_url") or item.get("source")
                or item.get("url")
            ),
            "retrieved_record": item,
        })
    for item in publications:
        evidence.append({
            "faculty": faculty_name,
            "section": "publications",
            "title": item.get("title"),
            "information": {
                "authors": item.get("authors"),
                "publication_type": item.get("publication_type"),
                "venue": item.get("venue"),
                "publisher": item.get("publisher"),
                "year": item.get("year"),
                "publication_date": item.get("publication_date"),
                "doi": item.get("doi"),
            },
            "source_url": item.get("source_url") or item.get("source_document"),
        })

    print("\n" + generate_faculty_answer(
        question,
        evidence,
        faculty_name=faculty_name,
    ))
    print_sources(evidence)
    return True


def should_reuse_faculty_context(question, status, department_wide):
    if status != "none" or department_wide:
        return False
    q = question.lower()
    followup_signals = (
        "his ", "her ", "their ", "he ", "she ", "them ",
        "those ", "these ", "that professor", "this professor",
        "his'", "her'", "what about", "how many", "latest",
        "recent", "achievements", "publications", "research areas",
        "education", "courses", "thesis", "supervision",
    )
    return any(signal in q for signal in followup_signals)


def print_sources(evidence):
    """Print unique source URLs associated with retrieved evidence."""
    sources = []
    seen = set()
    for item in evidence:
        url = item.get("source_url")
        if isinstance(url, str) and url.startswith(("https://", "http://")):
            if url not in seen:
                seen.add(url)
                sources.append(url)
    if sources:
        print("\nSources:")
        for index, url in enumerate(sources, start=1):
            print(f"[{index}] {url}")


def interactive_session():
    """Keep corpus, embeddings, faculty context, and short history in memory."""
    print("Loading Module II faculty data and embedding cache...")
    count = ensure_corpus_loaded()
    # ensure_corpus_loaded currently returns None; use the loaded module state
    # to report the actual count without reloading data.
    import importlib
    retrieval_module = importlib.import_module(
        "module2.retrieval.faculty_search"
    )
    count = len(retrieval_module._records or [])
    print(f"Ready. Searchable records loaded: {count}")
    print("Ask questions continuously. Type 'exit' or 'quit' to stop.")
    print("Commands: /context shows the current faculty; /reset clears context.\n")

    active_faculty_id = None
    active_faculty_ids = None
    active_faculty_name = None
    history = deque(maxlen=HISTORY_LIMIT)

    while True:
        try:
            question = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSession ended.")
            break

        if not question:
            continue
        command = question.lower()

        if command in {"exit", "quit"}:
            print("Session ended.")
            break
        if command == "/context":
            print(f"Current faculty: {active_faculty_name or 'none'}")
            print("Recent turns:")
            if not history:
                print("- No questions yet.")
            for old_question, _ in history:
                print(f"- {old_question}")
            continue
        if command == "/reset":
            active_faculty_id = None
            active_faculty_ids = None
            active_faculty_name = None
            history.clear()
            print("Conversation context cleared.")
            continue

        department_wide = is_department_wide_question(question)
        resolved_ids, explicit_name, status = resolve_faculty(
            question, _get_records()
        )

        if status == "ambiguous":
            print("That faculty name is ambiguous. Please use the full name.")
            continue
        if status == "unresolved":
            print("I could not match that name to the Module II faculty records.")
            continue

        if status == "matched":
            # Resolve the matching IDs, not just a display name. The existing
            # resolver handles duplicate directory records with the same name.
            active_faculty_ids = set(resolved_ids)
            active_faculty_id = (
                next(iter(active_faculty_ids))
                if len(active_faculty_ids) == 1 else None
            )
            active_faculty_name = explicit_name
        elif department_wide:
            active_faculty_id = None
            active_faculty_ids = None
            active_faculty_name = None
        elif active_faculty_name and should_reuse_faculty_context(
            question, status, department_wide
        ):
            pass
        else:
            # Do not carry old faculty context into an unrelated broad query.
            active_faculty_id = None
            active_faculty_ids = None
            active_faculty_name = None

        previous_question = history[-1][0].lower() if history else ""
        effective_question = question
        if (
            any(term in command for term in ("latest", "most recent", "newest"))
            and any(term in command for term in ("one", "ones", "it", "them"))
            and any(term in previous_question for term in ("publication", "paper"))
        ):
            effective_question = question + " publications"

        history.append((question, active_faculty_name))

        if run_combined_recent_query(
            effective_question,
            faculty_name=active_faculty_name,
            faculty_ids=active_faculty_ids,
            faculty_id=active_faculty_id,
        ):
            continue

        if run_analytics(
            effective_question,
            faculty_id=active_faculty_id,
            faculty_ids=active_faculty_ids,
            faculty_name=active_faculty_name,
            department_wide=department_wide,
        ):
            continue

        # Preserve current retrieval behavior, but pass the active faculty
        # name on a follow-up so records from other faculty cannot leak in.
        results = faculty_search(
            question,
            top_k=TOP_K,
            faculty_name=active_faculty_name,
        )

        evidence = []
        for item in results:
            evidence.append({
                "faculty": item.get("faculty_name") or active_faculty_name,
                "section": item.get("section"),
                "title": item.get("title"),
                "information": (
                    item.get("content") or item.get("text")
                    or item.get("information") or item.get("details")
                ),
                "source_url": (
                    item.get("source_url") or item.get("source")
                    or item.get("url")
                ),
                "retrieved_record": item,
            })

        print("\n" + generate_faculty_answer(
            question,
            evidence,
            faculty_name=active_faculty_name,
        ))
        print_sources(evidence)

        requested = detect_requested_sections(question)
        returned = {item["section"] for item in results}
        missing = [section for section in requested if section not in returned]
        if missing:
            print("Evidence was not retrieved for: " + ", ".join(missing))



def _get_records():
    # Access the already-loaded corpus; do not refetch or re-embed per turn.
    import importlib
    retrieval_module = importlib.import_module(
        "module2.retrieval.faculty_search"
    )
    if retrieval_module._records is None:
        retrieval_module.ensure_corpus_loaded()
    return retrieval_module._records or []


if __name__ == "__main__":
    try:
        interactive_session()
    except Exception as exc:
        print(f"Faculty assistant failed: {exc}")

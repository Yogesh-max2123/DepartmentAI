"""Temporary standalone web UI for the existing Module II faculty assistant.

Run from the DepartmentAI project root:
    python -m module2.chatbot_ui.server

This server listens on port 8001 and does not modify the main FastAPI app.
"""
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from module2.authorization import require_module2_permission

app = FastAPI(
    title="DepartmentAI Module II Temporary Chatbot",
    description="A temporary browser interface for Module II CSED faculty information.",
    version="0.1.0",
)

UI_FILE = Path(__file__).with_name("index.html")


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    faculty_context: Optional[str] = Field(default=None, max_length=200)


class ChatResponse(BaseModel):
    answer: str
    faculty_context: Optional[str] = None
    sources: list[dict] = []


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(UI_FILE)


@app.get("/health")
def health():
    return {"status": "ok", "service": "DepartmentAI Module II temporary chatbot"}


@app.post(
    "/api/chat",
    response_model=ChatResponse,
    dependencies=[Depends(require_module2_permission("module2.faculty.chat"))],
)
def chat(request: ChatRequest):
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Please enter a question.")

    try:
        from module2.retrieval import faculty_search as retrieval
        from module2.retrieval.faculty_gemini import generate_faculty_answer
        from module2.retrieval.faculty_assistant import (
            is_csed_faculty_related_question,
            is_explicitly_department_wide_question,
            extract_year_range,
            asks_publication_count,
            publication_count,
        )

        # Route exact aggregate questions to PostgreSQL BEFORE faculty-name
        # resolution or semantic retrieval. This avoids rejecting department-wide
        # count questions and avoids presenting a partial RAG result as a total.
        from module2.database.connection import get_connection

        q_lower = question.lower()
        count_intent = any(term in q_lower for term in (
            "how many", "number of", "count of", "count the",
            "total number", "total count", "how much",
        ))
        faculty_terms = ("faculty", "faculties", "professor", "professors", "academic staff")
        asks_faculty_count = count_intent and any(term in q_lower for term in faculty_terms)

        if asks_faculty_count:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT COUNT(*) FROM m2_faculties "
                        "WHERE is_active IS DISTINCT FROM FALSE"
                    )
                    faculty_total = int(cur.fetchone()[0] or 0)
            return ChatResponse(
                answer=(
                    f"The Module II database currently contains {faculty_total} active CSED faculty records. "
                    "This is the stored database count; the last verified official-directory discovery found "
                    "46 entries, so the directory/database difference should be reviewed separately."
                ),
                sources=[],
            )

        if asks_publication_count(question):
            year_range = extract_year_range(question)
            counts = publication_count(year_range=year_range)
            if year_range:
                period = f"between {year_range[0]} and {year_range[1]} inclusive"
                count_value = counts["unique_publications"]
                answer = (
                    f"The Module II database contains {count_value} unique publication records associated "
                    f"with active CSED faculty {period}. There are {counts['faculty_publication_associations']} "
                    "faculty-publication associations for those records; this association count can be higher "
                    "than the unique-publication count when a publication is linked to multiple faculty members. "
                    "The result uses the stored publication year, falling back to the publication date year "
                    "when the structured year is unavailable or invalid. It counts database records, not a "
                    "fresh live scrape of the department website."
                )
            else:
                answer = (
                    f"The Module II database contains {counts['unique_publications']} unique publication records "
                    f"associated with active CSED faculty. There are {counts['faculty_publication_associations']} "
                    "faculty-publication associations. Co-authored publications can have multiple associations."
                )
            return ChatResponse(answer=answer, sources=[])

        # Reuse the already-built Module II corpus/cache; do not re-ingest data.
        retrieval.ensure_corpus_loaded()
        records = retrieval._records or []
        if not records:
            return ChatResponse(
                answer=(
                    "The Module II faculty retrieval corpus is empty. Please verify "
                    "that the existing faculty ingestion and retrieval setup is available."
                )
            )

        resolved_ids, resolved_name, status = retrieval.resolve_faculty(question, records)
        active_context = None

        if status == "ambiguous":
            return ChatResponse(
                answer="That faculty name is ambiguous in the current dataset. Please use the faculty member's full name."
            )
        if status == "unresolved":
            return ChatResponse(
                answer=(
                    "I could not match that name to the Module II MNNIT CSED faculty records. "
                    "Please check the name or ask about a faculty member listed in the department records."
                )
            )

        if status == "matched":
            # A new explicit faculty name replaces the previous conversational context.
            active_context = resolved_name
        elif request.faculty_context:
            # Reuse the prior faculty context only for a follow-up without a new match.
            context_ids, context_name, context_status = retrieval.resolve_faculty(
                "", records, faculty_name=request.faculty_context
            )
            if context_status == "matched":
                active_context = context_name

        department_wide = is_explicitly_department_wide_question(question)
        if not active_context and not department_wide and not is_csed_faculty_related_question(
            question, has_faculty_context=False
        ):
            return ChatResponse(
                answer=(
                    "I can help with MNNIT CSED faculty records, including profiles, "
                    "education, research areas, teaching, publications, and thesis supervision. "
                    "Please ask a question related to that dataset."
                )
            )

        search_faculty = None if department_wide else active_context
        results = retrieval.faculty_search(
            question,
            top_k=retrieval.TOP_K,
            faculty_name=search_faculty,
        )

        evidence = []
        sources = []
        seen_sources = set()
        for item in results:
            source_url = item.get("source_url") or item.get("source") or item.get("url")
            evidence.append({
                "faculty": item.get("faculty_name") or active_context,
                "section": item.get("section"),
                "title": item.get("title"),
                "information": (
                    item.get("content") or item.get("text")
                    or item.get("information") or item.get("details")
                ),
                "source_url": source_url,
                "retrieved_record": item,
            })
            if source_url and source_url not in seen_sources:
                seen_sources.add(source_url)
                sources.append({
                    "title": item.get("title") or item.get("section") or "Source record",
                    "url": source_url,
                    "faculty": item.get("faculty_name") or active_context or "CSED faculty",
                })

        answer = generate_faculty_answer(
            question,
            evidence,
            faculty_name=search_faculty,
        )
        if not results:
            answer = (
                "I couldn't retrieve matching evidence from the Module II faculty dataset. "
                "Try a more specific question or verify the faculty name."
            )

        return ChatResponse(
            answer=answer,
            faculty_context=active_context,
            sources=sources[:8],
        )
    except Exception as exc:
        # Keep implementation details out of the browser response; details remain in server logs.
        print(f"[Module II temporary chatbot] Request failed: {type(exc).__name__}: {exc}")
        raise HTTPException(
            status_code=500,
            detail=(
                "The chatbot could not process this question. Check the terminal for the error; "
                "verify the database connection, existing Module II retrieval cache, and GEMINI_API_KEY."
            ),
        ) from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("module2.chatbot_ui.server:app", host="127.0.0.1", port=8001, reload=False)

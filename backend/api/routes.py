from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.rag.qa_pipeline import answer_question
from backend.rag.source_formatter import format_sources


router = APIRouter()


class AskRequest(BaseModel):
    question: str
    conversation_history: list[dict] = []
    role: str | None = None
    programme: str | None = None


class AskResponse(BaseModel):
    answer: str
    sources: list


@router.post("/ask", response_model=AskResponse)
def ask_question(request: AskRequest):
    try:
        answer, results = answer_question(
            request.question,
            request.conversation_history,
            role=request.role,
            programme=request.programme,
        )

        role_key = (request.role or "").strip().upper()
        sources = [] if role_key == "STUDENT" else format_sources(results)

        return {
            "answer": answer,
            "sources": sources,
        }

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

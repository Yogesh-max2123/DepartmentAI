"""
FastAPI routes for the Meeting Scheduling Agent.

POST /schedule/propose  find slots and send the WhatsApp proposal
POST /schedule/approve  HoD consent, then official email + .ics invite
GET  /schedule/proposals
GET  /schedule/proposals/{proposal_id}
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.agents.scheduling_agent import (
    approve_meeting,
    get_proposal,
    list_proposals,
    propose_meeting,
)


router = APIRouter(prefix="/schedule", tags=["scheduling"])


class ProposeRequest(BaseModel):
    committee_name: str = Field(
        ...,
        description="DUGC, DMPC or DDPC.",
        examples=["DDPC"],
    )
    date_range: str = Field(
        ...,
        description="Inclusive range, e.g. '2026-09-14 to 2026-09-25'.",
        examples=["2026-09-14 to 2026-09-25"],
    )
    agenda: str = Field(
        ...,
        description="Proposed meeting agenda.",
    )
    duration_minutes: int = Field(60, ge=30, le=180)
    use_gemini: bool = Field(
        True,
        description="If false, skip Gemini and run tools deterministically.",
    )


class ApproveRequest(BaseModel):
    proposal_id: str
    approved: bool = True
    slot_index: int | None = Field(
        default=None,
        description="1-based index into the proposed slots. Defaults to 1.",
        ge=1,
        le=3,
    )
    hod_comment: str = ""
    use_gemini: bool = True


@router.post("/propose")
def schedule_propose(request: ProposeRequest):
    try:
        return propose_meeting(
            committee_name=request.committee_name,
            date_range=request.date_range,
            agenda=request.agenda,
            duration_minutes=request.duration_minutes,
            use_gemini=request.use_gemini,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                f"{exc} Generate scheduler data first: "
                "python ai/ingestion/synthetic_scheduler_data.py"
            ),
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/approve")
def schedule_approve(request: ApproveRequest):
    try:
        return approve_meeting(
            proposal_id=request.proposal_id,
            slot_index=request.slot_index,
            approved=request.approved,
            hod_comment=request.hod_comment,
            use_gemini=request.use_gemini,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/proposals")
def schedule_list_proposals():
    return {"ok": True, "proposals": list_proposals()}


@router.get("/proposals/{proposal_id}")
def schedule_get_proposal(proposal_id: str):
    record = get_proposal(proposal_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown proposal_id: {proposal_id}",
        )
    return {"ok": True, "proposal": record}


import os
import datetime
from pydantic import BaseModel


class MinutesRequest(BaseModel):
    proposal_id: str
    context_text: str


def _fallback_minutes_body(context_text: str) -> str:
    excerpt = (context_text or "").strip().replace("\n", " ")
    if len(excerpt) > 280:
        excerpt = excerpt[:280].rstrip() + "..."
    return (
        "**1. Approved Agenda:**\n"
        "To consider the doctoral case placed before the Departmental Doctoral "
        "Programme Committee (DDPC) in light of the retrieved ordinance context "
        "and the Recommendation Agent draft resolution.\n\n"
        "**2. Notes & Member Observations:**\n"
        "- The HoD noted that the matter concerns Ph.D. academic processes "
        "under the Doctoral Ordinances, 2023, and must remain subject to human verification.\n"
        "- The Convener observed deficiencies and cited clauses from the retrieved "
        f"institutional context: {excerpt or 'context not supplied.'}\n"
        "- Members recalled that Comprehensive Examination, supervisor allocation, "
        "thesis extension and similar items are decided by DDPC / SDPC, not by the AI system.\n\n"
        "**3. Final Decisions:**\n"
        "- The committee adopted the Initial draft resolution from the Recommendation "
        "Agent as a working draft for human review.\n"
        "- The recommendation shall be forwarded through Convener DDPC and the Head "
        "of Department as required by the Doctoral Ordinances.\n"
    )


def _generate_minutes_text(context_text: str) -> str:
    prompt = f"""
    You are the Secretary of the Departmental Doctoral Programme Committee (DDPC).
    Based on the following AI-generated resolution and case context, draft professional meeting minutes.

    Context of the case:
    {context_text}

    Please structure the minutes with these exact 3 headings:
    **1. Approved Agenda:** (Create a 1-sentence formal agenda based on the case)
    **2. Notes & Member Observations:** (Create 2-3 logical points discussed by the HoD and Convener based on the rules and deficiencies mentioned in the context)
    **3. Final Decisions:** (State the final recommendation strictly based on the 'Initial draft resolution' from the context)

    Keep it concise, formal, and use bullet points for sections 2 and 3. Do not add any extra introductory text.
    """
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return _fallback_minutes_body(context_text)

    try:
        from backend.llm.gemini_client import generate_text

        text = generate_text(prompt)
        if text:
            return text
    except Exception:
        pass

    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=prompt,
        )
        if getattr(response, "text", None):
            return response.text
    except Exception:
        pass

    return _fallback_minutes_body(context_text)


@router.post("/minutes/generate")
async def generate_minutes(req: MinutesRequest):
    body = _generate_minutes_text(req.context_text)
    draft_minutes = (
        f"**DRAFT MINUTES OF MEETING**\n"
        f"**Ref:** {req.proposal_id}\n"
        f"**Date:** {datetime.datetime.now().strftime('%Y-%m-%d')}\n\n"
        f"{body}\n\n"
        f"*(System Note: Draft minutes circulated for member review and securely stored in documents/scheduler/processed/)*"
    )

    os.makedirs("documents/scheduler/processed", exist_ok=True)
    file_path = f"documents/scheduler/processed/{req.proposal_id}_minutes.md"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(draft_minutes)

    return {"status": "success", "minutes": draft_minutes, "file_path": file_path}
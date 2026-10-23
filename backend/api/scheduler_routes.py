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
        examples=["DMPC"],
    )
    date_range: str = Field(
        ...,
        description="Inclusive range, e.g. '2026-09-07 to 2026-09-18'.",
        examples=["2026-09-07 to 2026-09-18"],
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


import google.generativeai as genai
import os
import datetime
from pydantic import BaseModel
# (Ensure your router is imported as before)

# Ensure Gemini is configured
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

class MinutesRequest(BaseModel):
    proposal_id: str
    context_text: str  # <--- Naya field jo frontend se RAG ka data receive karega

@router.post("/minutes/generate")
async def generate_minutes(req: MinutesRequest):
    # Prompt Gemini to generate dynamic minutes based on the RAG context
    prompt = f"""
    You are the Secretary of the Departmental M.Tech. Programme Committee (DMPC).
    Based on the following AI-generated resolution and case context, draft professional meeting minutes.
    
    Context of the case:
    {req.context_text}
    
    Please structure the minutes with these exact 3 headings:
    **1. Approved Agenda:** (Create a 1-sentence formal agenda based on the case)
    **2. Notes & Member Observations:** (Create 2-3 logical points discussed by the HoD and Convener based on the rules and deficiencies mentioned in the context)
    **3. Final Decisions:** (State the final recommendation strictly based on the 'Initial draft resolution' from the context)
    
    Keep it concise, formal, and use bullet points for sections 2 and 3. Do not add any extra introductory text.
    """
    
    # Call Gemini AI
    model = genai.GenerativeModel('gemini-3.5-flash-lite')
    response = model.generate_content(prompt)
    
    # Format the final output
    draft_minutes = (
        f"**DRAFT MINUTES OF MEETING**\n"
        f"**Ref:** {req.proposal_id}\n"
        f"**Date:** {datetime.datetime.now().strftime('%Y-%m-%d')}\n\n"
        f"{response.text}\n\n"
        f"*(System Note: Draft minutes circulated for member review and securely stored in documents/scheduler/processed/)*"
    )
    
    # Secure storage
    os.makedirs("documents/scheduler/processed", exist_ok=True)
    file_path = f"documents/scheduler/processed/{req.proposal_id}_minutes.md"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(draft_minutes)
        
    return {"status": "success", "minutes": draft_minutes, "file_path": file_path}
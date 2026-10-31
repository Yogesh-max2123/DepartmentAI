from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from backend.rag.programme import committee_name, normalize_programme, ordinance_title, programme_label
from backend.workflow import store
from backend.workflow.auth import authenticate, issue_token, public_user, resolve_token
from backend.workflow.verify import extract_pdf_text, verify_documents


router = APIRouter(prefix="/api", tags=["workflow"])
bearer = HTTPBearer(auto_error=False)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
UPLOAD_ROOT = PROJECT_ROOT / "documents" / "uploads"

def _fallback_draft(programme: str | None = None) -> str:
    label = programme_label(programme)
    committee = committee_name(programme)
    title = ordinance_title(programme)
    return f"""**Relevant ordinance clauses**
- Retrieved ordinance context was insufficient or blocked by scope guardrails. Edit this draft using the {title}.

**Similar previous cases (citing the synthetic data)**
- No similar case was attached by the Recommendation Agent.

**Identified deficiencies**
- Confirm supporting documents and unmet academic conditions against the ordinance.

**Possible course of action**
- Place the matter before {committee} for human verification.
- Seek additional documents from the scholar if required.

**Initial draft resolution**
The Departmental {label} Programme Committee ({committee}) may consider the scholar's request subject to verification of documents and applicable clauses of the {title}. This draft is not a final approval.
"""


FALLBACK_DRAFT = _fallback_draft("phd")


class LoginRequest(BaseModel):
    email: str
    password: str


class ProfileUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    department: str | None = None
    programme: str | None = None


class ApplicationCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=512)
    description: str = Field(..., min_length=10)
    application_type: str = "general"


class DraftUpdate(BaseModel):
    draft_resolution: str = Field(..., min_length=10)


class ProposeRequest(BaseModel):
    date_range: str = "2026-09-14 to 2026-09-25"
    duration_minutes: int = Field(60, ge=30, le=180)
    use_gemini: bool = False


class ApproveRequest(BaseModel):
    slot_index: int = Field(1, ge=1, le=3)
    hod_comment: str = ""
    use_gemini: bool = False


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    authorization: Annotated[str | None, Header()] = None,
) -> dict:
    token = None
    if credentials and credentials.credentials:
        token = credentials.credentials
    elif authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    user = resolve_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")
    return user


def require_role(user: dict, *roles: str) -> None:
    if user["role"] not in roles:
        raise HTTPException(status_code=403, detail="Not permitted for this role.")


def can_view(user: dict, app: dict) -> bool:
    if user["role"] in ("OFFICIAL", "COMMITTEE_DDPC"):
        return True
    return app["student_id"] == user["id"]


def _safe_filename(name: str) -> str:
    base = Path(name or "document.pdf").name
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("._")
    return cleaned or "document.pdf"


def application_programme(app: dict) -> str:
    student = app.get("student") or {}
    raw = student.get("programme") or app.get("programme")
    if not raw:
        student_id = app.get("student_id")
        if student_id:
            user = store.get_user_by_id(student_id)
            if user:
                raw = user.get("programme")
    return normalize_programme(raw)


def _draft_stub(description: str, programme: str | None = None) -> str:
    excerpt = re.sub(r"\s+", " ", description).strip()
    if len(excerpt) > 400:
        excerpt = excerpt[:400] + "..."
    return (
        _fallback_draft(programme)
        + f"\n\nCase summary provided by the scholar:\n{excerpt}"
    )


def generate_draft_resolution(description: str, programme: str | None = None) -> str:
    programme_key = normalize_programme(programme)
    try:
        from backend.rag.qa_pipeline import answer_question

        answer, _results = answer_question(
            description,
            [],
            role="OFFICIAL",
            programme=programme_key,
        )
        if answer and "initial draft resolution" in answer.lower():
            return answer
        if answer and len(answer.strip()) > 40:
            return answer
    except Exception:
        pass
    try:
        from backend.llm.gemini_client import generate_answer

        return generate_answer(
            description,
            description,
            role="OFFICIAL",
            programme=programme_key,
        )
    except Exception:
        return _draft_stub(description, programme_key)


@router.post("/auth/login")
def login(payload: LoginRequest):
    user = authenticate(payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    token = issue_token(user)
    return {"token": token, "user": public_user(user)}


@router.get("/auth/me")
def me(user: dict = Depends(current_user)):
    return {"user": public_user(user)}


@router.put("/auth/profile")
def update_profile(payload: ProfileUpdate, user: dict = Depends(current_user)):
    updated = store.update_user(
        user["id"],
        full_name=payload.full_name,
        phone=payload.phone,
        department=payload.department,
        programme=payload.programme,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="User not found.")
    return {"user": public_user(updated)}


@router.post("/auth/profile/photo")
async def upload_profile_photo(
    file: UploadFile = File(...),
    user: dict = Depends(current_user),
):
    allowed = {"image/jpeg", "image/png", "image/webp", "image/gif"}
    content_type = (file.content_type or "").lower()
    if content_type not in allowed:
        raise HTTPException(status_code=400, detail="Upload a JPEG, PNG, WebP, or GIF photo.")
    dest_dir = PROJECT_ROOT / "frontend" / "uploads" / "profiles"
    dest_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "photo.png").suffix.lower() or ".png"
    if suffix not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        suffix = ".png"
    dest = dest_dir / f"user_{user['id']}{suffix}"
    with dest.open("wb") as handle:
        shutil.copyfileobj(file.file, handle)
    photo_url = f"/uploads/profiles/{dest.name}"
    updated = store.update_user(user["id"], photo_url=photo_url)
    return {"user": public_user(updated), "photo_url": photo_url}


@router.get("/meta")
def meta():
    return {
        "application_types": store.APPLICATION_TYPES,
        "statuses": store.STATUSES,
        "workflow_db": store.dialect(),
    }


@router.get("/applications")
def list_apps(user: dict = Depends(current_user)):
    return {"applications": store.list_applications(user)}


@router.post("/applications")
def create_app(payload: ApplicationCreate, user: dict = Depends(current_user)):
    require_role(user, "STUDENT")
    app = store.create_application(
        student_id=user["id"],
        title=payload.title,
        description=payload.description,
        application_type=payload.application_type,
    )
    return {"application": store.application_detail(app["id"])}


@router.get("/applications/{app_id}")
def get_app(app_id: int, user: dict = Depends(current_user)):
    app = store.application_detail(app_id)
    if app is None:
        raise HTTPException(status_code=404, detail="Application not found.")
    if not can_view(user, app):
        raise HTTPException(status_code=403, detail="Not permitted.")
    return {"application": app}


@router.post("/applications/{app_id}/documents")
async def upload_documents(
    app_id: int,
    files: list[UploadFile] = File(...),
    user: dict = Depends(current_user),
):
    require_role(user, "STUDENT")
    app = store.get_application(app_id)
    if app is None:
        raise HTTPException(status_code=404, detail="Application not found.")
    if app["student_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Not permitted.")
    if app["status"] != "DRAFT":
        raise HTTPException(status_code=400, detail="Documents can only be uploaded in DRAFT.")
    saved = []
    dest_dir = UPLOAD_ROOT / str(app_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    for upload in files:
        filename = _safe_filename(upload.filename or "document.pdf")
        dest = dest_dir / filename
        counter = 1
        while dest.exists():
            dest = dest_dir / f"{dest.stem}_{counter}{dest.suffix}"
            counter += 1
        with dest.open("wb") as handle:
            shutil.copyfileobj(upload.file, handle)
        extracted = ""
        if dest.suffix.lower() == ".pdf":
            extracted = extract_pdf_text(dest)
        else:
            try:
                extracted = dest.read_text(encoding="utf-8", errors="ignore")[:8000]
            except Exception:
                extracted = ""
        record = store.add_document(
            app_id,
            dest.name,
            str(dest.relative_to(PROJECT_ROOT)),
            upload.content_type or "application/pdf",
            extracted,
        )
        saved.append(
            {
                "id": record["id"],
                "filename": record["filename"],
                "stored_path": record["stored_path"],
                "text_length": len(extracted or ""),
            }
        )
    return {"ok": True, "documents": saved, "application": store.application_detail(app_id)}


@router.post("/applications/{app_id}/submit")
def submit_app(app_id: int, user: dict = Depends(current_user)):
    require_role(user, "STUDENT")
    app = store.get_application(app_id)
    if app is None:
        raise HTTPException(status_code=404, detail="Application not found.")
    if app["student_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Not permitted.")
    if app["status"] != "DRAFT":
        raise HTTPException(status_code=400, detail="Only DRAFT applications can be submitted.")
    docs = store.list_documents(app_id)
    filenames = [item["filename"] for item in docs]
    extracted = store.combined_extracted_text(app_id)
    result = verify_documents(app["application_type"], app["description"], extracted, filenames)
    store.update_application(
        app_id,
        verification_result=result,
        missing_documents=result.get("missing_documents") or [],
    )
    if not result.get("valid"):
        return {
            "ok": False,
            "verified": False,
            "message": result.get("notes") or "Documents did not match the application type.",
            "missing_documents": result.get("missing_documents") or [],
            "application": store.application_detail(app_id),
        }
    store.set_status(app_id, "DOCS_VERIFIED", user["id"], "AI document verification passed.")
    store.set_status(app_id, "OFFICIAL_REVIEW", user["id"], "Forwarded to departmental official.")
    return {
        "ok": True,
        "verified": True,
        "message": "Documents verified. Application is in official review.",
        "application": store.application_detail(app_id),
    }


@router.post("/applications/{app_id}/draft-resolution")
def create_draft(app_id: int, user: dict = Depends(current_user)):
    require_role(user, "OFFICIAL")
    app = store.get_application(app_id)
    if app is None:
        raise HTTPException(status_code=404, detail="Application not found.")
    if app["status"] not in ("OFFICIAL_REVIEW", "DOCS_VERIFIED"):
        if not app.get("draft_resolution"):
            raise HTTPException(
                status_code=400,
                detail=f"Draft resolution is generated during official review (current: {app['status']}).",
            )
        return {"application": store.application_detail(app_id), "cached": True}
    programme_key = application_programme(app)
    committee = committee_name(programme_key)
    label = programme_label(programme_key)
    question = (
        f"Prepare a {committee} draft resolution for this {label} application.\n"
        f"Type: {app['application_type']}\n"
        f"Title: {app['title']}\n"
        f"Description: {app['description']}"
    )
    draft = generate_draft_resolution(question, programme=programme_key)
    store.update_application(app_id, draft_resolution=draft, official_id=user["id"])
    if app["status"] == "DOCS_VERIFIED":
        store.set_status(app_id, "OFFICIAL_REVIEW", user["id"], "Moved to official review for drafting.")
    return {"application": store.application_detail(app_id), "cached": False}


@router.put("/applications/{app_id}/draft-resolution")
def save_draft(app_id: int, payload: DraftUpdate, user: dict = Depends(current_user)):
    require_role(user, "OFFICIAL")
    app = store.get_application(app_id)
    if app is None:
        raise HTTPException(status_code=404, detail="Application not found.")
    store.update_application(
        app_id,
        draft_resolution=payload.draft_resolution,
        official_id=user["id"],
    )
    return {"application": store.application_detail(app_id)}


@router.post("/applications/{app_id}/schedule/propose")
def propose(app_id: int, payload: ProposeRequest, user: dict = Depends(current_user)):
    require_role(user, "OFFICIAL")
    app = store.get_application(app_id)
    if app is None:
        raise HTTPException(status_code=404, detail="Application not found.")
    if app["status"] != "OFFICIAL_REVIEW":
        raise HTTPException(
            status_code=400,
            detail=f"Meetings can be proposed only from OFFICIAL_REVIEW (current: {app['status']}).",
        )
    from backend.agents.scheduling_agent import get_proposal, propose_meeting

    programme_key = application_programme(app)
    committee = committee_name(programme_key)
    agenda = (
        f"{committee} consideration of application #{app_id}: {app['title']}. "
        f"{(app.get('description') or '')[:240]}"
    )
    packed = propose_meeting(
        committee_name=committee,
        date_range=payload.date_range,
        agenda=agenda,
        duration_minutes=payload.duration_minutes,
        use_gemini=payload.use_gemini,
    )
    proposal = packed.get("proposal") or {}
    proposal_id = proposal.get("proposal_id")
    slots = proposal.get("slots") or []
    if not slots:
        slots = [
            {
                "date": "2026-09-15",
                "weekday": "Tuesday",
                "start": "10:30",
                "end": "11:30",
                "duration_minutes": payload.duration_minutes,
                "timezone": "Asia/Kolkata",
                "venue": "CSE Conference Room",
                "note": "Demo slot (calendar returned no common free time).",
            },
            {
                "date": "2026-09-17",
                "weekday": "Thursday",
                "start": "14:30",
                "end": "15:30",
                "duration_minutes": payload.duration_minutes,
                "timezone": "Asia/Kolkata",
                "venue": "CSE Conference Room",
                "note": "Demo slot (calendar returned no common free time).",
            },
            {
                "date": "2026-09-22",
                "weekday": "Tuesday",
                "start": "11:30",
                "end": "12:30",
                "duration_minutes": payload.duration_minutes,
                "timezone": "Asia/Kolkata",
                "venue": "HoD Chamber",
                "note": "Demo slot (calendar returned no common free time).",
            },
        ]
        proposal["slots"] = slots
        record = get_proposal(proposal_id) if proposal_id else None
        if record is not None:
            record["slots"] = slots
    member_free_windows = (
        (packed.get("slots") or {}).get("member_free_windows")
        or proposal.get("member_free_windows")
        or []
    )
    store.update_application(
        app_id,
        proposal_id=proposal_id,
        proposed_slots=slots,
        member_availability=member_free_windows,
        official_id=user["id"],
    )
    store.set_status(app_id, "MEETING_PROPOSED", user["id"], f"Meeting proposed ({proposal_id}).")
    return {
        "ok": True,
        "proposal_id": proposal_id,
        "slots": slots,
        "member_free_windows": member_free_windows,
        "schedule": packed,
        "application": store.application_detail(app_id),
    }


@router.post("/applications/{app_id}/schedule/approve")
def approve(app_id: int, payload: ApproveRequest, user: dict = Depends(current_user)):
    require_role(user, "COMMITTEE_DDPC")
    app = store.get_application(app_id)
    if app is None:
        raise HTTPException(status_code=404, detail="Application not found.")
    if app["status"] != "MEETING_PROPOSED":
        raise HTTPException(
            status_code=400,
            detail=f"A slot can be approved only in MEETING_PROPOSED (current: {app['status']}).",
        )
    if not app.get("proposal_id"):
        raise HTTPException(status_code=400, detail="No scheduler proposal is attached.")
    from backend.agents.scheduling_agent import approve_meeting

    result = approve_meeting(
        proposal_id=app["proposal_id"],
        slot_index=payload.slot_index,
        approved=True,
        hod_comment=payload.hod_comment,
        use_gemini=payload.use_gemini,
    )
    store.update_application(
        app_id,
        approved_slot=result.get("approved_slot"),
        committee_id=user["id"],
    )
    store.set_status(
        app_id,
        "MEETING_SCHEDULED",
        user["id"],
        f"Slot {payload.slot_index} approved. Official invite dispatched.",
    )
    return {
        "ok": True,
        "schedule": result,
        "application": store.application_detail(app_id),
    }


@router.post("/applications/{app_id}/minutes")
def minutes(app_id: int, user: dict = Depends(current_user)):
    require_role(user, "OFFICIAL")
    app = store.get_application(app_id)
    if app is None:
        raise HTTPException(status_code=404, detail="Application not found.")
    if app["status"] != "MEETING_SCHEDULED":
        raise HTTPException(
            status_code=400,
            detail=f"Minutes are generated after MEETING_SCHEDULED (current: {app['status']}).",
        )
    from backend.api.scheduler_routes import _generate_minutes_text

    context = (
        f"Title: {app['title']}\n"
        f"Type: {app['application_type']}\n"
        f"Description: {app['description']}\n\n"
        f"Draft resolution:\n{app.get('draft_resolution') or ''}\n\n"
        f"Approved slot: {app.get('approved_slot')}"
    )
    programme_key = application_programme(app)
    committee = committee_name(programme_key)
    body = _generate_minutes_text(context, programme=programme_key)
    proposal_id = app.get("proposal_id") or f"APP-{app_id}"
    draft_minutes = (
        f"**DRAFT MINUTES OF MEETING**\n"
        f"**Ref:** {proposal_id} / Application {app_id}\n\n"
        f"{body}\n\n"
        f"*(System Note: Draft minutes generated for {committee} review.)*"
    )
    os.makedirs("documents/scheduler/processed", exist_ok=True)
    file_path = f"documents/scheduler/processed/{proposal_id}_minutes.md"
    with open(file_path, "w", encoding="utf-8") as handle:
        handle.write(draft_minutes)
    summary = body.strip()
    store.update_application(
        app_id,
        minutes_text=draft_minutes,
        final_summary=summary,
        official_id=user["id"],
    )
    store.set_status(app_id, "MINUTES_GENERATED", user["id"], "AI minutes drafted.")
    store.set_status(app_id, "RESOLVED", user["id"], "Case resolved after minutes generation.")
    return {
        "ok": True,
        "minutes": draft_minutes,
        "file_path": file_path,
        "application": store.application_detail(app_id),
    }

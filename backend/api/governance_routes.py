from datetime import datetime, timedelta, timezone
import os
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.api.auth_routes import get_current_user
from backend.services.auth_service import AuthenticatedUser
from backend.services import governance_meeting_service as service
from backend.services.governance_workflow_registry import (
    load_governance_workflow_registry,
)


router = APIRouter(prefix="/governance", tags=["Governance"])
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]
CommitteeType = Literal["DUGC", "DMPC", "DDPC"]


class AgendaItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=2000)
    application_ids: list[int] = Field(default_factory=list, max_length=10)


class MeetingCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    committee_type: CommitteeType
    title: str = Field(min_length=1, max_length=160)
    purpose: str = Field(min_length=1, max_length=2000)
    proposed_start: datetime
    proposed_end: datetime
    duration_minutes: int = Field(ge=30, le=240)
    agenda: list[AgendaItem] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def validate_time_range(self):
        if not self.title.strip() or not self.purpose.strip():
            raise ValueError("Meeting title and purpose cannot be blank.")
        if (
            self.proposed_start.tzinfo is None
            or self.proposed_start.utcoffset() is None
            or self.proposed_end.tzinfo is None
            or self.proposed_end.utcoffset() is None
        ):
            raise ValueError("Meeting date range must include a timezone.")
        if self.proposed_end <= self.proposed_start:
            raise ValueError("Meeting end must follow meeting start.")
        if self.proposed_start <= datetime.now(timezone.utc):
            raise ValueError("Meeting range must be in the future.")
        if self.proposed_end - self.proposed_start > timedelta(days=90):
            raise ValueError("Meeting range cannot exceed 90 days.")
        return self


class AvailabilityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    committee_type: CommitteeType
    available_from: datetime
    available_until: datetime
    availability: Literal["AVAILABLE", "UNAVAILABLE"]

    @model_validator(mode="after")
    def validate_interval(self):
        if (
            self.available_from.tzinfo is None
            or self.available_from.utcoffset() is None
            or self.available_until.tzinfo is None
            or self.available_until.utcoffset() is None
        ):
            raise ValueError("Availability interval must include a timezone.")
        if self.available_until <= self.available_from:
            raise ValueError("Availability end must follow its start.")
        if self.available_until - self.available_from > timedelta(days=90):
            raise ValueError("Availability interval cannot exceed 90 days.")
        return self


class SlotSelectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposed_slot_start: datetime

    @model_validator(mode="after")
    def validate_timezone(self):
        if (
            self.proposed_slot_start.tzinfo is None
            or self.proposed_slot_start.utcoffset() is None
        ):
            raise ValueError("Selected slot must include a timezone.")
        return self


class MeetingAgendaUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agenda: list[AgendaItem] = Field(min_length=1, max_length=20)


class MeetingResponseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    response: Literal["CONFIRMED", "DECLINED"]


class MeetingRecordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agenda_item_index: int | None = Field(default=None, ge=0)
    record_type: Literal["NOTE", "OBSERVATION", "DECISION", "ATTENDANCE"]
    content: str = Field(min_length=1, max_length=5000)


class MinutesDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: dict


class MinutesCommentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    comment: str = Field(min_length=1, max_length=4000)


def _call(operation, *args, **kwargs):
    try:
        return operation(*args, **kwargs)
    except service.GovernanceWorkflowError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail={"code": error.code, "message": error.message},
        ) from error


@router.get("/configuration")
def read_configuration(user: CurrentUser):
    return _call(service.list_committee_workspaces, user)


@router.get("/applications/{application_id}/meetings")
def read_application_meetings(application_id: int, user: CurrentUser):
    return _call(service.get_application_meetings, user, application_id)


@router.post("/applications/{application_id}/meetings/{meeting_id}/approve")
def approve_application_meeting(
    application_id: int,
    meeting_id: int,
    user: CurrentUser,
):
    return _call(
        service.approve_application_meeting,
        user,
        application_id,
        meeting_id,
    )


@router.post("/applications/{application_id}/meetings/{meeting_id}/response")
def respond_to_application_meeting(
    application_id: int,
    meeting_id: int,
    request: MeetingResponseRequest,
    user: CurrentUser,
):
    return _call(
        service.respond_to_application_meeting,
        user,
        application_id,
        meeting_id,
        request.response,
    )


@router.get("/integrations")
def read_integrations(user: CurrentUser):
    if user.role != "DUGC":
        raise HTTPException(status_code=403, detail="Committee role required.")
    registry = load_governance_workflow_registry()
    return {
        "workflow_registry_status": registry["status"],
        "notifications": {
            "status": "NOT_CONFIGURED",
            "provider": None,
            "message": "No email or messaging provider is configured; no notification was sent.",
        },
        "calendar": {
            "status": "NOT_CONFIGURED",
            "provider": None,
            "message": "No institutional calendar provider is configured.",
        },
        "faculty_timetable": {
            "status": "NOT_CONFIGURED",
            "message": "Candidate slots use only explicit committee-member availability submissions.",
        },
        "minutes_generation": {
            "status": (
                "APPROVAL_ENABLED_PROVIDER_NOT_HEALTH_CHECKED"
                if os.getenv("DEPARTMENTAI_MINUTES_LLM_APPROVED", "").lower() == "true"
                else "APPROVAL_REQUIRED"
            ),
            "provider": "Gemini",
            "message": "Meeting notes are sent externally only when approval is enabled and a user requests generation. Provider credentials and availability are checked on that request.",
        },
    }


@router.get("/meetings")
def read_meetings(
    user: CurrentUser,
    committee_type: CommitteeType | None = None,
):
    return _call(service.list_meetings, user, committee_type)


@router.post("/meetings", status_code=201)
def create_meeting(
    request: MeetingCreateRequest,
    user: CurrentUser,
    idempotency_key: Annotated[
        str | None,
        Header(alias="Idempotency-Key", max_length=128),
    ] = None,
):
    return _call(
        service.create_meeting,
        user,
        request.model_dump(),
        idempotency_key,
    )


@router.get("/meetings/slots")
def read_candidate_slots(
    user: CurrentUser,
    committee_type: CommitteeType,
    range_start: datetime,
    range_end: datetime,
    duration_minutes: int = Query(ge=30, le=240),
    exclude_meeting_id: int | None = Query(default=None, ge=1),
):
    if (
        range_start.tzinfo is None
        or range_start.utcoffset() is None
        or range_end.tzinfo is None
        or range_end.utcoffset() is None
    ):
        raise HTTPException(
            status_code=422,
            detail="Slot search timestamps must include a timezone.",
        )
    if user.role != "OFFICIAL":
        raise HTTPException(
            status_code=403,
            detail="Only the assigned Official can search proposal slots.",
        )
    return _call(
        service.calculate_candidate_slots,
        user,
        committee_type,
        range_start,
        range_end,
        duration_minutes,
        exclude_meeting_id,
    )


@router.post("/availability", status_code=201)
def submit_availability(request: AvailabilityRequest, user: CurrentUser):
    return _call(
        service.update_member_availability,
        user,
        request.committee_type,
        request.available_from,
        request.available_until,
        request.availability,
    )


@router.get("/meetings/{meeting_id}")
def read_meeting(meeting_id: int, user: CurrentUser):
    if user.role != "OFFICIAL":
        raise HTTPException(
            status_code=403,
            detail="Open meeting confirmations from the linked application.",
        )
    return _call(
        service.get_meeting,
        user,
        meeting_id,
        allow_official_organizer=user.role == "OFFICIAL",
    )


@router.patch("/meetings/{meeting_id}/slot")
def propose_meeting_slot(
    meeting_id: int,
    request: SlotSelectionRequest,
    user: CurrentUser,
):
    return _call(
        service.select_meeting_slot,
        user,
        meeting_id,
        request.proposed_slot_start,
    )


@router.post("/meetings/{meeting_id}/approve")
def approve_meeting(meeting_id: int, user: CurrentUser):
    return _call(service.approve_meeting, user, meeting_id)


@router.post("/meetings/{meeting_id}/response")
def respond_to_meeting(
    meeting_id: int,
    request: MeetingResponseRequest,
    user: CurrentUser,
):
    return _call(
        service.respond_to_meeting,
        user,
        meeting_id,
        request.response,
    )


@router.get("/meetings/{meeting_id}/agenda")
def read_meeting_agenda(meeting_id: int, user: CurrentUser):
    return _call(service.get_agenda, user, meeting_id)


@router.patch("/meetings/{meeting_id}/agenda")
def update_meeting_agenda(
    meeting_id: int,
    request: MeetingAgendaUpdateRequest,
    user: CurrentUser,
):
    return _call(
        service.update_meeting_agenda,
        user,
        meeting_id,
        [item.model_dump() for item in request.agenda],
    )


@router.get("/meetings/{meeting_id}/notice")
def read_meeting_notice(meeting_id: int, user: CurrentUser):
    return _call(service.get_meeting_notice, user, meeting_id)


@router.post("/meetings/{meeting_id}/records", status_code=201)
def add_meeting_record(
    meeting_id: int,
    request: MeetingRecordRequest,
    user: CurrentUser,
):
    return _call(
        service.add_meeting_record,
        user,
        meeting_id,
        request.agenda_item_index,
        request.record_type,
        request.content,
    )


@router.get("/meetings/{meeting_id}/minutes")
def read_minutes_workspace(meeting_id: int, user: CurrentUser):
    return _call(service.get_minutes_workspace, user, meeting_id)


@router.post("/meetings/{meeting_id}/minutes", status_code=201)
def create_manual_minutes_draft(meeting_id: int, user: CurrentUser):
    return _call(service.create_minutes_draft, user, meeting_id)


@router.post("/meetings/{meeting_id}/minutes/generate", status_code=201)
def generate_minutes(meeting_id: int, user: CurrentUser):
    return _call(service.generate_minutes, user, meeting_id)


@router.patch("/meetings/{meeting_id}/minutes/{version_id}")
def save_minutes(
    meeting_id: int,
    version_id: int,
    request: MinutesDraftRequest,
    user: CurrentUser,
):
    return _call(
        service.save_minutes_draft,
        user,
        meeting_id,
        version_id,
        request.content,
    )


@router.post("/minutes/{version_id}/submit")
def submit_minutes(version_id: int, user: CurrentUser):
    return _call(service.submit_minutes_for_review, user, version_id)


@router.post("/minutes/{version_id}/comments", status_code=201)
def comment_on_minutes(
    version_id: int,
    request: MinutesCommentRequest,
    user: CurrentUser,
):
    return _call(
        service.add_minutes_comment,
        user,
        version_id,
        request.comment,
    )


@router.post("/minutes/{version_id}/approve")
def approve_minutes(version_id: int, user: CurrentUser):
    return _call(service.approve_minutes, user, version_id)

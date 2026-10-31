"""
Meeting Scheduling Agent.

Gemini function-calling wrapper over the tools in scheduling_tools.py.

Workflow (project proposal):
    1. Load committee membership.
    2. Check academic-calendar restrictions.
    3. Find common free slots from member timetables.
    4. Send a WhatsApp proposal to the committee group (simulated).
    5. After HoD consent, send official email + .ics invites (simulated).

If Gemini is unavailable the same tools run in a deterministic fallback
so the module can be tested without a live LLM.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from pathlib import Path

from backend.agents.scheduling_tools import (
    TOOL_FUNCTIONS,
    call_tool,
    check_academic_calendar,
    find_common_free_slots,
    get_committee_members,
    mock_send_official_invite,
    mock_send_whatsapp_proposal,
    normalize_committee_name,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

try:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-3.5-flash-lite")
MAX_TOOL_TURNS = 8

PROPOSAL_STORE: dict[str, dict] = {}

FUNCTION_DECLARATIONS = [
    {
        "name": "get_committee_members",
        "description": (
            "Load DUGC, DMPC or DDPC membership including roles (HoD, "
            "Convener, Member), emails, dummy phone numbers, weekly busy "
            "slots and existing meetings."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "committee_name": {
                    "type": "string",
                    "description": "Committee name: DUGC, DMPC or DDPC.",
                }
            },
            "required": ["committee_name"],
        },
    },
    {
        "name": "check_academic_calendar",
        "description": (
            "Check the academic calendar for blocked dates in a range. "
            "Blocked categories include Winter Vacation, MID SEM Exam, "
            "Diwali, Dussehra, END SEM Theory EXAM, holidays and breaks."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "target_date_range": {
                    "type": "string",
                    "description": (
                        "Inclusive range such as '2026-09-07 to 2026-09-18' "
                        "or a single date '2026-09-10'."
                    ),
                }
            },
            "required": ["target_date_range"],
        },
    },
    {
        "name": "find_common_free_slots",
        "description": (
            "Cross-reference member busy slots with academic-calendar "
            "restrictions and return up to 3 valid 60-minute meeting times."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "committee_name": {
                    "type": "string",
                    "description": "Committee name: DUGC, DMPC or DDPC.",
                },
                "date_range": {
                    "type": "string",
                    "description": "Inclusive date range YYYY-MM-DD to YYYY-MM-DD.",
                },
                "duration_minutes": {
                    "type": "integer",
                    "description": "Meeting duration in minutes. Default 60.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of slots to return. Default 3.",
                },
            },
            "required": ["committee_name", "date_range"],
        },
    },
    {
        "name": "mock_send_whatsapp_proposal",
        "description": (
            "Simulate sending the proposed slots and agenda to the official "
            "committee WhatsApp group for HoD approval."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "slots": {
                    "type": "array",
                    "description": "List of slot objects from find_common_free_slots.",
                    "items": {"type": "object"},
                },
                "agenda": {
                    "type": "string",
                    "description": "Proposed meeting agenda.",
                },
                "committee_name": {
                    "type": "string",
                    "description": "Committee name: DUGC, DMPC or DDPC.",
                },
            },
            "required": ["slots", "agenda"],
        },
    },
    {
        "name": "mock_send_official_invite",
        "description": (
            "Simulate dispatching the official meeting notice by authorized "
            "email and an .ics calendar invite after HoD approval."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "final_slot": {
                    "type": "object",
                    "description": "The approved slot object.",
                },
                "agenda": {
                    "type": "string",
                    "description": "Final agenda text.",
                },
                "committee_name": {
                    "type": "string",
                    "description": "Committee name: DUGC, DMPC or DDPC.",
                },
            },
            "required": ["final_slot", "agenda"],
        },
    },
]


def _gemini_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    try:
        from google import genai

        return genai.Client(api_key=api_key)
    except Exception:
        return None


def _tool_config():
    from google.genai import types

    declarations = [
        types.FunctionDeclaration(
            name=item["name"],
            description=item["description"],
            parameters=item["parameters"],
        )
        for item in FUNCTION_DECLARATIONS
    ]
    return types.GenerateContentConfig(
        tools=[types.Tool(function_declarations=declarations)],
        temperature=0.1,
    )


def _function_calls(response) -> list:
    calls = []
    if not response or not getattr(response, "candidates", None):
        return calls
    candidate = response.candidates[0]
    content = getattr(candidate, "content", None)
    if not content or not getattr(content, "parts", None):
        return calls
    for part in content.parts:
        fn = getattr(part, "function_call", None)
        if fn and getattr(fn, "name", None):
            args = dict(fn.args) if getattr(fn, "args", None) else {}
            calls.append({"name": fn.name, "args": args})
    return calls


def _run_gemini_loop(user_prompt: str) -> dict:
    """Ask Gemini to call tools. Returns transcript + last text."""
    client = _gemini_client()
    if client is None:
        raise RuntimeError("Gemini client is not available.")

    from google.genai import types

    contents = [
        types.Content(
            role="user",
            parts=[types.Part(text=user_prompt)],
        )
    ]
    config = _tool_config()
    tool_trace = []
    final_text = ""

    for _ in range(MAX_TOOL_TURNS):
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=contents,
            config=config,
        )
        calls = _function_calls(response)
        if not calls:
            final_text = (getattr(response, "text", None) or "").strip()
            break

        contents.append(response.candidates[0].content)
        function_response_parts = []
        for call in calls:
            result = call_tool(call["name"], call["args"])
            tool_trace.append(
                {
                    "tool": call["name"],
                    "arguments": call["args"],
                    "result_ok": bool(result.get("ok")) if isinstance(result, dict) else False,
                }
            )
            function_response_parts.append(
                types.Part.from_function_response(
                    name=call["name"],
                    response=result if isinstance(result, dict) else {"result": result},
                )
            )
        contents.append(
            types.Content(role="user", parts=function_response_parts)
        )

    return {"text": final_text, "tool_trace": tool_trace, "mode": "gemini"}


def _fallback_propose(committee_name: str, date_range: str, agenda: str, duration_minutes: int) -> dict:
    members = get_committee_members(committee_name)
    calendar_check = check_academic_calendar(date_range)
    slots_result = find_common_free_slots(
        committee_name,
        date_range,
        duration_minutes=duration_minutes,
    )
    whatsapp = mock_send_whatsapp_proposal(
        slots_result.get("slots") or [],
        agenda,
        committee_name=members["committee"],
    )
    return {
        "members": members,
        "calendar": calendar_check,
        "slots": slots_result,
        "whatsapp": whatsapp,
        "mode": "deterministic_fallback",
        "tool_trace": [
            {"tool": "get_committee_members", "result_ok": True},
            {"tool": "check_academic_calendar", "result_ok": True},
            {"tool": "find_common_free_slots", "result_ok": True},
            {"tool": "mock_send_whatsapp_proposal", "result_ok": True},
        ],
    }


def propose_meeting(
    committee_name: str,
    date_range: str,
    agenda: str,
    duration_minutes: int = 60,
    use_gemini: bool = True,
) -> dict:
    committee_name = normalize_committee_name(committee_name)
    agenda = (agenda or "").strip()
    if not agenda:
        raise ValueError("agenda cannot be empty.")
    if not date_range or not date_range.strip():
        raise ValueError("date_range cannot be empty.")

    gemini_meta = None
    if use_gemini:
        prompt = f"""
You are the Meeting Scheduling Agent of DepartmentAI.

Task: propose a {committee_name} meeting.

Date range: {date_range}
Duration minutes: {duration_minutes}
Agenda:
{agenda}

You MUST use the tools in this order:
1. get_committee_members(committee_name="{committee_name}")
2. check_academic_calendar(target_date_range="{date_range}")
3. find_common_free_slots(committee_name="{committee_name}", date_range="{date_range}", duration_minutes={duration_minutes})
4. mock_send_whatsapp_proposal with the returned slots, the agenda, and committee_name="{committee_name}"

Do not invent members, dates, or slots. After the WhatsApp tool returns,
write a short confirmation that the proposal was sent and list the slots.
"""
        try:
            gemini_meta = _run_gemini_loop(prompt)
        except Exception as exc:
            gemini_meta = {"error": str(exc), "mode": "gemini_failed"}

    packed = _fallback_propose(
        committee_name,
        date_range,
        agenda,
        duration_minutes,
    )
    if gemini_meta:
        packed["llm"] = gemini_meta

    proposal_id = f"PROP-{uuid.uuid4().hex[:10].upper()}"
    record = {
        "proposal_id": proposal_id,
        "status": "awaiting_hod_consent",
        "committee": committee_name,
        "date_range": date_range,
        "agenda": agenda,
        "duration_minutes": duration_minutes,
        "slots": packed["slots"].get("slots") or [],
        "member_free_windows": packed["slots"].get("member_free_windows") or [],
        "whatsapp_dispatch_id": packed["whatsapp"].get("dispatch_id"),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "hod": packed["members"].get("hod"),
        "convener": packed["members"].get("convener"),
        "whatsapp_group": packed["members"].get("whatsapp_group"),
    }
    PROPOSAL_STORE[proposal_id] = record
    packed["proposal"] = record
    packed["ok"] = True
    return packed


def get_proposal(proposal_id: str) -> dict | None:
    return PROPOSAL_STORE.get(proposal_id)


def list_proposals() -> list[dict]:
    return list(PROPOSAL_STORE.values())


def _select_slot(record: dict, slot_index: int | None, slot: dict | None) -> dict:
    slots = record.get("slots") or []
    if slot:
        return slot
    if slot_index is None:
        if not slots:
            raise ValueError("No proposed slots are available to approve.")
        return slots[0]
    index = int(slot_index)
    if index < 1 or index > len(slots):
        raise ValueError(
            f"slot_index {index} is out of range. Valid: 1..{len(slots) or 0}."
        )
    return slots[index - 1]


def approve_meeting(
    proposal_id: str,
    slot_index: int | None = None,
    slot: dict | None = None,
    approved: bool = True,
    hod_comment: str = "",
    use_gemini: bool = True,
) -> dict:
    record = PROPOSAL_STORE.get(proposal_id)
    if record is None:
        raise KeyError(f"Unknown proposal_id: {proposal_id}")

    if not approved:
        record["status"] = "rejected_by_hod"
        record["hod_comment"] = hod_comment
        record["resolved_at"] = datetime.now().isoformat(timespec="seconds")
        return {
            "ok": True,
            "proposal_id": proposal_id,
            "status": record["status"],
            "message": "HoD rejected the proposed meeting. No official invite was sent.",
            "hod_comment": hod_comment,
        }

    chosen = _select_slot(record, slot_index, slot)
    agenda = record["agenda"]
    committee_name = record["committee"]

    gemini_meta = None
    if use_gemini:
        prompt = f"""
You are the Meeting Scheduling Agent of DepartmentAI.

The Head of Department has APPROVED a {committee_name} meeting.

Approved slot JSON:
{json.dumps(chosen)}

Agenda:
{agenda}

Call mock_send_official_invite with:
  final_slot = the approved slot object
  agenda = the agenda
  committee_name = "{committee_name}"

Then confirm that the official notice and .ics invite were dispatched.
"""
        try:
            gemini_meta = _run_gemini_loop(prompt)
        except Exception as exc:
            gemini_meta = {"error": str(exc), "mode": "gemini_failed"}

    invite = mock_send_official_invite(
        chosen,
        agenda,
        committee_name=committee_name,
    )
    record["status"] = "notice_issued"
    record["approved_slot"] = chosen
    record["official_dispatch_id"] = invite.get("dispatch_id")
    record["ics_path"] = invite.get("ics_path")
    record["hod_comment"] = hod_comment
    record["resolved_at"] = datetime.now().isoformat(timespec="seconds")

    result = {
        "ok": True,
        "proposal_id": proposal_id,
        "status": record["status"],
        "approved_slot": chosen,
        "invite": invite,
        "proposal": record,
    }
    if gemini_meta:
        result["llm"] = gemini_meta
    return result

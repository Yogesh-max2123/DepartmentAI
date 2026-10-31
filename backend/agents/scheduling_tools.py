"""
Pure-Python tools used by the Meeting Scheduling Agent.

These functions are the Gemini function-calling targets. They load the
synthetic committee database and academic-calendar restrictions and do
not require the Gemini API.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import date, datetime, time, timedelta
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DIR = PROJECT_ROOT / "documents" / "scheduler" / "processed"
COMMITTEE_DB_FILE = PROCESSED_DIR / "synthetic_committee_db.json"
RESTRICTIONS_FILE = PROCESSED_DIR / "academic_calendar_restrictions.json"
DISPATCH_LOG_FILE = PROCESSED_DIR / "dispatch_log.jsonl"

logger = logging.getLogger("departmentai.scheduling")

if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s")
    )
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

WORKING_DAYS = {0, 1, 2, 3, 4}
SLOT_STARTS = [
    time(9, 30),
    time(10, 30),
    time(11, 30),
    time(14, 30),
    time(15, 30),
    time(16, 30),
]
DEFAULT_DURATION = 60
MAX_SLOTS = 3
VALID_COMMITTEES = ("DUGC", "DMPC", "DDPC")

_committee_cache = None
_restrictions_cache = None


def _load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Run: python ai/ingestion/synthetic_scheduler_data.py"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def load_committee_db(force: bool = False) -> dict:
    global _committee_cache
    if _committee_cache is None or force:
        _committee_cache = _load_json(COMMITTEE_DB_FILE)
    return _committee_cache


def load_restrictions(force: bool = False) -> dict:
    global _restrictions_cache
    if _restrictions_cache is None or force:
        _restrictions_cache = _load_json(RESTRICTIONS_FILE)
    return _restrictions_cache


def parse_iso_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def parse_hhmm(value: str) -> time:
    return datetime.strptime(value, "%H:%M").time()


def combine(day: date, clock: time) -> datetime:
    return datetime.combine(day, clock)


def minutes_between(start: time, end: time) -> int:
    return int(
        (
            datetime.combine(date.min, end) - datetime.combine(date.min, start)
        ).total_seconds()
        // 60
    )


def intervals_overlap(a_start, a_end, b_start, b_end) -> bool:
    return a_start < b_end and b_start < a_end


def parse_date_range(target_date_range: str) -> tuple[date, date]:
    text = (target_date_range or "").strip()
    if not text:
        raise ValueError("target_date_range cannot be empty.")

    for separator in (" to ", " - ", ",", "..", "–"):
        if separator in text:
            left, right = text.split(separator, 1)
            return parse_iso_date(left.strip()), parse_iso_date(right.strip())

    single = parse_iso_date(text)
    return single, single


def normalize_committee_name(committee_name: str) -> str:
    name = (committee_name or "").strip().upper()
    aliases = {
        "UG": "DUGC",
        "UNDERGRADUATE": "DUGC",
        "DEPARTMENTAL UNDERGRADUATE COMMITTEE": "DUGC",
        "PG": "DMPC",
        "MTECH": "DMPC",
        "M.TECH": "DMPC",
        "MASTERS": "DMPC",
        "DEPARTMENTAL M.TECH. PROGRAMME COMMITTEE": "DMPC",
        "PHD": "DDPC",
        "PH.D": "DDPC",
        "PH.D.": "DDPC",
        "DOCTORAL": "DDPC",
        "DPGC": "DDPC",
        "DEPARTMENTAL DOCTORAL PROGRAMME COMMITTEE": "DDPC",
        "DEPARTMENTAL POSTGRADUATE COMMITTEE": "DMPC",
    }
    name = aliases.get(name, name)
    if name not in VALID_COMMITTEES:
        raise ValueError(
            f"Unknown committee '{committee_name}'. "
            f"Use one of: {', '.join(VALID_COMMITTEES)}."
        )
    return name


def blocked_dates_set() -> set[str]:
    data = load_restrictions()
    return {
        row["date"]
        for row in data.get("blocked_dates", [])
        if row.get("blocks_meeting")
    }


def blocked_lookup() -> dict:
    data = load_restrictions()
    return {
        row["date"]: row
        for row in data.get("blocked_dates", [])
        if row.get("blocks_meeting")
    }


def get_committee_members(committee_name: str) -> dict:
    """Load membership, roles, emails, phones and busy slots."""
    key = normalize_committee_name(committee_name)
    db = load_committee_db()
    committee = db["committees"][key]
    members = []
    for member in committee["members"]:
        members.append(
            {
                "member_id": member["member_id"],
                "name": member["name"],
                "role": member["role"],
                "designation": member["designation"],
                "email": member["email"],
                "phone": member["phone"],
                "weekly_busy_slots": member.get("weekly_busy_slots", []),
                "existing_meetings": member.get("existing_meetings", []),
            }
        )
    hod = next((m for m in members if str(m.get("role") or "").lower() == "hod"), None)
    convener = next(
        (
            m
            for m in members
            if "convener" in str(m.get("role") or "").lower()
        ),
        None,
    )
    return {
        "ok": True,
        "committee": key,
        "full_name": committee["full_name"],
        "department": committee["department"],
        "whatsapp_group": committee["whatsapp_group"],
        "email_list": committee["email_list"],
        "hod": hod,
        "convener": convener,
        "member_count": len(members),
        "members": members,
    }


def check_academic_calendar(target_date_range: str) -> dict:
    """Return blocked and allowed working days in a date range."""
    start, end = parse_date_range(target_date_range)
    if end < start:
        start, end = end, start

    lookup = blocked_lookup()
    blocked = []
    allowed = []
    weekends = []

    current = start
    while current <= end:
        iso = current.isoformat()
        weekday = current.strftime("%A")
        if current.weekday() not in WORKING_DAYS:
            weekends.append({"date": iso, "weekday": weekday, "reason": "Weekend"})
        elif iso in lookup:
            row = lookup[iso]
            blocked.append(
                {
                    "date": iso,
                    "weekday": weekday,
                    "label": row.get("label"),
                    "categories": row.get("categories", []),
                }
            )
        else:
            allowed.append({"date": iso, "weekday": weekday})
        current += timedelta(days=1)

    return {
        "ok": True,
        "range_start": start.isoformat(),
        "range_end": end.isoformat(),
        "blocked_dates": blocked,
        "allowed_working_dates": allowed,
        "weekends": weekends,
        "blocked_count": len(blocked),
        "allowed_count": len(allowed),
        "meetings_permitted": len(allowed) > 0,
    }


def _working_windows(day: date) -> list[tuple[datetime, datetime]]:
    morning = (combine(day, time(9, 0)), combine(day, time(13, 0)))
    afternoon = (combine(day, time(14, 0)), combine(day, time(17, 0)))
    return [morning, afternoon]


def _busy_intervals(member: dict, day: date) -> list[tuple[datetime, datetime]]:
    intervals = []
    weekday = day.strftime("%A")
    for slot in member.get("weekly_busy_slots", []):
        if slot.get("day") != weekday:
            continue
        intervals.append(
            (combine(day, parse_hhmm(slot["start"])), combine(day, parse_hhmm(slot["end"])))
        )
    for meeting in member.get("existing_meetings", []):
        if meeting.get("date") != day.isoformat():
            continue
        intervals.append(
            (
                combine(day, parse_hhmm(meeting["start"])),
                combine(day, parse_hhmm(meeting["end"])),
            )
        )
    intervals.sort(key=lambda item: item[0])
    return intervals


def _free_segments(member: dict, day: date) -> list[tuple[datetime, datetime]]:
    busy = _busy_intervals(member, day)
    free = []
    for window_start, window_end in _working_windows(day):
        cursor = window_start
        for busy_start, busy_end in busy:
            if busy_end <= cursor or busy_start >= window_end:
                continue
            overlap_start = max(cursor, busy_start)
            if overlap_start > cursor:
                free.append((cursor, min(overlap_start, window_end)))
            cursor = max(cursor, min(busy_end, window_end))
            if cursor >= window_end:
                break
        if cursor < window_end:
            free.append((cursor, window_end))
    return [(start, end) for start, end in free if minutes_between(start.time(), end.time()) >= 30]


def _format_windows(windows: list[tuple[datetime, datetime]]) -> str:
    if not windows:
        return "no free window"
    return ", ".join(f"{start.strftime('%H:%M')}-{end.strftime('%H:%M')}" for start, end in windows)


def _member_availability_for_slot(
    members: list[dict], day: date, start_dt: datetime, end_dt: datetime
) -> list[dict]:
    rows = []
    for member in members:
        windows = _free_segments(member, day)
        rows.append(
            {
                "name": member["name"],
                "role": member.get("role"),
                "free": _member_busy_on(member, day, start_dt, end_dt) is None,
                "free_windows": [
                    f"{start.strftime('%H:%M')}-{end.strftime('%H:%M')}" for start, end in windows
                ],
                "summary": f"{member['name']} is free {_format_windows(windows)}",
            }
        )
    return rows


def _member_free_windows(
    members: list[dict], allowed_dates: list[dict], duration_minutes: int
) -> list[dict]:
    sample_dates = allowed_dates[:5]
    rows = []
    for member in members:
        day_summaries = []
        for day_row in sample_dates:
            day = parse_iso_date(day_row["date"])
            windows = _free_segments(member, day)
            if not windows:
                continue
            day_summaries.append(
                {
                    "date": day.isoformat(),
                    "weekday": day.strftime("%A"),
                    "windows": [
                        f"{start.strftime('%H:%M')}-{end.strftime('%H:%M')}" for start, end in windows
                    ],
                }
            )
        typical = []
        for weekday in ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday"):
            probe = date(2026, 9, 14)
            while probe.strftime("%A") != weekday:
                probe += timedelta(days=1)
            windows = _free_segments(member, probe)
            if windows:
                typical.append(
                    f"{weekday} {_format_windows(windows)}"
                )
        rows.append(
            {
                "member_id": member.get("member_id"),
                "name": member["name"],
                "role": member.get("role"),
                "designation": member.get("designation"),
                "typical_free_windows": typical,
                "sample_dates": day_summaries,
                "summary": f"{member['name']} is free {'; '.join(typical[:3]) or 'no weekday window'}",
            }
        )
    return rows


def _member_busy_on(member: dict, day: date, start_dt: datetime, end_dt: datetime) -> str | None:
    weekday = day.strftime("%A")
    for slot in member.get("weekly_busy_slots", []):
        if slot.get("day") != weekday:
            continue
        busy_start = combine(day, parse_hhmm(slot["start"]))
        busy_end = combine(day, parse_hhmm(slot["end"]))
        if intervals_overlap(start_dt, end_dt, busy_start, busy_end):
            return (
                f"{member['name']} busy {slot['start']}-{slot['end']} "
                f"({slot.get('reason') or 'timetable'})"
            )

    for meeting in member.get("existing_meetings", []):
        if meeting.get("date") != day.isoformat():
            continue
        busy_start = combine(day, parse_hhmm(meeting["start"]))
        busy_end = combine(day, parse_hhmm(meeting["end"]))
        if intervals_overlap(start_dt, end_dt, busy_start, busy_end):
            return (
                f"{member['name']} already in '{meeting.get('title')}' "
                f"{meeting['start']}-{meeting['end']}"
            )
    return None


def find_common_free_slots(
    committee_name: str,
    date_range: str,
    duration_minutes: int = DEFAULT_DURATION,
    limit: int = MAX_SLOTS,
) -> dict:
    """Cross-reference busy slots and calendar restrictions."""
    duration_minutes = int(duration_minutes or DEFAULT_DURATION)
    limit = int(limit or MAX_SLOTS)
    committee = get_committee_members(committee_name)
    calendar_check = check_academic_calendar(date_range)

    candidates = []
    conflicts_sampled = []

    for day_row in calendar_check["allowed_working_dates"]:
        day = parse_iso_date(day_row["date"])
        for start_clock in SLOT_STARTS:
            start_dt = combine(day, start_clock)
            end_dt = start_dt + timedelta(minutes=duration_minutes)
            if end_dt.time() > time(17, 0) and not (
                end_dt.hour == 17 and end_dt.minute == 0
            ):
                continue
            if end_dt.date() != day:
                continue
            if intervals_overlap(start_dt, end_dt, combine(day, time(13, 0)), combine(day, time(14, 0))):
                continue

            reasons = []
            for member in committee["members"]:
                reason = _member_busy_on(member, day, start_dt, end_dt)
                if reason:
                    reasons.append(reason)
            if reasons:
                if len(conflicts_sampled) < 8:
                    conflicts_sampled.append(
                        {
                            "date": day.isoformat(),
                            "start": start_clock.strftime("%H:%M"),
                            "conflicts": reasons[:4],
                        }
                    )
                continue

            candidates.append(
                {
                    "date": day.isoformat(),
                    "weekday": day.strftime("%A"),
                    "start": start_clock.strftime("%H:%M"),
                    "end": end_dt.strftime("%H:%M"),
                    "duration_minutes": duration_minutes,
                    "timezone": "Asia/Kolkata",
                    "available_members": [m["name"] for m in committee["members"]],
                    "member_availability": _member_availability_for_slot(
                        committee["members"], day, start_dt, end_dt
                    ),
                }
            )

    selected = candidates[:limit]
    member_free_windows = _member_free_windows(
        committee["members"],
        calendar_check["allowed_working_dates"],
        duration_minutes,
    )
    return {
        "ok": True,
        "committee": committee["committee"],
        "range_start": calendar_check["range_start"],
        "range_end": calendar_check["range_end"],
        "blocked_dates_in_range": calendar_check["blocked_dates"],
        "slots": selected,
        "slot_count": len(selected),
        "candidate_count": len(candidates),
        "sample_conflicts": conflicts_sampled,
        "member_free_windows": member_free_windows,
        "message": (
            f"Found {len(selected)} valid meeting slot(s) for {committee['committee']}."
            if selected
            else (
                "No common free slot found in the requested range after applying "
                "academic-calendar restrictions and member timetables."
            )
        ),
    }


def _append_dispatch_log(entry: dict) -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    with DISPATCH_LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def format_whatsapp_message(committee: str, slots: list, agenda: str) -> str:
    lines = [
        f"*DepartmentAI – {committee} meeting proposal*",
        "",
        "Proposed agenda:",
        agenda.strip() or "(agenda not supplied)",
        "",
        "Suggested slots (subject to HoD consent):",
    ]
    if not slots:
        lines.append("  No valid slots were found.")
    for index, slot in enumerate(slots, start=1):
        lines.append(
            f"  {index}. {slot.get('weekday')} {slot.get('date')} "
            f"{slot.get('start')}-{slot.get('end')} ({slot.get('timezone', 'IST')})"
        )
    lines.extend(
        [
            "",
            "HoD: please reply APPROVE <slot number> to confirm, or REJECT.",
            "This is a simulated WhatsApp dispatch for demonstration.",
        ]
    )
    return "\n".join(lines)


def mock_send_whatsapp_proposal(slots, agenda: str, committee_name: str = "DDPC") -> dict:
    """Simulate sending a WhatsApp proposal to the committee group."""
    if isinstance(slots, str):
        try:
            slots = json.loads(slots)
        except json.JSONDecodeError:
            slots = []
    committee = get_committee_members(committee_name)
    message = format_whatsapp_message(committee["committee"], slots or [], agenda or "")
    dispatch_id = f"WA-{uuid.uuid4().hex[:10].upper()}"
    entry = {
        "channel": "whatsapp",
        "dispatch_id": dispatch_id,
        "status": "simulated",
        "committee": committee["committee"],
        "group": committee["whatsapp_group"],
        "agenda": agenda,
        "slots": slots or [],
        "message": message,
        "sent_at": datetime.now().isoformat(timespec="seconds"),
    }
    logger.info("WHATSAPP PROPOSAL [%s]\n%s", dispatch_id, message)
    print("\n===== MOCK WHATSAPP DISPATCH =====")
    print(message)
    print("==================================\n")
    _append_dispatch_log(entry)
    return {
        "ok": True,
        "channel": "whatsapp",
        "dispatch_id": dispatch_id,
        "status": "simulated",
        "group": committee["whatsapp_group"],
        "message": message,
    }


def build_ics(slot: dict, agenda: str, committee: dict) -> str:
    stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    day = slot["date"].replace("-", "")
    start = slot["start"].replace(":", "") + "00"
    end = slot["end"].replace(":", "") + "00"
    uid = f"{uuid.uuid4()}@departmentai.local"
    attendees = "\n".join(
        f"ATTENDEE;CN={member['name']}:MAILTO:{member['email']}"
        for member in committee["members"]
    )
    summary = f"{committee['committee']} Meeting"
    description = (agenda or "Committee meeting").replace("\n", "\\n")
    return "\n".join(
        [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//DepartmentAI//Scheduling Agent//EN",
            "CALSCALE:GREGORIAN",
            "METHOD:REQUEST",
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{stamp}",
            f"DTSTART;TZID=Asia/Kolkata:{day}T{start}",
            f"DTEND;TZID=Asia/Kolkata:{day}T{end}",
            f"SUMMARY:{summary}",
            f"DESCRIPTION:{description}",
            f"ORGANIZER;CN={committee['hod']['name']}:MAILTO:{committee['hod']['email']}",
            attendees,
            "STATUS:CONFIRMED",
            "END:VEVENT",
            "END:VCALENDAR",
            "",
        ]
    )


def format_official_notice(committee: dict, slot: dict, agenda: str) -> str:
    members = "\n".join(
        f"  - {m['name']} ({m['role']}) <{m['email']}>"
        for m in committee["members"]
    )
    return "\n".join(
        [
            f"NOTICE: Meeting of the {committee['full_name']} ({committee['committee']})",
            f"Department: {committee['department']}",
            "",
            f"Date       : {slot.get('weekday')} {slot.get('date')}",
            f"Time       : {slot.get('start')} – {slot.get('end')} ({slot.get('timezone', 'IST')})",
            f"Venue      : Department Committee Room / authorized hybrid link",
            "",
            "Agenda:",
            agenda.strip() or "(to be circulated)",
            "",
            "Members:",
            members,
            "",
            "This notice is issued after HoD consent. Please attend as scheduled.",
            "A calendar (.ics) invite has been dispatched to authorized email addresses.",
            "",
            f"Issued by: {committee['convener']['name']} (Convener), with consent of",
            f"{committee['hod']['name']} (Head of Department).",
        ]
    )


def mock_send_official_invite(final_slot, agenda: str, committee_name: str = "DDPC") -> dict:
    """Simulate official email + .ics calendar invite after HoD approval."""
    if isinstance(final_slot, str):
        try:
            final_slot = json.loads(final_slot)
        except json.JSONDecodeError as exc:
            raise ValueError("final_slot must be an object or JSON object string.") from exc

    committee = get_committee_members(committee_name)
    notice = format_official_notice(committee, final_slot, agenda or "")
    ics = build_ics(final_slot, agenda or "", committee)
    dispatch_id = f"MAIL-{uuid.uuid4().hex[:10].upper()}"
    ics_path = PROCESSED_DIR / f"{dispatch_id}.ics"
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    ics_path.write_text(ics, encoding="utf-8")

    recipients = [m["email"] for m in committee["members"]]
    entry = {
        "channel": "email_calendar",
        "dispatch_id": dispatch_id,
        "status": "simulated",
        "committee": committee["committee"],
        "recipients": recipients,
        "slot": final_slot,
        "agenda": agenda,
        "notice": notice,
        "ics_path": str(ics_path.relative_to(PROJECT_ROOT)),
        "sent_at": datetime.now().isoformat(timespec="seconds"),
    }
    logger.info("OFFICIAL INVITE [%s] recipients=%s", dispatch_id, recipients)
    print("\n===== MOCK OFFICIAL EMAIL / CALENDAR INVITE =====")
    print(notice)
    print(f"\nICS written: {ics_path}")
    print("=================================================\n")
    _append_dispatch_log(entry)
    return {
        "ok": True,
        "channel": "email_calendar",
        "dispatch_id": dispatch_id,
        "status": "simulated",
        "recipients": recipients,
        "notice": notice,
        "ics_path": str(ics_path.relative_to(PROJECT_ROOT)),
        "slot": final_slot,
    }


TOOL_FUNCTIONS = {
    "get_committee_members": get_committee_members,
    "check_academic_calendar": check_academic_calendar,
    "find_common_free_slots": find_common_free_slots,
    "mock_send_whatsapp_proposal": mock_send_whatsapp_proposal,
    "mock_send_official_invite": mock_send_official_invite,
}


def call_tool(name: str, arguments: dict):
    if name not in TOOL_FUNCTIONS:
        return {"ok": False, "error": f"Unknown tool: {name}"}
    try:
        return TOOL_FUNCTIONS[name](**(arguments or {}))
    except TypeError as exc:
        return {"ok": False, "error": f"Invalid arguments for {name}: {exc}"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

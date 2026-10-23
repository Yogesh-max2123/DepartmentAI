"""
DepartmentAI - Meeting Scheduling Agent data synthesis.

Builds two local knowledge files used by the Scheduling Agent:

    documents/scheduler/processed/synthetic_committee_db.json
    documents/scheduler/processed/academic_calendar_restrictions.json

The academic calendar PDF in documents/calendar/ is image-based (no
extractable text). Events below were transcribed from that official
Even/Odd Semester (2026-27) calendar. The script writes a text dump
and then parses that text into the restrictions JSON so the parser
is real and testable.
"""

from __future__ import annotations

import argparse
import calendar
import json
from datetime import date, datetime, timedelta
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

CALENDAR_PDF = (
    PROJECT_ROOT
    / "documents"
    / "calendar"
    / "academic_calendar_rotated_compressed.pdf"
)

OUTPUT_DIR = PROJECT_ROOT / "documents" / "scheduler" / "processed"

COMMITTEE_DB_FILE = OUTPUT_DIR / "synthetic_committee_db.json"
RESTRICTIONS_FILE = OUTPUT_DIR / "academic_calendar_restrictions.json"
CALENDAR_TEXT_FILE = OUTPUT_DIR / "academic_calendar.txt"

TIMEZONE = "Asia/Kolkata"
ACADEMIC_YEAR = "2026-27"


# ============================================================
# Transcribed official calendar events (2026-27)
# ============================================================

# Each event: start, end (inclusive), label, category, blocks_meeting, semester
# categories: holiday, exam, break, vacation, festival, institute_event,
#             evaluation, registration, notification, result, admin, instruction

CALENDAR_EVENTS = [
    # ----- Odd Semester 2026-27 (Jul 2026 - Dec 2026) -----
    ("2026-07-07", "2026-07-07", "Declaration of Supplementary Result", "result", False, "odd"),
    ("2026-07-09", "2026-07-09", "Summer Vacation Ends / Online Registration Ends", "vacation_end", False, "odd"),
    ("2026-07-13", "2026-07-17", "Physical Registration (Odd Semester)", "registration", False, "odd"),
    ("2026-07-20", "2026-07-20", "Start of Classes (Odd Semester)", "instruction", False, "odd"),
    ("2026-08-15", "2026-08-15", "Independence Day", "holiday", True, "odd"),
    ("2026-08-26", "2026-08-26", "Id-e-Milad", "holiday", True, "odd"),
    ("2026-09-04", "2026-09-04", "Janmashtami", "holiday", True, "odd"),
    ("2026-10-02", "2026-10-02", "Gandhi Jayanti", "holiday", True, "odd"),
    ("2026-10-08", "2026-10-08", "1st Short Attendance Notification", "notification", False, "odd"),
    ("2026-10-09", "2026-10-09", "MID SEM Exam Start", "exam", True, "odd"),
    ("2026-10-16", "2026-10-16", "MID SEM Exam End", "exam", True, "odd"),
    ("2026-10-09", "2026-10-16", "MID SEM Exam", "exam", True, "odd"),
    ("2026-10-17", "2026-10-17", "MID SEM Break Start", "break", True, "odd"),
    ("2026-10-20", "2026-10-20", "Dussehra", "holiday", True, "odd"),
    ("2026-10-25", "2026-10-25", "MID SEM Break End", "break", True, "odd"),
    ("2026-10-17", "2026-10-25", "MID SEM Break", "break", True, "odd"),
    ("2026-11-02", "2026-11-02", "MT/PhD Evaluation Start / Practical Exam Start", "exam", True, "odd"),
    ("2026-11-03", "2026-11-03", "2nd Short Attendance Notification", "notification", False, "odd"),
    ("2026-11-08", "2026-11-08", "Diwali", "holiday", True, "odd"),
    ("2026-11-13", "2026-11-13", "Practical Exam End / End of Classes", "exam", True, "odd"),
    ("2026-11-02", "2026-11-13", "Practical Examination", "exam", True, "odd"),
    ("2026-11-16", "2026-11-16", "END SEM Exam Start", "exam", True, "odd"),
    ("2026-11-24", "2026-11-24", "Guru Nanak Jayanti", "holiday", True, "odd"),
    ("2026-11-30", "2026-11-30", "End Semester Exam End", "exam", True, "odd"),
    ("2026-11-16", "2026-11-30", "END SEM Theory EXAM", "exam", True, "odd"),
    ("2026-12-01", "2026-12-09", "Culrav + Avishkar + Gnosiomania", "festival", True, "odd"),
    ("2026-12-13", "2026-12-13", "Submission of Grades", "admin", False, "odd"),
    ("2026-12-14", "2026-12-14", "Online Registration Start (Even) / MT/PhD Evaluation End", "registration", False, "odd"),
    ("2026-12-21", "2026-12-21", "Winter Vacation Start", "vacation", True, "odd"),
    ("2026-12-24", "2026-12-24", "Declaration of Results", "result", False, "odd"),
    ("2026-12-25", "2026-12-25", "Christmas Day", "holiday", True, "odd"),
    ("2026-12-21", "2027-01-01", "Winter Vacation", "vacation", True, "odd"),
    # ----- Even Semester 2026-27 (Jan 2027 - Jul 2027) -----
    ("2027-01-01", "2027-01-01", "Winter Vacation End / Online Registration End", "vacation_end", True, "even"),
    ("2027-01-04", "2027-01-04", "Classes Start", "instruction", False, "even"),
    ("2027-01-26", "2027-01-26", "Republic Day", "holiday", True, "even"),
    ("2027-02-05", "2027-02-07", "Annual Athletics Meet", "institute_event", True, "even"),
    ("2027-02-11", "2027-02-11", "Basant Panchami", "holiday", True, "even"),
    ("2027-03-10", "2027-03-10", "Eid-ul-Fitr", "holiday", True, "even"),
    ("2027-03-11", "2027-03-11", "1st Short Attendance Notification", "notification", False, "even"),
    ("2027-03-12", "2027-03-12", "MID SEM Exam Start", "exam", True, "even"),
    ("2027-03-19", "2027-03-19", "MID SEM Exam End", "exam", True, "even"),
    ("2027-03-12", "2027-03-19", "MID SEM Exam", "exam", True, "even"),
    ("2027-03-20", "2027-03-20", "MID SEM Break Start", "break", True, "even"),
    ("2027-03-23", "2027-03-23", "Holi", "holiday", True, "even"),
    ("2027-03-26", "2027-03-26", "Good Friday", "holiday", True, "even"),
    ("2027-03-28", "2027-03-28", "MID SEM Break End", "break", True, "even"),
    ("2027-03-20", "2027-03-28", "MID SEM Break", "break", True, "even"),
    ("2027-04-02", "2027-04-02", "MT / PhD / MCA Evaluation Start", "evaluation", True, "even"),
    ("2027-04-12", "2027-04-12", "Practical Exam", "exam", True, "even"),
    ("2027-04-15", "2027-04-15", "Ram Navami", "holiday", True, "even"),
    ("2027-04-16", "2027-04-16", "2nd Short Attendance Notification", "notification", False, "even"),
    ("2027-04-19", "2027-04-19", "Mahavir Jayanti", "holiday", True, "even"),
    ("2027-04-23", "2027-04-23", "Practical Exam End / End of Classes", "exam", True, "even"),
    ("2027-04-12", "2027-04-23", "Practical Examination", "exam", True, "even"),
    ("2027-04-26", "2027-04-26", "END SEM Theory Exam Start", "exam", True, "even"),
    ("2027-05-07", "2027-05-07", "END SEM Theory EXAM Ends / MCA Evaluation Ends", "exam", True, "even"),
    ("2027-04-26", "2027-05-07", "END SEM Theory EXAM", "exam", True, "even"),
    ("2027-05-17", "2027-05-17", "Id-Ul-Zuha", "holiday", True, "even"),
    ("2027-05-19", "2027-05-19", "Submission of Grades", "admin", False, "even"),
    ("2027-05-20", "2027-05-20", "Buddha Purnima", "holiday", True, "even"),
    ("2027-05-22", "2027-05-22", "Summer Vacation Start", "vacation", True, "even"),
    ("2027-06-04", "2027-06-04", "Declaration of Results", "result", False, "even"),
    ("2027-06-07", "2027-06-07", "Supplementary Registration Start", "registration", False, "even"),
    ("2027-06-08", "2027-06-08", "Online (Odd) Semester Registration Start", "registration", False, "even"),
    ("2027-06-09", "2027-06-09", "Supplementary Registration End", "registration", False, "even"),
    ("2027-06-14", "2027-06-14", "Supplementary Exam Start", "exam", True, "even"),
    ("2027-06-16", "2027-06-16", "Muharram", "holiday", True, "even"),
    ("2027-06-21", "2027-06-21", "Supplementary Exam End", "exam", True, "even"),
    ("2027-06-14", "2027-06-21", "Supplementary Exam", "exam", True, "even"),
    ("2027-06-24", "2027-06-24", "MT/PhD Evaluation Ends", "evaluation", True, "even"),
    ("2027-06-25", "2027-06-25", "Submission of Supplementary Grades", "admin", False, "even"),
    ("2027-07-06", "2027-07-06", "Declaration of Supplementary Result", "result", False, "even"),
    ("2027-07-08", "2027-07-08", "Summer Vacation Ends / Online (Odd) Registration Ends", "vacation_end", True, "even"),
    ("2027-05-22", "2027-07-08", "Summer Vacation", "vacation", True, "even"),
    ("2027-07-12", "2027-07-16", "Physical Registration (Odd Semester)", "registration", False, "even"),
    ("2027-07-19", "2027-07-19", "Start of Classes", "instruction", False, "even"),
]


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def parse_iso(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def daterange(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def try_extract_pdf_text(pdf_path: Path) -> str:
    if not pdf_path.exists():
        return ""
    try:
        import pymupdf
    except ImportError:
        try:
            from pypdf import PdfReader
        except ImportError:
            return ""
        reader = PdfReader(str(pdf_path))
        parts = [(page.extract_text() or "") for page in reader.pages]
        return "\n".join(parts).strip()

    text_parts = []
    document = pymupdf.open(str(pdf_path))
    try:
        for page in document:
            text_parts.append(page.get_text() or "")
    finally:
        document.close()
    return "\n".join(text_parts).strip()


def write_calendar_text() -> str:
    lines = [
        f"MNNIT Allahabad Academic Calendar {ACADEMIC_YEAR}",
        "Source: academic_calendar_rotated_compressed.pdf",
        "Odd Semester (2026-27) and Even Semester (2026-27)",
        "The declared Institute holidays will be considered final",
        "in case of any mismatch with the proposed academic calendar.",
        "",
        "FORMAT: START[..END] | LABEL | CATEGORY | BLOCK|ALLOW | SEMESTER",
        "",
    ]
    for start, end, label, category, blocks, semester in CALENDAR_EVENTS:
        span = start if start == end else f"{start}..{end}"
        flag = "BLOCK" if blocks else "ALLOW"
        lines.append(f"{span} | {label} | {category} | {flag} | {semester}")
    text = "\n".join(lines) + "\n"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CALENDAR_TEXT_FILE.write_text(text, encoding="utf-8")
    return text


EVENT_LINE_RE = None


def _event_line_pattern():
    import re

    return re.compile(
        r"^(?P<start>\d{4}-\d{2}-\d{2})"
        r"(?:\.\.(?P<end>\d{4}-\d{2}-\d{2}))?"
        r"\s*\|\s*(?P<label>[^|]+)"
        r"\s*\|\s*(?P<category>[^|]+)"
        r"\s*\|\s*(?P<flag>BLOCK|ALLOW)"
        r"\s*\|\s*(?P<semester>\w+)\s*$"
    )


def parse_academic_calendar_text(text: str) -> list[dict]:
    """Parse the generated (or hand-edited) academic calendar text."""
    pattern = _event_line_pattern()
    events = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("MNNIT") or line.startswith("Source"):
            continue
        if line.startswith("Odd ") or line.startswith("FORMAT") or line.startswith("The declared"):
            continue
        match = pattern.match(line)
        if not match:
            continue
        start = parse_iso(match.group("start"))
        end_raw = match.group("end")
        end = parse_iso(end_raw) if end_raw else start
        events.append(
            {
                "start": start.isoformat(),
                "end": end.isoformat(),
                "label": match.group("label").strip(),
                "category": match.group("category").strip(),
                "blocks_meeting": match.group("flag") == "BLOCK",
                "semester": match.group("semester").strip(),
            }
        )
    return events


def expand_restrictions(events: list[dict]) -> list[dict]:
    """One row per blocked date, merging overlapping labels."""
    by_date = {}
    for event in events:
        if not event.get("blocks_meeting"):
            continue
        start = parse_iso(event["start"])
        end = parse_iso(event["end"])
        for day in daterange(start, end):
            key = day.isoformat()
            item = by_date.setdefault(
                key,
                {
                    "date": key,
                    "weekday": calendar.day_name[day.weekday()],
                    "labels": [],
                    "categories": [],
                    "semesters": [],
                    "blocks_meeting": True,
                },
            )
            if event["label"] not in item["labels"]:
                item["labels"].append(event["label"])
            if event["category"] not in item["categories"]:
                item["categories"].append(event["category"])
            if event["semester"] not in item["semesters"]:
                item["semesters"].append(event["semester"])

    rows = []
    for key in sorted(by_date):
        item = by_date[key]
        rows.append(
            {
                "date": item["date"],
                "weekday": item["weekday"],
                "label": "; ".join(item["labels"]),
                "categories": item["categories"],
                "semester": ",".join(item["semesters"]),
                "blocks_meeting": True,
            }
        )
    return rows


def build_restrictions_document(events: list[dict], pdf_text_extracted: bool) -> dict:
    blocked = expand_restrictions(events)
    return {
        "document": "MNNIT Allahabad Academic Calendar Restrictions",
        "academic_year": ACADEMIC_YEAR,
        "timezone": TIMEZONE,
        "source_pdf": str(CALENDAR_PDF.relative_to(PROJECT_ROOT)) if CALENDAR_PDF.exists() else None,
        "source_text": str(CALENDAR_TEXT_FILE.relative_to(PROJECT_ROOT)),
        "pdf_text_extracted": pdf_text_extracted,
        "parsing_notes": [
            "The official calendar PDF is a scanned/rotated image; embedded text is empty.",
            "Events were transcribed from the Odd and Even Semester 2026-27 calendar pages.",
            "BLOCK dates cannot host DUGC/DMPC/DDPC meetings.",
            "Weekends are not listed here; the scheduling agent also skips Saturday and Sunday.",
            "Institute holidays override the academic calendar on mismatch, per the footer note.",
        ],
        "meeting_policy": {
            "allowed_weekdays": [
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
            ],
            "working_hours": {"start": "09:00", "end": "17:00"},
            "lunch_break": {"start": "13:00", "end": "14:00"},
            "default_duration_minutes": 60,
        },
        "events": events,
        "blocked_dates": blocked,
        "total_events": len(events),
        "total_blocked_dates": len(blocked),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }


# ============================================================
# Synthetic committee database
# ============================================================

def _slot(day: str, start: str, end: str, reason: str) -> dict:
    return {"day": day, "start": start, "end": end, "reason": reason}


def _member(
    member_id: str,
    name: str,
    role: str,
    email: str,
    phone: str,
    designation: str,
    busy: list[dict],
    existing: list[dict] | None = None,
) -> dict:
    return {
        "member_id": member_id,
        "name": name,
        "role": role,
        "designation": designation,
        "email": email,
        "phone": phone,
        "department": "Computer Science and Engineering",
        "weekly_busy_slots": busy,
        "existing_meetings": existing or [],
    }


def build_committee_db() -> dict:
    hod = _member(
        "CSE-HOD-001",
        "Prof. Anil Kumar Srivastava",
        "HoD",
        "hod.cse@dept.mnnit.ac.in",
        "+91-532-2278101",
        "Professor and Head",
        [
            _slot("Monday", "10:00", "12:00", "Institute Directors' meeting window"),
            _slot("Tuesday", "09:00", "11:00", "UG lecture CS-101"),
            _slot("Wednesday", "11:00", "13:00", "Ph.D. supervision slot"),
            _slot("Thursday", "14:00", "16:00", "BoG / Senate liaison"),
            _slot("Friday", "09:00", "10:00", "Department office hours"),
        ],
        [
            {
                "date": "2026-09-10",
                "start": "15:00",
                "end": "16:30",
                "title": "HoD-Conveners coordination",
            }
        ],
    )

    dugc_convener = _member(
        "CSE-DUGC-C-001",
        "Dr. Rahul Verma",
        "Convener",
        "rahul.verma@dept.mnnit.ac.in",
        "+91-532-2278202",
        "Associate Professor",
        [
            _slot("Monday", "09:00", "11:00", "B.Tech. lecture CS-301"),
            _slot("Monday", "14:00", "16:00", "Lab CS-351"),
            _slot("Tuesday", "11:00", "13:00", "Tutorial CS-301"),
            _slot("Wednesday", "09:00", "11:00", "Department UG counselling"),
            _slot("Thursday", "09:00", "12:00", "Lab CS-352"),
            _slot("Friday", "14:00", "16:00", "Project evaluation"),
        ],
    )

    dmpc_convener = _member(
        "CSE-DMPC-C-001",
        "Dr. Meera Joshi",
        "Convener",
        "meera.joshi@dept.mnnit.ac.in",
        "+91-532-2278203",
        "Associate Professor",
        [
            _slot("Monday", "11:00", "13:00", "M.Tech. lecture CS-631"),
            _slot("Tuesday", "14:00", "16:00", "M.Tech. lab CS-671"),
            _slot("Wednesday", "09:00", "11:00", "PG seminar"),
            _slot("Thursday", "11:00", "13:00", "Thesis supervision"),
            _slot("Friday", "09:00", "11:00", "M.Tech. lecture CS-641"),
        ],
        [
            {
                "date": "2026-09-18",
                "start": "15:00",
                "end": "16:00",
                "title": "Existing DMPC pre-meeting",
            }
        ],
    )

    ddpc_convener = _member(
        "CSE-DDPC-C-001",
        "Dr. Farhan Siddiqui",
        "Convener",
        "farhan.siddiqui@dept.mnnit.ac.in",
        "+91-532-2278204",
        "Associate Professor",
        [
            _slot("Monday", "14:00", "16:00", "Ph.D. coursework CS-801"),
            _slot("Tuesday", "09:00", "11:00", "Research group meeting"),
            _slot("Wednesday", "14:00", "16:00", "Doctoral seminar"),
            _slot("Thursday", "09:00", "11:00", "Ph.D. coursework CS-802"),
            _slot("Friday", "11:00", "13:00", "Thesis progress reviews"),
        ],
    )

    kavita = _member(
        "CSE-FAC-001",
        "Dr. Kavita Nair",
        "Member",
        "kavita.nair@dept.mnnit.ac.in",
        "+91-532-2278211",
        "Assistant Professor",
        [
            _slot("Monday", "09:00", "11:00", "Lecture CS-401"),
            _slot("Tuesday", "09:00", "12:00", "Lab CS-451"),
            _slot("Wednesday", "14:00", "16:00", "Lecture CS-501"),
            _slot("Thursday", "14:00", "17:00", "Lab CS-551"),
            _slot("Friday", "11:00", "13:00", "Honours mentoring"),
        ],
    )

    sandeep = _member(
        "CSE-FAC-002",
        "Dr. Sandeep Chauhan",
        "Member",
        "sandeep.chauhan@dept.mnnit.ac.in",
        "+91-532-2278212",
        "Assistant Professor",
        [
            _slot("Monday", "14:00", "17:00", "Lab CS-251"),
            _slot("Tuesday", "11:00", "13:00", "Lecture CS-201"),
            _slot("Wednesday", "11:00", "13:00", "Lecture CS-202"),
            _slot("Thursday", "09:00", "11:00", "Tutorial CS-201"),
            _slot("Friday", "14:00", "16:00", "Faculty development slot"),
        ],
    )

    priya = _member(
        "CSE-FAC-003",
        "Dr. Priya Malhotra",
        "Member",
        "priya.malhotra@dept.mnnit.ac.in",
        "+91-532-2278213",
        "Assistant Professor",
        [
            _slot("Monday", "11:00", "13:00", "Lecture CS-511"),
            _slot("Tuesday", "14:00", "17:00", "Lab CS-571"),
            _slot("Wednesday", "09:00", "12:00", "M.Tech. lab CS-672"),
            _slot("Thursday", "15:00", "17:00", "Research slot"),
            _slot("Friday", "09:00", "11:00", "Lecture CS-521"),
        ],
    )

    amitabh = _member(
        "CSE-FAC-004",
        "Dr. Amitabh Rao",
        "Member",
        "amitabh.rao@dept.mnnit.ac.in",
        "+91-532-2278214",
        "Professor",
        [
            _slot("Monday", "09:00", "10:00", "Office hours"),
            _slot("Tuesday", "09:00", "11:00", "Lecture CS-701"),
            _slot("Wednesday", "15:00", "17:00", "Sponsored project review"),
            _slot("Thursday", "11:00", "13:00", "Ph.D. comprehensive"),
            _slot("Friday", "14:00", "16:00", "Lecture CS-711"),
        ],
    )

    neha = _member(
        "CSE-FAC-005",
        "Dr. Neha Kulkarni",
        "Member",
        "neha.kulkarni@dept.mnnit.ac.in",
        "+91-532-2278215",
        "Assistant Professor",
        [
            _slot("Monday", "15:00", "17:00", "Lab CS-451-B"),
            _slot("Tuesday", "09:00", "11:00", "Lecture CS-311"),
            _slot("Wednesday", "11:00", "13:00", "Tutorial CS-311"),
            _slot("Thursday", "09:00", "12:00", "Lab CS-361"),
            _slot("Friday", "11:00", "13:00", "Lecture CS-411"),
        ],
    )

    vikram = _member(
        "CSE-FAC-006",
        "Dr. Vikram Singh",
        "Member",
        "vikram.singh@dept.mnnit.ac.in",
        "+91-532-2278216",
        "Associate Professor",
        [
            _slot("Monday", "09:00", "11:00", "Lecture CS-601"),
            _slot("Tuesday", "15:00", "17:00", "Industry lecture series"),
            _slot("Wednesday", "09:00", "11:00", "Lecture CS-611"),
            _slot("Thursday", "14:00", "16:00", "M.Tech. project slot"),
            _slot("Friday", "09:00", "12:00", "Lab CS-651"),
        ],
    )

    shalini = _member(
        "CSE-FAC-007",
        "Dr. Shalini Iyer",
        "Member Secretary",
        "shalini.iyer@dept.mnnit.ac.in",
        "+91-532-2278217",
        "Assistant Professor",
        [
            _slot("Monday", "11:00", "13:00", "Lecture CS-221"),
            _slot("Tuesday", "11:00", "13:00", "Lecture CS-222"),
            _slot("Wednesday", "14:00", "16:00", "Minutes and agenda drafting"),
            _slot("Thursday", "09:00", "11:00", "Tutorial CS-221"),
            _slot("Friday", "15:00", "17:00", "Department documentation"),
        ],
    )

    mohit = _member(
        "CSE-FAC-008",
        "Dr. Mohit Bansal",
        "Member",
        "mohit.bansal@dept.mnnit.ac.in",
        "+91-532-2278218",
        "Assistant Professor",
        [
            _slot("Monday", "14:00", "16:00", "Lecture CS-331"),
            _slot("Tuesday", "09:00", "12:00", "Lab CS-341"),
            _slot("Wednesday", "09:00", "11:00", "Lecture CS-431"),
            _slot("Thursday", "14:00", "17:00", "Lab CS-441"),
            _slot("Friday", "09:00", "11:00", "Office hours"),
        ],
    )

    committees = {
        "DUGC": {
            "committee_id": "CSE-DUGC",
            "name": "DUGC",
            "full_name": "Departmental Undergraduate Committee",
            "department": "Computer Science and Engineering",
            "whatsapp_group": {
                "name": "CSE DUGC Official",
                "id": "whatsapp:cse-dugc-official",
            },
            "email_list": "dugc.cse@dept.mnnit.ac.in",
            "hod_member_id": hod["member_id"],
            "members": [
                hod,
                dugc_convener,
                kavita,
                sandeep,
                neha,
                mohit,
                shalini,
            ],
        },
        "DMPC": {
            "committee_id": "CSE-DMPC",
            "name": "DMPC",
            "full_name": "Departmental M.Tech. Programme Committee",
            "department": "Computer Science and Engineering",
            "whatsapp_group": {
                "name": "CSE DMPC Official",
                "id": "whatsapp:cse-dmpc-official",
            },
            "email_list": "dmpc.cse@dept.mnnit.ac.in",
            "hod_member_id": hod["member_id"],
            "members": [
                hod,
                dmpc_convener,
                priya,
                vikram,
                amitabh,
                shalini,
            ],
        },
        "DDPC": {
            "committee_id": "CSE-DDPC",
            "name": "DDPC",
            "full_name": "Departmental Doctoral Programme Committee",
            "department": "Computer Science and Engineering",
            "whatsapp_group": {
                "name": "CSE DDPC Official",
                "id": "whatsapp:cse-ddpc-official",
            },
            "email_list": "ddpc.cse@dept.mnnit.ac.in",
            "hod_member_id": hod["member_id"],
            "members": [
                hod,
                ddpc_convener,
                amitabh,
                priya,
                kavita,
                vikram,
                shalini,
            ],
        },
    }

    return {
        "document": "Synthetic CSE Committee Database",
        "disclaimer": (
            "Synthetic demonstration data for the Meeting Scheduling Agent. "
            "Names, emails, phone numbers, timetables and WhatsApp groups "
            "are fictitious and are not real institutional records."
        ),
        "institute": "Motilal Nehru National Institute of Technology Allahabad",
        "department": "Computer Science and Engineering",
        "timezone": TIMEZONE,
        "academic_year": ACADEMIC_YEAR,
        "committees": committees,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }


def run_generator():
    print("========================================")
    print("DepartmentAI Scheduling Data Synthesis")
    print("========================================")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    pdf_text = try_extract_pdf_text(CALENDAR_PDF)
    pdf_extracted = bool(pdf_text)
    print(f"Calendar PDF present : {CALENDAR_PDF.exists()}")
    print(f"PDF text extracted   : {pdf_extracted}")

    calendar_text = write_calendar_text()
    events = parse_academic_calendar_text(calendar_text)
    if not events:
        raise RuntimeError("Academic calendar text parser produced 0 events.")

    restrictions = build_restrictions_document(events, pdf_extracted)
    save_json(RESTRICTIONS_FILE, restrictions)
    print(f"Events parsed        : {restrictions['total_events']}")
    print(f"Blocked dates        : {restrictions['total_blocked_dates']}")
    print(f"Wrote {RESTRICTIONS_FILE}")

    committee_db = build_committee_db()
    save_json(COMMITTEE_DB_FILE, committee_db)
    counts = {
        name: len(body["members"])
        for name, body in committee_db["committees"].items()
    }
    print(f"Committees           : {counts}")
    print(f"Wrote {COMMITTEE_DB_FILE}")
    print("========================================")
    print("Scheduling data synthesis complete.")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate synthetic committee DB and academic calendar restrictions."
    )
    parser.parse_args(argv)
    run_generator()


if __name__ == "__main__":
    main()

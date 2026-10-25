# SCHEDULING_BUILD_HISTORY

Log of how the Meeting Scheduling Agent was implemented, how synthetic data was built, and how academic-calendar parsing works.

---

## 1. Context

Project proposal (DepartmentAI Module I, item 4) requires a Meeting Scheduling Agent that checks:

- faculty timetables
- committee membership
- existing meetings
- member availability
- academic calendar restrictions

then:

- suggests suitable slots
- sends the proposed agenda to the official DUGC / DMPC / DDPC WhatsApp group
- waits for HoD consent and member availability
- prepares the meeting notice and agenda in the prescribed format
- sends them through authorized email, calendar and messaging services

Real data available: only the Academic Calendar PDF (`academic_calendar_rotated_compressed.pdf`).

Not available: real faculty timetables, real committee rolls, real WhatsApp / SMTP credentials.

Design choice: synthesise the missing databases, parse the calendar into a machine-readable block-list, expose five Python tools, wrap them with Gemini function calling, and mock the two outbound channels.

---

## 2. Academic calendar parsing

### Source

`documents/calendar/academic_calendar_rotated_compressed.pdf`

- 2 pages, landscape, `/Rotate 90`
- Producer: iLovePDF
- Each page is a single raster XObject (`/X0`, `/X1`)
- `page.get_text()` and pypdf `extract_text()` both return empty strings
- Tesseract is not installed in the build environment

The PDF was rendered with PyMuPDF and read as images. Events were transcribed from:

- Page 2: **ODD Semester (2026-27) Academic Calendar for All Students** (Jul-26 to Dec-26)
- Page 1: **Even Semester (2026-27) Academic Calendar for All Students** (Jan-27 to Jul-27)

Footer on both pages: "The declared Institute holidays will be considered final in case of any mismatch with the proposed academic calendar."

### Why a text dump exists

`synthetic_scheduler_data.py` does not hard-code the restrictions JSON only. It:

1. Attempts PDF text extraction (expected to fail).
2. Writes `academic_calendar.txt` in a stable line format:

   `YYYY-MM-DD[..YYYY-MM-DD] | LABEL | category | BLOCK|ALLOW | semester`

3. Parses that text with a regex into `events[]`.
4. Expands BLOCK events into one row per date in `blocked_dates[]`.

This keeps a real parser in the pipeline. If a future text-based calendar is supplied, the same parser can ingest it.

### Blocking policy (assumptions)

A date **blocks meetings** when its category is:

- `holiday` (Republic Day, Independence Day, Diwali, Dussehra, Holi, Christmas, Gandhi Jayanti, Id-e-Milad, Janmashtami, Eid-ul-Fitr, Ram Navami, Mahavir Jayanti, Good Friday, Buddha Purnima, Id-Ul-Zuha, Muharram, Guru Nanak Jayanti, Basant Panchami)
- `exam` including MID SEM Exam Start/End, END SEM Theory EXAM, Practical Exam, Supplementary Exam
- `break` (MID SEM Break Start/End)
- `vacation` / `vacation_end` (Winter Vacation, Summer Vacation)
- `festival` (Culrav + Avishkar + Gnosiomania, 1–9 Dec 2026)
- `institute_event` (Annual Athletics Meet, 5–7 Feb 2027)
- `evaluation` windows that overlap exam-like duties (MT/PhD evaluation start/end)

A date does **not** block meetings when it is only:

- `instruction` (Start of Classes)
- `notification` (short attendance notifications)
- `registration` / physical registration
- `result` / `admin` (declaration of results, submission of grades)

Additional agent rules (not in the JSON date list):

- Saturday and Sunday are never scheduled
- Working hours 09:00–17:00 IST
- Lunch 13:00–14:00 excluded
- Default duration 60 minutes
- Candidate starts: 09:30, 10:30, 11:30, 14:30, 15:30, 16:30

### Transcribed anchors used in tests

| Date       | Label |
| ---------- | ----- |
| 2026-10-09 | MID SEM Exam Start (Odd) |
| 2026-10-20 | Dussehra |
| 2026-11-08 | Diwali |
| 2026-11-16 | END SEM Exam Start |
| 2026-12-21 | Winter Vacation start |
| 2026-09-10 | ordinary instructional day (must NOT be blocked) |

Where the scanned grid is visually ambiguous (exact last day of a coloured bar), the labelled start/end cells on that date row were used, and spanning aliases (`MID SEM Exam`, `Winter Vacation`) were added so range checks still hit.

---

## 3. Synthetic committee database

File: `documents/scheduler/processed/synthetic_committee_db.json`

Assumptions:

- One department only: Computer Science and Engineering (the Ph.D. module is CSE-oriented).
- One HoD sits on DUGC, DMPC and DDPC (normal departmental practice).
- Each committee has a Convener plus faculty members and a Member Secretary.
- Emails use `@dept.mnnit.ac.in` (dummy domain, not a real mailbox).
- Phones are dummy `+91-532-2278xxx` numbers.
- WhatsApp groups are dummy ids (`whatsapp:cse-ddpc-official`, `whatsapp:cse-dmpc-official`, etc.). Default doctoral committee is DDPC.
- Weekly busy slots are teaching / lab / office patterns on weekdays. They are dense enough that not every hour is free, but sparse enough that a 2-week instructional window still yields 3 common slots.
- A few dated `existing_meetings` exist so the clash detector is not dead code.
- All records are flagged in the JSON `disclaimer` as synthetic.

Committee sizes:

- DUGC: 7
- DMPC: 6
- DDPC: 7

---

## 4. Function-calling architecture

```text
POST /schedule/propose
        │
        ▼
scheduling_agent.propose_meeting
        │
        ├─ (optional) Gemini loop with 5 declared tools
        │
        └─ deterministic fallback always materialises:
              get_committee_members
              check_academic_calendar
              find_common_free_slots
              mock_send_whatsapp_proposal
        │
        ▼
proposal stored in PROPOSAL_STORE (status=awaiting_hod_consent)
        │
POST /schedule/approve
        │
        ▼
scheduling_agent.approve_meeting
        │
        ├─ if approved=false → status=rejected_by_hod, stop
        │
        └─ mock_send_official_invite
              email notice (printed)
              .ics file on disk
              dispatch_log.jsonl
```

### Why fallback always runs

Gemini function calling is the declared interface, but:

- the sandbox may lack a usable key
- tool-call argument JSON from the model can omit fields
- tests must be hermetic

So Gemini is asked first when `use_gemini=True`, its tool trace is attached as `llm`, and the Python tools still run to produce the canonical `proposal_id`, slots, and dispatch ids. That keeps the API contract stable.

### Tool implementation notes

- `find_common_free_slots` is interval overlap, not LLM reasoning. A member is busy if a weekly slot on that weekday or a dated existing meeting overlaps the candidate.
- `mock_send_whatsapp_proposal` and `mock_send_official_invite` never open a network socket. They log, print, append JSONL, and (for invites) write an ICS file.
- ICS uses `DTSTART;TZID=Asia/Kolkata` and lists every member as `ATTENDEE`.

### In-memory proposal store

`PROPOSAL_STORE` is a process-local dict. It is enough for the two-step demo. A later merge can persist rows in PostgreSQL next to `knowledge_chunks` without changing the route shapes.

---

## 5. API surface

Added in `backend/api/scheduler_routes.py`, mounted from `backend/main.py`:

| Method | Path | Role |
| ------ | ---- | ---- |
| POST | `/schedule/propose` | step 1 |
| POST | `/schedule/approve` | step 2 |
| GET | `/schedule/proposals` | debug |
| GET | `/schedule/proposals/{proposal_id}` | debug |

RAG `/ask` is unchanged.

---

## 6. Files created

| Path | Role |
| ---- | ---- |
| `ai/ingestion/synthetic_scheduler_data.py` | committee DB + calendar parser |
| `backend/agents/__init__.py` | package |
| `backend/agents/scheduling_tools.py` | five tools |
| `backend/agents/scheduling_agent.py` | Gemini wrapper + two-step workflow |
| `backend/api/scheduler_routes.py` | FastAPI |
| `tests/test_scheduling_agent.py` | independent tests |
| `documents/calendar/academic_calendar_rotated_compressed.pdf` | source PDF copy |
| `SCHEDULING_README.md` | operator guide |
| `SCHEDULING_BUILD_HISTORY.md` | this log |

Modified:

| Path | Change |
| ---- | ------ |
| `backend/main.py` | `include_router(scheduler_router)` |

Generated at runtime / by the synthesizer:

| Path | Change |
| ---- | ------ |
| `documents/scheduler/processed/academic_calendar.txt` | parsed source text |
| `documents/scheduler/processed/academic_calendar_restrictions.json` | block list |
| `documents/scheduler/processed/synthetic_committee_db.json` | members |
| `documents/scheduler/processed/dispatch_log.jsonl` | mock outbound log |
| `documents/scheduler/processed/MAIL-*.ics` | mock calendar invites |

---

## 7. How to re-run synthesis after calendar edits

1. Edit event lines in `write_calendar_text()` inside `synthetic_scheduler_data.py`, or edit `academic_calendar.txt` and extend the parser.
2. `python ai/ingestion/synthetic_scheduler_data.py`
3. `python -m tests.test_scheduling_agent` (or the function-by-function runner in SCHEDULING_README.md)

Do not ingest scheduler JSON into pgvector. It is operational data, not ordinance text.

# Meeting Scheduling Agent

Module for DepartmentAI (Ph.D.) that proposes DUGC / DMPC / DDPC meeting slots. The default doctoral committee is **DDPC**. It sends a simulated WhatsApp proposal for HoD consent, then issues a simulated official email plus `.ics` calendar invite.

It follows the project-proposal workflow:

1. Check faculty timetables (synthetic weekly busy slots).
2. Check committee membership (HoD, Convener, Members).
3. Check existing meetings on member calendars.
4. Check academic-calendar restrictions (Winter Vacation, MID SEM Exam, Diwali, Dussehra, END SEM Theory EXAM, holidays, breaks).
5. Suggest up to three valid slots.
6. Send the proposal to the committee WhatsApp group (mocked).
7. After HoD approval, prepare the notice and send authorized email + calendar invite (mocked).

This module is independent of the RAG / Recommendation Agent. It shares only FastAPI (`backend/main.py`) and `.env` (`GEMINI_API_KEY`).

---

## Repository structure required

```text
DepartmentAI-Replace-2026/
├── ai/ingestion/synthetic_scheduler_data.py
├── backend/
│   ├── main.py                          # includes scheduler_router
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── scheduling_tools.py          # five Python tools
│   │   └── scheduling_agent.py          # Gemini function-calling wrapper
│   └── api/
│       └── scheduler_routes.py          # POST /schedule/propose|approve
├── documents/
│   ├── calendar/
│   │   └── academic_calendar_rotated_compressed.pdf
│   └── scheduler/processed/
│       ├── academic_calendar.txt
│       ├── academic_calendar_restrictions.json
│       ├── synthetic_committee_db.json
│       └── dispatch_log.jsonl           # created at runtime
├── tests/test_scheduling_agent.py
├── SCHEDULING_README.md
└── SCHEDULING_BUILD_HISTORY.md
```

Do not put scheduler JSON under `documents/phd/processed/`. That directory is the RAG knowledge base.

---

## Data files

### `synthetic_committee_db.json`

Mock CSE committees: DUGC, DMPC, DDPC. Default doctoral committee is DDPC (Departmental Doctoral Programme Committee). DMPC remains the Masters' committee in the shared scheduler.

Each member has:

- `name`, `role` (`HoD`, `Convener`, `Member`, `Member Secretary`)
- `email`, dummy `phone`
- `weekly_busy_slots` (teaching / office / existing recurring commitments)
- optional `existing_meetings` (dated one-off clashes)

Names, emails, phones and WhatsApp group ids are fictitious.

### `academic_calendar_restrictions.json`

Parsed from the official Even/Odd Semester 2026-27 calendar PDF.

The PDF is a scanned image (no extractable text). The synthesizer writes a structured text dump, then parses it. Dates that `blocks_meeting=true` cannot host a committee meeting.

Always-blocked categories include:

- Winter Vacation
- Summer Vacation
- MID SEM Exam Start / End / window
- MID SEM Break
- END SEM Theory EXAM
- Practical examinations
- Diwali, Dussehra, Holi, Republic Day, Independence Day, Christmas, Gandhi Jayanti, and other listed holidays
- Institute festivals (Culrav / Avishkar / Gnosiomania)
- Annual Athletics Meet

Weekends are not stored in the JSON; the agent also skips Saturday and Sunday. Working hours are 09:00–17:00 IST with 13:00–14:00 lunch excluded. Default slot length is 60 minutes. Candidate starts: 09:30, 10:30, 11:30, 14:30, 15:30, 16:30.

---

## Tools (Gemini function calling)

| Tool | Purpose |
| ---- | ------- |
| `get_committee_members(committee_name)` | Load membership from the synthetic JSON |
| `check_academic_calendar(target_date_range)` | Return blocked vs allowed working days |
| `find_common_free_slots(committee_name, date_range)` | Intersect timetables + calendar; up to 3 slots |
| `mock_send_whatsapp_proposal(slots, agenda)` | Print/log a WhatsApp group message |
| `mock_send_official_invite(final_slot, agenda)` | Print/log email notice and write `.ics` |

If `GEMINI_API_KEY` is missing or Gemini fails, the agent runs the same tools in a deterministic fallback. WhatsApp and email are always simulated (console + `dispatch_log.jsonl`). No real message is sent.

---

## API

Base URL: FastAPI app in `backend/main.py` (default `http://127.0.0.1:8000`).

### `POST /schedule/propose`

Finds slots and sends the WhatsApp proposal. Returns `proposal_id` with status `awaiting_hod_consent`.

```json
{
  "committee_name": "DDPC",
  "date_range": "2026-09-14 to 2026-09-25",
  "agenda": "Second Comprehensive Examination after first-attempt failure.",
  "duration_minutes": 60,
  "use_gemini": false
}
```

`use_gemini: false` is the reliable local test path.

### `POST /schedule/approve`

Simulates HoD consent and dispatches the official invite.

```json
{
  "proposal_id": "PROP-........",
  "approved": true,
  "slot_index": 1,
  "hod_comment": "Approved.",
  "use_gemini": false
}
```

Set `"approved": false` to reject. No email/ics is sent on rejection.

Also:

- `GET /schedule/proposals`
- `GET /schedule/proposals/{proposal_id}`

Proposal state is in-memory (`PROPOSAL_STORE`). It resets when uvicorn restarts.

---

## How to run this module independently

From the repository root, with the same venv used by DepartmentAI.

```bash
python -m venv venv
```

Windows:

```powershell
.\venv\Scripts\Activate.ps1
```

Linux/macOS:

```bash
source venv/bin/activate
```

```bash
pip install -r requirements.txt
cp .env.example .env
```

`.env` needs `GEMINI_API_KEY` only if you want live function calling. Scheduling tools work without it.

Generate data:

```bash
python ai/ingestion/synthetic_scheduler_data.py
```

Expected console:

```text
Events parsed        : (40+)
Blocked dates        : (40+)
Committees           : {'DUGC': 7, 'DMPC': 6, 'DDPC': 7}
```

Unit tests (no server, no Gemini):

```bash
python -m tests.test_scheduling_agent
```

Or:

```bash
python -c "import tests.test_scheduling_agent as t
for n in dir(t):
    if n.startswith('test_'):
        getattr(t, n)(); print('PASS', n)"
```

Start API:

```bash
uvicorn backend.main:app --reload
```

Propose (Windows PowerShell use `curl.exe`):

```bash
curl -s http://127.0.0.1:8000/schedule/propose \
  -H "Content-Type: application/json" \
  -d "{\"committee_name\":\"DDPC\",\"date_range\":\"2026-09-14 to 2026-09-25\",\"agenda\":\"Comprehensive Examination cases.\",\"use_gemini\":false}"
```

Copy `proposal.proposal_id`, then:

```bash
curl -s http://127.0.0.1:8000/schedule/approve \
  -H "Content-Type: application/json" \
  -d "{\"proposal_id\":\"PROP-REPLACE\",\"approved\":true,\"slot_index\":1,\"use_gemini\":false}"
```

Server logs print the mock WhatsApp text and the official notice. An `.ics` file is written under `documents/scheduler/processed/`.

A known-good window for DDPC is `2026-09-14 to 2026-09-25` (instructional days, not mid-sem / vacation). `2026-10-09 to 2026-10-16` is fully blocked (MID SEM Exam).

---

## Merge with the existing RAG module

The RAG Recommendation Agent and this Scheduling Agent are separate.

Already done in this repo:

- `backend/main.py` includes `scheduler_router` next to the `/ask` router.
- RAG files under `backend/rag/` and `backend/llm/gemini_client.py` are unchanged in behaviour.
- New files are additive except the two-line include in `main.py`.

If you merge into another copy of DepartmentAI:

1. Copy the files listed in the tree above.
2. In `backend/main.py` add:

```python
from backend.api.scheduler_routes import router as scheduler_router
app.include_router(scheduler_router)
```

3. Run `python ai/ingestion/synthetic_scheduler_data.py` once so JSON exists.
4. Keep `documents/phd/processed/` (ordinance RAG) and `documents/scheduler/processed/` (this module) separate.
5. Optional later: the Recommendation Agent draft resolution can call `POST /schedule/propose` after a DDPC case is prepared. Do not mix scheduler JSON into pgvector unless you explicitly want calendar Q&A.

CORS already allows `localhost:5500`. Add scheduler UI later against `/schedule/propose` and `/schedule/approve`; the RAG chat UI does not need changes.

---

## Limits and assumptions

- No real faculty timetable or committee database exists; membership and busy slots are synthetic.
- WhatsApp, email and calendar sends are mocked. Replace `mock_send_*` with approved gateways to go live.
- HoD consent is the `/schedule/approve` API, not a live WhatsApp webhook.
- Default venue is "Department Committee Room / authorized hybrid link".
- Calendar year is 2026-27 as printed on the supplied PDF.
- Institute holidays override the academic calendar on mismatch (footer of the official calendar).

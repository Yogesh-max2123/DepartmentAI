from datetime import date

from backend.agents.scheduling_tools import (
    blocked_dates_set,
    check_academic_calendar,
    find_common_free_slots,
    get_committee_members,
    load_restrictions,
    mock_send_official_invite,
    mock_send_whatsapp_proposal,
    normalize_committee_name,
    parse_date_range,
)
from backend.agents.scheduling_agent import approve_meeting, propose_meeting


def test_normalize_committee_aliases():
    assert normalize_committee_name("dmpc") == "DMPC"
    assert normalize_committee_name("masters") == "DMPC"
    assert normalize_committee_name("doctoral") == "DDPC"


def test_parse_date_range_variants():
    assert parse_date_range("2026-09-07 to 2026-09-18") == (
        date(2026, 9, 7),
        date(2026, 9, 18),
    )
    assert parse_date_range("2026-10-02") == (date(2026, 10, 2), date(2026, 10, 2))


def test_get_committee_members_dmpc():
    result = get_committee_members("DMPC")
    assert result["ok"] is True
    assert result["hod"]["role"] == "HoD"
    assert result["convener"]["role"] == "Convener"
    assert result["member_count"] >= 4
    emails = {member["email"] for member in result["members"]}
    assert "hod.cse@dept.mnnit.ac.in" in emails


def test_calendar_blocks_named_events():
    blocked = blocked_dates_set()
    assert "2026-12-21" in blocked
    assert "2026-11-08" in blocked
    assert "2026-10-20" in blocked
    assert "2026-11-16" in blocked
    assert "2026-10-09" in blocked
    assert "2026-09-10" not in blocked


def test_check_academic_calendar_mid_sem():
    result = check_academic_calendar("2026-10-08 to 2026-10-10")
    blocked_dates = {row["date"] for row in result["blocked_dates"]}
    assert "2026-10-09" in blocked_dates
    labels = " ".join(row["label"] for row in result["blocked_dates"])
    assert "MID SEM Exam Start" in labels


def test_find_common_free_slots_returns_three_or_fewer():
    result = find_common_free_slots("DMPC", "2026-09-07 to 2026-09-18")
    assert result["ok"] is True
    assert 1 <= result["slot_count"] <= 3
    first = result["slots"][0]
    assert first["date"] >= "2026-09-07"
    assert first["start"] < first["end"]
    assert first["weekday"] not in {"Saturday", "Sunday"}


def test_find_common_free_slots_skips_blocked_week():
    result = find_common_free_slots("DUGC", "2026-10-09 to 2026-10-16")
    assert result["slot_count"] == 0
    assert result["blocked_dates_in_range"]


def test_whatsapp_and_invite_simulation():
    slots = find_common_free_slots("DDPC", "2026-09-07 to 2026-09-11")["slots"]
    wa = mock_send_whatsapp_proposal(slots, "Confirm Ph.D. SRC reports.", "DDPC")
    assert wa["ok"] is True
    assert wa["dispatch_id"].startswith("WA-")
    invite = mock_send_official_invite(slots[0], "Confirm Ph.D. SRC reports.", "DDPC")
    assert invite["ok"] is True
    assert invite["ics_path"].endswith(".ics")
    assert "NOTICE:" in invite["notice"]


def test_two_step_workflow_without_gemini():
    proposal = propose_meeting(
        committee_name="DMPC",
        date_range="2026-09-07 to 2026-09-18",
        agenda="Late registration and Form MP-02 deficiencies.",
        use_gemini=False,
    )
    assert proposal["ok"] is True
    proposal_id = proposal["proposal"]["proposal_id"]
    assert proposal["proposal"]["status"] == "awaiting_hod_consent"
    assert proposal["whatsapp"]["dispatch_id"]

    approved = approve_meeting(
        proposal_id=proposal_id,
        slot_index=1,
        approved=True,
        use_gemini=False,
    )
    assert approved["status"] == "notice_issued"
    assert approved["invite"]["dispatch_id"].startswith("MAIL-")


def test_hod_rejection():
    proposal = propose_meeting(
        committee_name="DUGC",
        date_range="2026-09-07 to 2026-09-18",
        agenda="UG registration cases.",
        use_gemini=False,
    )
    rejected = approve_meeting(
        proposal_id=proposal["proposal"]["proposal_id"],
        approved=False,
        hod_comment="Clash with Senate.",
        use_gemini=False,
    )
    assert rejected["status"] == "rejected_by_hod"
    assert "No official invite" in rejected["message"]


def test_restrictions_file_has_policy():
    data = load_restrictions()
    assert data["academic_year"] == "2026-27"
    assert data["total_blocked_dates"] > 20
    assert data["meeting_policy"]["default_duration_minutes"] == 60

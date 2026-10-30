import json
import os


class MinutesGenerationUnavailable(RuntimeError):
    pass


def generate_minutes_draft(meeting, records, source_references):
    if os.getenv("DEPARTMENTAI_MINUTES_LLM_APPROVED", "").lower() != "true":
        raise MinutesGenerationUnavailable(
            "External minutes generation is disabled until institutional data-sharing approval is configured."
        )

    try:
        from google.genai.errors import APIError
        from backend.llm.gemini_client import MODEL_NAME, client
    except (ImportError, RuntimeError) as error:
        raise MinutesGenerationUnavailable(
            "The configured Gemini minutes provider is unavailable."
        ) from error

    agenda = meeting["agenda"]
    source_context = {
        "agenda": [
            {
                "index": item["index"],
                "title": item["title"],
                "description": item["description"],
            }
            for item in agenda
        ],
        "notes_and_observations": [
            {
                "agenda_item_index": record["agenda_item_index"],
                "record_type": record["record_type"],
                "content": record["content"],
            }
            for record in records
            if record["record_type"] in {"NOTE", "OBSERVATION"}
        ],
        "source_references": source_references,
    }
    prompt = f"""
Prepare concise, neutral summaries of the recorded notes and observations for
each agenda item. The data below is the complete allowed source. Do not invent
facts, attendance, decisions, votes, or actions. Do not make recommendations
or determine policy. A summary may say that evidence is insufficient.

Return ONLY valid JSON with this shape:
{{"agenda_summaries":[{{"agenda_item_index":0,"summary":"..."}}, ...]}}
Include each supplied agenda index exactly once and no other keys.

MEETING CONTEXT:
{json.dumps(source_context, ensure_ascii=False)}
"""
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
        )
    except APIError as error:
        raise MinutesGenerationUnavailable(
            "The configured Gemini minutes request failed."
        ) from error

    response_text = getattr(response, "text", None)
    if not isinstance(response_text, str) or not response_text.strip():
        raise MinutesGenerationUnavailable(
            "The configured Gemini provider returned no minutes summary."
        )
    try:
        generated = json.loads(response_text)
    except json.JSONDecodeError as error:
        raise MinutesGenerationUnavailable(
            "The configured Gemini provider did not return valid structured minutes summaries."
        ) from error

    summaries = generated.get("agenda_summaries") if isinstance(generated, dict) else None
    expected_indexes = [item["index"] for item in agenda]
    if (
        not isinstance(generated, dict)
        or set(generated) != {"agenda_summaries"}
        or not isinstance(summaries, list)
        or [item.get("agenda_item_index") for item in summaries
            if isinstance(item, dict)] != expected_indexes
        or any(
            not isinstance(item, dict)
            or not isinstance(item.get("summary"), str)
            or not item["summary"].strip()
            for item in summaries
        )
    ):
        raise MinutesGenerationUnavailable(
            "The configured Gemini provider returned a mismatched agenda summary structure."
        )

    attendance_records = [
        record["content"]
        for record in records
        if record["record_type"] == "ATTENDANCE"
    ]
    decision_records = [
        {
            "agenda_item_index": record["agenda_item_index"],
            "recorded_decision": record["content"],
            "recorded_by": record["recorded_by"],
        }
        for record in records
        if record["record_type"] == "DECISION"
    ]
    return {
        "draft_notice": "AI-assisted draft; human review and approval required.",
        "meeting": {
            "committee_type": meeting["committee_type"],
            "title": meeting["title"],
            "purpose": meeting["purpose"],
            "scheduled_start": (
                meeting["proposed_slot_start"].isoformat()
                if meeting["proposed_slot_start"] is not None
                else None
            ),
        },
        "attendance_as_recorded": attendance_records,
        "sections": [
            {
                "agenda_item_index": item["index"],
                "title": item["title"],
                "ai_summary": summaries[index]["summary"],
                "human_decisions_as_recorded": [
                    decision
                    for decision in decision_records
                    if decision["agenda_item_index"] == item["index"]
                ],
            }
            for index, item in enumerate(agenda)
        ],
        "source_references": source_references,
    }

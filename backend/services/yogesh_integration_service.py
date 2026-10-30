import hashlib
import ipaddress
import json
import os
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener

from backend.academic_programmes import get_programme_corpus
from backend.database.connection import LOCAL_DATABASES, get_connection, get_database_settings
from backend.services.local_demo import local_demo_enabled


INTEGRATION_ENABLED_ENV = "DEPARTMENTAI_YOGESH_INTEGRATION_ENABLED"
INTEGRATION_TOKEN_ENV = "DEPARTMENTAI_YOGESH_INTERNAL_TOKEN"
REQUEST_TIMEOUT_SECONDS = 90
MAX_QUESTION_CHARACTERS = 8000


class YogeshIntegrationError(RuntimeError):
    def __init__(self, message, status_code=503):
        super().__init__(message)
        self.status_code = status_code


def _require_test_integration():
    if os.getenv(INTEGRATION_ENABLED_ENV, "").lower() != "true":
        raise YogeshIntegrationError(
            "The local Yogesh integration is not enabled."
        )
    if not os.getenv(INTEGRATION_TOKEN_ENV, "").strip():
        raise YogeshIntegrationError(
            "The local Yogesh integration token is not configured."
        )
    try:
        settings = get_database_settings()
        demo_enabled = local_demo_enabled()
    except (RuntimeError, ValueError) as error:
        raise YogeshIntegrationError(
            "The isolated test database profile is unavailable."
        ) from error
    if (
        settings.environment != "test"
        or settings.database != LOCAL_DATABASES["test"]
        or not demo_enabled
    ):
        raise YogeshIntegrationError(
            "The Yogesh integration is restricted to the isolated local demo."
        )


def is_integration_enabled():
    return os.getenv(INTEGRATION_ENABLED_ENV, "").lower() == "true"


def _resolve_base_url(programme):
    environment_key = f"DEPARTMENTAI_YOGESH_{programme}_URL"
    configured_url = os.getenv(environment_key, "").strip()
    if not configured_url:
        raise YogeshIntegrationError(
            f"The local {programme} Yogesh service URL is not configured."
        )
    try:
        parsed = urlsplit(configured_url)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as error:
        raise YogeshIntegrationError(
            f"The local {programme} Yogesh service URL is invalid."
        ) from error
    if (
        parsed.scheme != "http"
        or not hostname
        or parsed.username
        or parsed.password
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        raise YogeshIntegrationError(
            f"The local {programme} Yogesh service must use a loopback HTTP URL."
        )
    try:
        is_loopback = ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        is_loopback = hostname.lower() == "localhost"
    if not is_loopback or (port is not None and not 1 <= port <= 65535):
        raise YogeshIntegrationError(
            f"The local {programme} Yogesh service must use a loopback HTTP URL."
        )
    return f"http://{hostname}:{port}" if port else f"http://{hostname}"


def _post_json(url, payload):
    token = os.getenv(INTEGRATION_TOKEN_ENV, "").strip()
    if not token:
        raise YogeshIntegrationError(
            "The local Yogesh integration token is not configured."
        )
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-SoStudy-Integration-Token": token,
        },
        method="POST",
    )
    try:
        opener = build_opener(ProxyHandler({}))
        with opener.open(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            response_body = response.read(2_000_001)
    except HTTPError as error:
        raise YogeshIntegrationError(
            f"The local Yogesh service returned HTTP {error.code}."
        ) from error
    except (URLError, TimeoutError, OSError) as error:
        raise YogeshIntegrationError(
            "The local Yogesh service could not be reached."
        ) from error
    if len(response_body) > 2_000_000:
        raise YogeshIntegrationError(
            "The local Yogesh service returned an oversized response."
        )
    try:
        result = json.loads(response_body)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise YogeshIntegrationError(
            "The local Yogesh service returned invalid JSON."
        ) from error
    if not isinstance(result, dict):
        raise YogeshIntegrationError(
            "The local Yogesh service returned an invalid response."
        )
    return result


def get_meeting_options(
    programme,
    range_start,
    range_end,
    duration_minutes,
    reserved_slots,
):
    _require_test_integration()
    if programme not in {"MTECH", "PHD"}:
        raise YogeshIntegrationError(
            "Yogesh meeting options are available only for M.Tech and PhD.",
            422,
        )
    if (
        not isinstance(range_start, datetime)
        or range_start.tzinfo is None
        or range_start.utcoffset() is None
        or not isinstance(range_end, datetime)
        or range_end.tzinfo is None
        or range_end.utcoffset() is None
    ):
        raise YogeshIntegrationError(
            "Yogesh meeting range must include time zones.",
            422,
        )
    if not isinstance(duration_minutes, int) or not 30 <= duration_minutes <= 240:
        raise YogeshIntegrationError(
            "Yogesh meeting duration must be between 30 and 240 minutes.",
            422,
        )
    if not isinstance(reserved_slots, list):
        raise YogeshIntegrationError(
            "Yogesh reserved meeting slots are invalid.",
            422,
        )
    serialized_reservations = []
    for slot in reserved_slots:
        if not isinstance(slot, dict):
            raise YogeshIntegrationError(
                "Yogesh reserved meeting slots are invalid.",
                422,
            )
        start = slot.get("start")
        end = slot.get("end")
        if not isinstance(start, datetime) or not isinstance(end, datetime):
            raise YogeshIntegrationError(
                "Yogesh reserved meeting timestamps are invalid.",
                422,
            )
        if (
            start.tzinfo is None
            or end.tzinfo is None
            or start.utcoffset() is None
            or end.utcoffset() is None
            or end <= start
        ):
            raise YogeshIntegrationError(
                "Yogesh reserved meeting timestamps are invalid.",
                422,
            )
        serialized_reservations.append(
            {"start": start.isoformat(), "end": end.isoformat()}
        )

    response = _post_json(
        f"{_resolve_base_url(programme)}/integration/meeting-options",
        {
            "programme": programme,
            "range_start": range_start.isoformat(),
            "range_end": range_end.isoformat(),
            "duration_minutes": duration_minutes,
            "reserved_slots": serialized_reservations,
        },
    )
    candidate_slots = response.get("candidate_slots")
    if (
        response.get("programme") != programme
        or not isinstance(candidate_slots, list)
    ):
        raise YogeshIntegrationError(
            "The local Yogesh service returned invalid meeting options."
        )
    for slot in candidate_slots:
        if (
            not isinstance(slot, dict)
            or not isinstance(slot.get("start"), str)
            or not isinstance(slot.get("end"), str)
            or not isinstance(slot.get("candidate"), bool)
        ):
            raise YogeshIntegrationError(
                "The local Yogesh service returned invalid meeting options."
            )
        try:
            start = datetime.fromisoformat(slot["start"])
            end = datetime.fromisoformat(slot["end"])
        except ValueError as error:
            raise YogeshIntegrationError(
                "The local Yogesh service returned invalid meeting timestamps."
            ) from error
        if (
            start.tzinfo is None
            or end.tzinfo is None
            or start.utcoffset() is None
            or end.utcoffset() is None
            or end <= start
        ):
            raise YogeshIntegrationError(
                "The local Yogesh service returned invalid meeting timestamps."
            )
    return response


def _build_question(application, programme):
    fields = [
        ("Application type", application.get("application_type")),
        ("Title", application.get("title")),
        ("Description", application.get("description")),
    ]
    details = "\n".join(
        f"{label}: {value.strip()}"
        for label, value in fields
        if isinstance(value, str) and value.strip()
    )
    question = (
        f"Using only the {programme} ordinance, provide an advisory summary "
        "of the requirements relevant to this draft application. Cite the "
        "supporting sections. Do not decide whether the application is "
        "eligible, approved, or rejected.\n"
        f"{details}"
    )
    if len(question) > MAX_QUESTION_CHARACTERS:
        raise YogeshIntegrationError(
            "The draft details are too long for the local ordinance advisory.",
            422,
        )
    return question


def _validate_response(response, programme):
    answer = response.get("answer")
    sources = response.get("sources")
    if (
        response.get("programme") != programme
        or not isinstance(answer, str)
        or not answer.strip()
    ):
        raise YogeshIntegrationError(
            "The local Yogesh service returned no advisory answer."
        )
    if not isinstance(sources, list):
        raise YogeshIntegrationError(
            "The local Yogesh service returned an invalid source list."
        )
    expected_source = get_programme_corpus(programme)["source_file"]
    if not sources:
        raise YogeshIntegrationError(
            "The local Yogesh service found no ordinance source evidence."
        )
    if any(
        not isinstance(source, dict)
        or source.get("source_file") != expected_source
        for source in sources
    ):
        raise YogeshIntegrationError(
            "The local Yogesh service returned evidence outside the verified programme scope."
        )
    return answer.strip(), sources


def _application_fingerprint(application):
    serialized = json.dumps(
        {
            "application_type": application.get("application_type"),
            "title": application.get("title"),
            "description": application.get("description"),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _store_advisory(application_id, application, programme, answer, sources):
    application_fingerprint = _application_fingerprint(application)
    result = {
        "status": "COMPLETED",
        "programme": programme,
        "pipeline": f"YOGESH_{programme}_RAG",
        "answer": answer,
        "sources": sources,
        "advisory": True,
        "formal_decision": False,
        "application_fingerprint": application_fingerprint,
        "is_stale": False,
    }
    connection = get_connection()
    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT application_type, title, description, status
                    FROM applications
                    WHERE id = %s
                    FOR UPDATE;
                    """,
                    (application_id,),
                )
                current = cursor.fetchone()
                if current is None:
                    raise YogeshIntegrationError(
                        "The draft application no longer exists.",
                        404,
                    )
                current_application = {
                    "application_type": current[0],
                    "title": current[1],
                    "description": current[2],
                }
                if (
                    current[3] != "DRAFT"
                    or _application_fingerprint(current_application)
                    != application_fingerprint
                ):
                    raise YogeshIntegrationError(
                        "The draft changed during analysis; rerun the advisory.",
                        409,
                    )
                cursor.execute(
                    """
                    INSERT INTO ai_analyses (
                        application_id, analysis_type, input_reference,
                        analysis_result, recommendation, model
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id, created_at;
                    """,
                    (
                        application_id,
                        "YOGESH_RAG_ADVISORY",
                        json.dumps(
                            {
                                "programme": programme,
                                "pipeline": result["pipeline"],
                                "application_fingerprint": application_fingerprint,
                            },
                            sort_keys=True,
                        ),
                        json.dumps(result, sort_keys=True),
                        answer,
                        result["pipeline"],
                    ),
                )
                analysis_id, created_at = cursor.fetchone()
        result["analysis_id"] = analysis_id
        result["created_at"] = created_at.isoformat()
        return result
    finally:
        connection.close()


def generate_application_advisory(application_id, application, programme):
    _require_test_integration()
    if programme not in {"MTECH", "PHD"}:
        raise YogeshIntegrationError(
            "Yogesh ordinance advisory is available only for M.Tech and PhD.",
            422,
        )
    base_url = _resolve_base_url(programme)
    question = _build_question(application, programme)
    response = _post_json(
        f"{base_url}/integration/ask",
        {"question": question, "programme": programme},
    )
    answer, sources = _validate_response(response, programme)
    return _store_advisory(
        application_id,
        application,
        programme,
        answer,
        sources,
    )


def get_latest_application_advisory(application_id):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, input_reference, analysis_result, created_at
                FROM ai_analyses
                WHERE application_id = %s
                  AND analysis_type = %s
                ORDER BY id DESC
                LIMIT 1;
                """,
                (application_id, "YOGESH_RAG_ADVISORY"),
            )
            row = cursor.fetchone()
        if row is None:
            return None
        try:
            input_reference = json.loads(row[1] or "{}")
            result = json.loads(row[2] or "{}")
        except (TypeError, json.JSONDecodeError) as error:
            raise YogeshIntegrationError(
                "The saved Yogesh advisory could not be read."
            ) from error
        if not isinstance(input_reference, dict) or not isinstance(result, dict):
            raise YogeshIntegrationError(
                "The saved Yogesh advisory has an invalid shape."
            )
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT application_type, title, description
                FROM applications
                WHERE id = %s;
                """,
                (application_id,),
            )
            application_row = cursor.fetchone()
        if application_row is None:
            return None
        current_application = {
            "application_type": application_row[0],
            "title": application_row[1],
            "description": application_row[2],
        }
        result["is_stale"] = (
            input_reference.get("application_fingerprint")
            != _application_fingerprint(current_application)
        )
        result["analysis_id"] = row[0]
        result["created_at"] = row[3].isoformat()
        return result
    finally:
        connection.close()

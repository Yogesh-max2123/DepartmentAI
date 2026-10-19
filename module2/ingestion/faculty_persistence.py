from __future__ import annotations

from typing import Iterable

from module2.database.connection import get_connection
from module2.ingestion.faculty_basic import FacultyBasicData


def _clean(value) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split()).strip()


def _find_faculty_id(cur, profile_url: str) -> int | None:
    cur.execute(
        """
        SELECT id
        FROM m2_faculties
        WHERE profile_url = %s
        """,
        (profile_url,),
    )

    row = cur.fetchone()

    if row:
        return row[0]

    return None


def _upsert_faculty(
    cur,
    data: FacultyBasicData,
    profile_url: str,
    source_url: str | None = None,
) -> int:
    """
    Insert or update the master faculty record.

    profile_url is the stable identity because m2_faculties
    has a UNIQUE constraint on profile_url.
    """

    faculty_name = _clean(data.faculty_name)

    if not faculty_name:
        raise ValueError("Faculty name is empty.")

    profile_url = _clean(profile_url)

    if not profile_url:
        raise ValueError("Faculty profile URL is empty.")

    source_url = _clean(source_url) or profile_url

    cur.execute(
        """
        INSERT INTO m2_faculties (
            full_name,
            designation,
            department,
            qualification,
            area_of_interest,
            phone,
            email,
            profile_url,
            source_url,
            source_name,
            source_last_fetched_at,
            verification_status,
            is_active
        )
        VALUES (
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            CURRENT_TIMESTAMP,
            'AI_EXTRACTED',
            TRUE
        )
        ON CONFLICT (profile_url)
        DO UPDATE SET
            full_name = EXCLUDED.full_name,
            designation = EXCLUDED.designation,
            department = EXCLUDED.department,
            qualification = EXCLUDED.qualification,
            area_of_interest = EXCLUDED.area_of_interest,
            phone = EXCLUDED.phone,
            email = EXCLUDED.email,
            source_url = EXCLUDED.source_url,
            source_name = EXCLUDED.source_name,
            source_last_fetched_at = CURRENT_TIMESTAMP,
            verification_status = EXCLUDED.verification_status,
            is_active = TRUE,
            updated_at = CURRENT_TIMESTAMP
        RETURNING id
        """,
        (
            faculty_name,
            _clean(data.designation),
            _clean(data.department),
            None,
            None,
            _clean(data.telephone),
            _clean(data.email),
            profile_url,
            source_url,
            "MNNIT CSE Website",
        ),
    )

    row = cur.fetchone()

    if not row:
        raise RuntimeError(
            f"Could not obtain faculty ID for: {faculty_name}"
        )

    return row[0]


def _replace_education(
    cur,
    faculty_id: int,
    education: Iterable[dict],
    source_url: str,
):
    """
    Replace the extracted education records for one faculty member.

    The schema has no natural unique constraint for education records,
    so replacement provides deterministic/idempotent ingestion.
    """

    cur.execute(
        """
        DELETE FROM m2_education
        WHERE faculty_id = %s
        """,
        (faculty_id,),
    )

    for item in education:
        level = _clean(item.get("level"))
        details = _clean(item.get("details"))

        if not level and not details:
            continue

        cur.execute(
            """
            INSERT INTO m2_education (
                faculty_id,
                degree,
                specialization,
                institution,
                year,
                details,
                source_url
            )
            VALUES (
                %s,
                %s,
                NULL,
                NULL,
                NULL,
                %s,
                %s
            )
            """,
            (
                faculty_id,
                level or "Unknown",
                details or None,
                source_url,
            ),
        )


def _replace_courses(
    cur,
    faculty_id: int,
    data: FacultyBasicData,
    source_url: str,
):
    """
    Replace current and past course records.
    """

    cur.execute(
        """
        DELETE FROM m2_courses
        WHERE faculty_id = %s
        """,
        (faculty_id,),
    )

    course_groups = [
        ("CURRENT", data.current_courses),
        ("PAST", data.past_courses),
    ]

    for status, courses in course_groups:
        for course in courses:
            course_name = _clean(course.get("course_name"))
            course_code = _clean(course.get("course_code"))

            if not course_name:
                continue

            cur.execute(
                """
                INSERT INTO m2_courses (
                    faculty_id,
                    course_name,
                    course_status,
                    course_code,
                    academic_year,
                    semester,
                    source_url
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    NULL,
                    NULL,
                    %s
                )
                """,
                (
                    faculty_id,
                    course_name,
                    status,
                    course_code or None,
                    source_url,
                ),
            )


def _replace_research_areas(
    cur,
    faculty_id: int,
    research_areas: Iterable[str],
    source_url: str,
):
    """
    Replace research areas.

    m2_research_areas has a UNIQUE constraint on
    (faculty_id, research_area).
    """

    cur.execute(
        """
        DELETE FROM m2_research_areas
        WHERE faculty_id = %s
        """,
        (faculty_id,),
    )

    seen = set()

    for area in research_areas:
        area = _clean(area)

        if not area:
            continue

        key = area.casefold()

        if key in seen:
            continue

        seen.add(key)

        cur.execute(
            """
            INSERT INTO m2_research_areas (
                faculty_id,
                research_area,
                source_url
            )
            VALUES (
                %s,
                %s,
                %s
            )
            ON CONFLICT (
                faculty_id,
                research_area
            )
            DO NOTHING
            """,
            (
                faculty_id,
                area,
                source_url,
            ),
        )


def _replace_memberships(
    cur,
    faculty_id: int,
    memberships: Iterable[str],
    source_url: str,
):
    """
    Replace professional membership records.

    The source currently provides membership text rather than
    consistently separated organization/type/number fields.
    Therefore the original text is preserved in organization/details
    without inventing structured information.
    """

    cur.execute(
        """
        DELETE FROM m2_memberships
        WHERE faculty_id = %s
        """,
        (faculty_id,),
    )

    seen = set()

    for membership in memberships:
        membership = _clean(membership)

        if not membership:
            continue

        key = membership.casefold()

        if key in seen:
            continue

        seen.add(key)

        cur.execute(
            """
            INSERT INTO m2_memberships (
                faculty_id,
                organization,
                membership_type,
                membership_number,
                details,
                source_url
            )
            VALUES (
                %s,
                %s,
                NULL,
                NULL,
                %s,
                %s
            )
            """,
            (
                faculty_id,
                membership,
                membership,
                source_url,
            ),
        )


def _replace_research_ids(
    cur,
    faculty_id: int,
    research_ids: Iterable[dict],
    source_url: str,
):
    """
    Replace research identifier records.

    The schema has a UNIQUE constraint on
    (faculty_id, identifier_type).
    """

    cur.execute(
        """
        DELETE FROM m2_research_ids
        WHERE faculty_id = %s
        """,
        (faculty_id,),
    )

    seen_types = set()

    for item in research_ids:
        identifier_type = _clean(item.get("type"))
        identifier_value = _clean(item.get("value"))
        identifier_url = _clean(item.get("url"))

        if not identifier_type or not identifier_value:
            continue

        key = identifier_type.casefold()

        if key in seen_types:
            continue

        seen_types.add(key)

        cur.execute(
            """
            INSERT INTO m2_research_ids (
                faculty_id,
                identifier_type,
                identifier_value,
                identifier_url,
                source_url
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s
            )
            ON CONFLICT (
                faculty_id,
                identifier_type
            )
            DO UPDATE SET
                identifier_value = EXCLUDED.identifier_value,
                identifier_url = EXCLUDED.identifier_url,
                source_url = EXCLUDED.source_url
            """,
            (
                faculty_id,
                identifier_type,
                identifier_value,
                identifier_url or None,
                source_url,
            ),
        )


def persist_faculty_basic(
    data: FacultyBasicData,
    profile_url: str,
    source_url: str | None = None,
) -> int:
    """
    Persist one FacultyBasicData record and all basic-information
    child records.

    Returns:
        faculty_id
    """

    profile_url = _clean(profile_url)
    source_url = _clean(source_url) or profile_url

    if not profile_url:
        raise ValueError("profile_url is required.")

    conn = get_connection()

    try:
        with conn.transaction():
            with conn.cursor() as cur:

                faculty_id = _upsert_faculty(
                    cur=cur,
                    data=data,
                    profile_url=profile_url,
                    source_url=source_url,
                )

                _replace_education(
                    cur=cur,
                    faculty_id=faculty_id,
                    education=data.education,
                    source_url=source_url,
                )

                _replace_courses(
                    cur=cur,
                    faculty_id=faculty_id,
                    data=data,
                    source_url=source_url,
                )

                _replace_research_areas(
                    cur=cur,
                    faculty_id=faculty_id,
                    research_areas=data.research_areas,
                    source_url=source_url,
                )

                _replace_memberships(
                    cur=cur,
                    faculty_id=faculty_id,
                    memberships=data.memberships,
                    source_url=source_url,
                )

                _replace_research_ids(
                    cur=cur,
                    faculty_id=faculty_id,
                    research_ids=data.research_ids,
                    source_url=source_url,
                )

        return faculty_id

    finally:
        conn.close()


def persist_faculty_basic_from_url(
    faculty_name: str,
    profile_url: str,
    basic_url: str,
) -> int:
    """
    Convenience function:
    fetch -> extract -> persist one faculty member.
    """

    from module2.ingestion.faculty_basic import (
        extract_basic_profile_from_url,
    )

    data = extract_basic_profile_from_url(
        faculty_name=faculty_name,
        basic_url=basic_url,
    )

    return persist_faculty_basic(
        data=data,
        profile_url=profile_url,
        source_url=basic_url,
    )


if __name__ == "__main__":
    FACULTY_NAME = "Prof. M.M.Gore"

    PROFILE_URL = (
        "https://mnnit.ac.in/profile/"
        "preview.php?login=gore"
    )

    BASIC_URL = PROFILE_URL

    faculty_id = persist_faculty_basic_from_url(
        faculty_name=FACULTY_NAME,
        profile_url=PROFILE_URL,
        basic_url=BASIC_URL,
    )

    print(f"Faculty persisted successfully. ID: {faculty_id}")
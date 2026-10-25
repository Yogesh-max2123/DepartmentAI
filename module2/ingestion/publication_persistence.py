from __future__ import annotations

import json
import re
from typing import Iterable

from module2.database.connection import get_connection
from module2.ingestion.faculty_publications import (
    PublicationRecord,
    _deduplication_key,
)


def _normalize_title(title: str) -> str:
    """Normalize a publication title for database matching."""
    normalized = re.sub(
        r"[^a-z0-9]+",
        " ",
        title.lower(),
    )
    return " ".join(normalized.split())


def _normalize_person_name(name: str) -> str:
    """Normalize names for punctuation-insensitive matching."""
    value = (name or "").casefold()
    value = re.sub(
        r"(lieutenant|professor|prof|doctor|dr|mr|mrs|ms|miss|lt)",
        " ",
        value,
    )
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def _find_faculty_id(
    cursor,
    faculty_name: str,
    profile_url: str | None = None,
) -> int | None:
    """Resolve faculty by profile URL first, then unique normalized name."""
    if not faculty_name:
        return None

    # Prefer the authoritative profile URL when supplied.
    if profile_url:
        cursor.execute(
            """
            SELECT id
            FROM m2_faculties
            WHERE LOWER(RTRIM(profile_url, '/')) =
                  LOWER(RTRIM(%s, '/'))
            LIMIT 2
            """,
            (profile_url.strip(),),
        )
        rows = cursor.fetchall()

        if len(rows) == 1:
            return rows[0][0]

        if len(rows) > 1:
            raise ValueError(
                f"Ambiguous faculty profile_url in m2_faculties: "
                f"{profile_url}"
            )

    cursor.execute("SELECT id, full_name FROM m2_faculties")
    faculty_rows = cursor.fetchall()

    # Explicit aliases for known differences in source and stored names.
    aliases = {
        "m m gore": "manoj madhava gore",
        "r s yadav": "rama shankar yadav",
        "d s kushwaha": "dharmender singh kushwaha",
        "d k yadav": "dharmendra kumar yadav",
        "kailash w kalare": "kailash wamanrao kalare",
        "prasun chandra tripathi": "prasun tripathi",
    }

    source_key = _normalize_person_name(faculty_name)
    alias_target = aliases.get(source_key)
    target_keys = {source_key}

    if alias_target:
        target_keys.add(_normalize_person_name(alias_target))

    matches = [
        faculty_id
        for faculty_id, stored_name in faculty_rows
        if _normalize_person_name(stored_name) in target_keys
    ]

    if len(matches) == 1:
        return matches[0]

    if len(matches) > 1:
        raise ValueError(
            f"Ambiguous faculty name '{faculty_name}' matches multiple "
            "database rows; the directory profile URL is required."
        )

    return None


def _find_existing_publication(
    cursor,
    publication: PublicationRecord,
) -> int | None:
    """
    Find an existing publication using:

    1. DOI, when available.
    2. Otherwise normalized title + type + year.
    """

    if publication.doi:
        cursor.execute(
            """
            SELECT id
            FROM m2_publications
            WHERE LOWER(TRIM(doi)) = LOWER(TRIM(%s))
            LIMIT 1
            """,
            (publication.doi,),
        )

        row = cursor.fetchone()

        if row:
            return row[0]

    normalized_title = _normalize_title(
        publication.title
    )

    cursor.execute(
        """
        SELECT id, title
        FROM m2_publications
        WHERE publication_type = %s
          AND publication_year IS NOT DISTINCT FROM %s
        """,
        (
            publication.publication_type,
            publication.publication_year,
        ),
    )

    for publication_id, stored_title in cursor.fetchall():
        if (
            _normalize_title(stored_title)
            == normalized_title
        ):
            return publication_id

    return None


def _insert_publication(
    cursor,
    publication: PublicationRecord,
) -> int:
    """Insert a new publication and return its ID."""

    raw_metadata = publication.raw_metadata or {}

    cursor.execute(
        """
        INSERT INTO m2_publications (
            title,
            publication_type,
            journal_or_conference,
            publisher,
            publication_date,
            publication_year,
            volume,
            issue,
            pages,
            doi,
            indexing_information,
            impact_information,
            authors,
            source_url,
            source_document,
            raw_metadata
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s
        )
        RETURNING id
        """,
        (
            publication.title,
            publication.publication_type,
            publication.journal_or_conference,
            publication.publisher,
            publication.publication_date,
            publication.publication_year,
            publication.volume,
            publication.issue,
            publication.pages,
            publication.doi,
            publication.indexing_information,
            publication.impact_information,
            publication.authors,
            publication.source_url,
            publication.source_document,
            json.dumps(raw_metadata),
        ),
    )

    return cursor.fetchone()[0]


def _update_publication_metadata(
    cursor,
    publication_id: int,
    publication: PublicationRecord,
) -> None:
    """
    Fill useful fields when an existing publication is found.

    Existing non-null values are preserved.
    """

    cursor.execute(
        """
        UPDATE m2_publications
        SET
            journal_or_conference =
                COALESCE(journal_or_conference, %s),
            publisher =
                COALESCE(publisher, %s),
            publication_date =
                COALESCE(publication_date, %s),
            volume =
                COALESCE(volume, %s),
            issue =
                COALESCE(issue, %s),
            pages =
                COALESCE(pages, %s),
            doi =
                COALESCE(doi, %s),
            indexing_information =
                COALESCE(indexing_information, %s),
            impact_information =
                COALESCE(impact_information, %s),
            authors =
                COALESCE(authors, %s),
            source_url =
                COALESCE(source_url, %s),
            source_document =
                COALESCE(source_document, %s),
            raw_metadata =
                COALESCE(raw_metadata, %s::jsonb),
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (
            publication.journal_or_conference,
            publication.publisher,
            publication.publication_date,
            publication.volume,
            publication.issue,
            publication.pages,
            publication.doi,
            publication.indexing_information,
            publication.impact_information,
            publication.authors,
            publication.source_url,
            publication.source_document,
            json.dumps(publication.raw_metadata or {}),
            publication_id,
        ),
    )


def _create_faculty_publication_link(
    cursor,
    faculty_id: int,
    publication_id: int,
    author_position: int | None = None,
) -> bool:
    """
    Create faculty-publication relationship.

    Returns True if a new relationship was created.
    """

    cursor.execute(
        """
        SELECT id
        FROM m2_faculty_publications
        WHERE faculty_id = %s
          AND publication_id = %s
        LIMIT 1
        """,
        (
            faculty_id,
            publication_id,
        ),
    )

    if cursor.fetchone():
        return False

    cursor.execute(
        """
        INSERT INTO m2_faculty_publications (
            faculty_id,
            publication_id,
            author_position
        )
        VALUES (%s, %s, %s)
        """,
        (
            faculty_id,
            publication_id,
            author_position,
        ),
    )

    return True


def persist_publications(
    faculty_name: str,
    publications: Iterable[PublicationRecord],
    profile_url: str | None = None,
) -> dict[str, int]:
    """
    Persist publications for one faculty member.

    The operation is idempotent:
    - Existing publications are reused.
    - Existing faculty-publication links are not duplicated.
    """

    publications = list(publications)

    result = {
        "faculty_found": 0,
        "input_records": len(publications),
        "unique_records": 0,
        "publications_inserted": 0,
        "publications_reused": 0,
        "relationships_created": 0,
        "relationships_existing": 0,
    }

    if not faculty_name:
        raise ValueError(
            "faculty_name is required"
        )

    if not publications:
        return result

    # Final in-memory deduplication before touching the DB.
    unique_publications: list[PublicationRecord] = []
    seen: set[tuple] = set()

    for publication in publications:
        key = _deduplication_key(publication)

        if key in seen:
            continue

        seen.add(key)
        unique_publications.append(publication)

    result["unique_records"] = len(
        unique_publications
    )

    with get_connection() as connection:
        with connection.cursor() as cursor:

            faculty_id = _find_faculty_id(
                cursor,
                faculty_name,
                profile_url=profile_url,
            )

            if faculty_id is None:
                raise ValueError(
                    f"Faculty not found in m2_faculties: "
                    f"{faculty_name}"
                )

            result["faculty_found"] = 1

            for publication in unique_publications:

                publication_id = (
                    _find_existing_publication(
                        cursor,
                        publication,
                    )
                )

                if publication_id is None:
                    publication_id = _insert_publication(
                        cursor,
                        publication,
                    )

                    result[
                        "publications_inserted"
                    ] += 1

                else:
                    result[
                        "publications_reused"
                    ] += 1

                    _update_publication_metadata(
                        cursor,
                        publication_id,
                        publication,
                    )

                relationship_created = (
                    _create_faculty_publication_link(
                        cursor,
                        faculty_id,
                        publication_id,
                    )
                )

                if relationship_created:
                    result[
                        "relationships_created"
                    ] += 1
                else:
                    result[
                        "relationships_existing"
                    ] += 1

    return result


def persist_faculty_publications(
    publications: Iterable[PublicationRecord],
) -> dict[str, int]:
    """
    Convenience wrapper that takes faculty_name from the records.

    All records in one batch are expected to belong to the same faculty.
    """

    publications = list(publications)

    if not publications:
        return {
            "faculty_found": 0,
            "input_records": 0,
            "unique_records": 0,
            "publications_inserted": 0,
            "publications_reused": 0,
            "relationships_created": 0,
            "relationships_existing": 0,
        }

    faculty_names = {
        publication.faculty_name
        for publication in publications
        if publication.faculty_name
    }

    if len(faculty_names) != 1:
        raise ValueError(
            "All publications in one persistence batch "
            "must belong to exactly one faculty."
        )

    faculty_name = next(
        iter(faculty_names)
    )

    return persist_publications(
        faculty_name=faculty_name,
        publications=publications,
    )
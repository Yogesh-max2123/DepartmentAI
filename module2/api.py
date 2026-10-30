from __future__ import annotations

from contextlib import contextmanager
from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query, status

from module2.authorization import (
    Module2AccessGrant,
    get_module2_access_grant,
    require_module2_permission,
)
from module2.data_quality import (
    QUALITY_CATEGORIES,
    QUALITY_MAX_PAGE_SIZE,
    QUALITY_SCAN_LIMIT,
    build_data_quality_report,
)
from module2.database.connection import (
    Module2DatabaseConfigurationError,
    get_connection,
    get_database_settings,
)
from module2.report_routes import router as reporting_router


router = APIRouter(prefix="/module2", tags=["Module II"])
router.include_router(reporting_router, prefix="/reports", tags=["Module II Reports"])
MAX_PAGE_SIZE = 100
MIN_YEAR = 1900
MAX_YEAR = 2100

_QUALITY_QUERIES = {
    "faculty": (
        "SELECT id, full_name, department, profile_url, source_name, source_url "
        "FROM public.m2_faculties "
        "WHERE is_active IS TRUE AND department = ANY(%s) "
        "ORDER BY id LIMIT %s"
    ),
    "publications": (
        "SELECT p.id, p.title, p.publication_type, p.publication_date, "
        "p.publication_year, p.source_url "
        "FROM public.m2_publications AS p "
        "WHERE EXISTS ("
        "SELECT 1 FROM public.m2_faculty_publications AS fp "
        "JOIN public.m2_faculties AS f ON f.id = fp.faculty_id "
        "WHERE fp.publication_id = p.id AND f.is_active IS TRUE "
        "AND f.department = ANY(%s)) "
        "ORDER BY p.id LIMIT %s"
    ),
    "projects": (
        "SELECT p.id, p.title, p.funding_agency, p.start_date, p.end_date, "
        "p.source_url "
        "FROM public.m2_projects AS p "
        "WHERE EXISTS ("
        "SELECT 1 FROM public.m2_faculty_projects AS fp "
        "JOIN public.m2_faculties AS f ON f.id = fp.faculty_id "
        "WHERE fp.project_id = p.id AND f.is_active IS TRUE "
        "AND f.department = ANY(%s)) "
        "ORDER BY p.id LIMIT %s"
    ),
    "achievements": (
        "SELECT a.id, a.category, a.title, a.start_date, a.end_date, "
        "a.event_date, a.year, a.source_url "
        "FROM public.m2_achievements AS a "
        "JOIN public.m2_faculties AS f ON f.id = a.faculty_id "
        "WHERE f.is_active IS TRUE AND f.department = ANY(%s) "
        "ORDER BY a.id LIMIT %s"
    ),
}

_RESEARCH_QUERIES = {
    "publications": {
        "select": (
            "SELECT p.id, p.title, p.publication_type, "
            "p.journal_or_conference, p.publisher, p.publication_date, "
            "p.publication_year, p.doi, p.authors, p.source_url, "
            "f.department, f.id AS faculty_id, f.full_name AS faculty_name "
            "FROM public.m2_publications AS p "
            "JOIN public.m2_faculty_publications AS fp "
            "ON fp.publication_id = p.id "
            "JOIN public.m2_faculties AS f ON f.id = fp.faculty_id "
            "WHERE f.is_active IS TRUE AND f.department = ANY(%s)"
        ),
        "search": "(p.title ILIKE %s OR p.authors ILIKE %s)",
        "year": "p.publication_year",
        "order": "p.publication_year DESC NULLS LAST, p.id, f.id",
    },
    "projects": {
        "select": (
            "SELECT p.id, p.title, p.funding_agency, p.reference_number, "
            "p.start_date, p.end_date, p.status, p.description, p.source_url, "
            "f.department, f.id AS faculty_id, f.full_name AS faculty_name "
            "FROM public.m2_projects AS p "
            "JOIN public.m2_faculty_projects AS fp ON fp.project_id = p.id "
            "JOIN public.m2_faculties AS f ON f.id = fp.faculty_id "
            "WHERE f.is_active IS TRUE AND f.department = ANY(%s)"
        ),
        "search": "(p.title ILIKE %s OR p.funding_agency ILIKE %s)",
        "year": "EXTRACT(YEAR FROM p.start_date)::integer",
        "order": "p.start_date DESC NULLS LAST, p.id, f.id",
    },
    "achievements": {
        "select": (
            "SELECT a.id, a.category, a.title, a.description, a.organization, "
            "a.venue, a.role, a.event_date, a.start_date, a.end_date, a.year, "
            "a.status, a.source_url, f.department, f.id AS faculty_id, "
            "f.full_name AS faculty_name "
            "FROM public.m2_achievements AS a "
            "JOIN public.m2_faculties AS f ON f.id = a.faculty_id "
            "WHERE f.is_active IS TRUE AND f.department = ANY(%s)"
        ),
        "search": "(a.title ILIKE %s OR a.description ILIKE %s)",
        "year": "COALESCE(a.year, EXTRACT(YEAR FROM a.event_date)::integer)",
        "order": "COALESCE(a.year, EXTRACT(YEAR FROM a.event_date)) DESC, a.id",
    },
}


@contextmanager
def _database_connection():
    connection = get_connection()
    try:
        yield connection
    finally:
        connection.close()


def _validate_department_scope(
    grant: Module2AccessGrant,
    department: str | None,
) -> tuple[str, ...]:
    if not grant.departments:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No Module II department scope is configured for this account.",
        )
    if department is None:
        return grant.departments
    if department not in grant.departments:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The requested Module II record was not found.",
        )
    return (department,)


def _rows_as_dicts(cursor) -> list[dict]:
    column_names = [description.name for description in cursor.description]
    return [
        dict(zip(column_names, row))
        for row in cursor.fetchall()
    ]


def _database_unavailable(error: Exception) -> HTTPException:
    if isinstance(error, Module2DatabaseConfigurationError):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Module II database configuration is unavailable.",
        )
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Module II data service is temporarily unavailable.",
    )


@router.get("/capabilities")
def get_module2_capabilities(
    grant: Annotated[
        Module2AccessGrant,
        Depends(get_module2_access_grant),
    ],
) -> dict:
    try:
        get_database_settings()
        database_profile_configured = True
    except Module2DatabaseConfigurationError:
        database_profile_configured = False

    return {
        "permissions": sorted(grant.permissions),
        "departments": list(grant.departments),
        "database_profile_configured": database_profile_configured,
    }


@router.get("/faculty")
def list_faculty(
    grant: Annotated[
        Module2AccessGrant,
        Depends(require_module2_permission("module2.faculty.read")),
    ],
    department: str | None = Query(None, min_length=1, max_length=200),
    query: str | None = Query(None, min_length=1, max_length=200),
    limit: int = Query(50, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(0, ge=0, le=100_000),
) -> dict:
    departments = _validate_department_scope(grant, department)
    sql_query = (
        "SELECT id, full_name, designation, department, qualification, "
        "area_of_interest, profile_url, source_url, source_name, "
        "verification_status, source_last_fetched_at "
        "FROM public.m2_faculties "
        "WHERE is_active IS TRUE AND department = ANY(%s)"
    )
    parameters: list[object] = [list(departments)]
    if query is not None:
        sql_query += " AND (full_name ILIKE %s OR area_of_interest ILIKE %s)"
        search_value = f"%{query}%"
        parameters.extend((search_value, search_value))
    sql_query += " ORDER BY lower(full_name), id LIMIT %s OFFSET %s"
    parameters.extend((limit, offset))

    try:
        with _database_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql_query, parameters)
                return {"items": _rows_as_dicts(cursor), "limit": limit, "offset": offset}
    except (Module2DatabaseConfigurationError, psycopg.Error) as error:
        raise _database_unavailable(error) from error


@router.get("/faculty/{faculty_id}")
def get_faculty(
    faculty_id: int,
    grant: Annotated[
        Module2AccessGrant,
        Depends(require_module2_permission("module2.faculty.read")),
    ],
) -> dict:
    if faculty_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="faculty_id must be a positive integer.",
        )
    if not grant.departments:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No Module II department scope is configured for this account.",
        )
    try:
        with _database_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, full_name, designation, department,
                           qualification, area_of_interest, profile_url,
                           source_url, source_name, source_last_fetched_at,
                           verification_status, created_at, updated_at
                    FROM public.m2_faculties
                    WHERE id = %s AND is_active IS TRUE
                      AND department = ANY(%s);
                    """,
                    (faculty_id, list(grant.departments)),
                )
                rows = _rows_as_dicts(cursor)
    except (Module2DatabaseConfigurationError, psycopg.Error) as error:
        raise _database_unavailable(error) from error
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The requested Module II record was not found.",
        )
    return rows[0]


@router.get("/research/records/{record_type}")
def list_research_records(
    record_type: str,
    grant: Annotated[
        Module2AccessGrant,
        Depends(require_module2_permission("module2.research.read")),
    ],
    department: str | None = Query(None, min_length=1, max_length=200),
    query: str | None = Query(None, min_length=1, max_length=200),
    year_from: int | None = Query(None, ge=MIN_YEAR, le=MAX_YEAR),
    year_to: int | None = Query(None, ge=MIN_YEAR, le=MAX_YEAR),
    limit: int = Query(50, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(0, ge=0, le=100_000),
) -> dict:
    definition = _RESEARCH_QUERIES.get(record_type)
    if definition is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The requested Module II record type is not available.",
        )
    if year_from is not None and year_to is not None and year_from > year_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="year_from must not be later than year_to.",
        )
    departments = _validate_department_scope(grant, department)
    sql_query = definition["select"]
    parameters: list[object] = [list(departments)]
    if query is not None:
        sql_query += f" AND {definition['search']}"
        search_value = f"%{query}%"
        parameters.extend((search_value, search_value))
    if year_from is not None:
        sql_query += f" AND {definition['year']} >= %s"
        parameters.append(year_from)
    if year_to is not None:
        sql_query += f" AND {definition['year']} <= %s"
        parameters.append(year_to)
    sql_query += f" ORDER BY {definition['order']} LIMIT %s OFFSET %s"
    parameters.extend((limit, offset))

    try:
        with _database_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql_query, parameters)
                items = _rows_as_dicts(cursor)
    except (Module2DatabaseConfigurationError, psycopg.Error) as error:
        raise _database_unavailable(error) from error
    return {
        "record_type": record_type,
        "items": items,
        "limit": limit,
        "offset": offset,
    }


@router.get("/research/statistics")
def get_research_statistics(
    grant: Annotated[
        Module2AccessGrant,
        Depends(
            require_module2_permission("module2.research.statistics.read")
        ),
    ],
    department: str | None = Query(None, min_length=1, max_length=200),
) -> dict:
    departments = _validate_department_scope(grant, department)
    try:
        with _database_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                      (SELECT COUNT(DISTINCT p.id)
                       FROM public.m2_publications AS p
                       JOIN public.m2_faculty_publications AS fp
                         ON fp.publication_id = p.id
                       JOIN public.m2_faculties AS f ON f.id = fp.faculty_id
                       WHERE f.is_active IS TRUE AND f.department = ANY(%s))
                        AS publications,
                      (SELECT COUNT(DISTINCT p.id)
                       FROM public.m2_projects AS p
                       JOIN public.m2_faculty_projects AS fp
                         ON fp.project_id = p.id
                       JOIN public.m2_faculties AS f ON f.id = fp.faculty_id
                       WHERE f.is_active IS TRUE AND f.department = ANY(%s))
                        AS projects,
                      (SELECT COUNT(*)
                       FROM public.m2_achievements AS a
                       JOIN public.m2_faculties AS f ON f.id = a.faculty_id
                       WHERE f.is_active IS TRUE AND f.department = ANY(%s))
                        AS achievements;
                    """,
                    (
                        list(departments),
                        list(departments),
                        list(departments),
                    ),
                )
                row = cursor.fetchone()
    except (Module2DatabaseConfigurationError, psycopg.Error) as error:
        raise _database_unavailable(error) from error
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Module II statistics are unavailable.",
        )
    return {
        "scope": {"departments": list(departments)},
        "counts": {
            "publications": row[0],
            "projects": row[1],
            "achievements": row[2],
        },
        "source": "Module II persisted records",
    }


@router.get("/data-quality/issues")
def get_data_quality_issues(
    grant: Annotated[
        Module2AccessGrant,
        Depends(require_module2_permission("module2.data_quality.read")),
    ],
    category: str | None = Query(None, min_length=1, max_length=32),
    limit: int = Query(50, ge=1, le=QUALITY_MAX_PAGE_SIZE),
    offset: int = Query(0, ge=0, le=100_000),
) -> dict:
    if category is not None and category not in QUALITY_CATEGORIES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The requested data-quality category is not supported.",
        )
    if not grant.departments:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No Module II department scope is configured for this account.",
        )

    categories = (category,) if category else QUALITY_CATEGORIES
    records_by_category: dict[str, list[dict]] = {}
    try:
        with _database_connection() as connection:
            with connection.cursor() as cursor:
                for record_category in categories:
                    cursor.execute(
                        _QUALITY_QUERIES[record_category],
                        (
                            list(grant.departments),
                            QUALITY_SCAN_LIMIT + 1,
                        ),
                    )
                    records = _rows_as_dicts(cursor)
                    if len(records) > QUALITY_SCAN_LIMIT:
                        raise HTTPException(
                            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail=(
                                "The authorized dataset exceeds the bounded "
                                "data-quality review scan limit."
                            ),
                        )
                    records_by_category[record_category] = records
    except HTTPException:
        raise
    except (Module2DatabaseConfigurationError, psycopg.Error) as error:
        raise _database_unavailable(error) from error

    return build_data_quality_report(
        records_by_category,
        category=category,
        limit=limit,
        offset=offset,
    )


@router.get("/supervision")
def get_student_sensitive_supervision(
    _grant: Annotated[
        Module2AccessGrant,
        Depends(get_module2_access_grant),
    ],
) -> None:
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Student-sensitive supervision access is not configured.",
    )

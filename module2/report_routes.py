"""Authenticated, department-scoped configurable-draft report routes."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated
from urllib.parse import quote

import psycopg
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from module2.authorization import (
    Module2AccessGrant,
    authorize_module2_permission,
    get_module2_access_grant,
)
from module2.database.connection import (
    Module2DatabaseConfigurationError,
    get_connection,
)
from module2.reporting import (
    REPORT_FORMAT_MODULES,
    REPORT_MAX_ROWS,
    REPORT_MIME_TYPES,
    REPORT_PERMISSION,
    ReportFormatUnavailable,
    ReportRequestError,
    ReportSizeLimitError,
    available_report_formats,
    fetch_report_rows,
    list_report_templates,
    render_report,
    report_metadata,
    report_preview_rows,
    validate_report_request,
)


router = APIRouter()


class ReportPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_id: str = Field(..., min_length=1, max_length=64)
    year_from: int | None = Field(default=None, ge=1900, le=2100)
    year_to: int | None = Field(default=None, ge=1900, le=2100)


class ReportGenerateRequest(ReportPreviewRequest):
    format: str = Field(..., min_length=3, max_length=4)


def _authorize_report(grant: Module2AccessGrant) -> None:
    authorize_module2_permission(grant, REPORT_PERMISSION)


def _fetch_rows(
    grant: Module2AccessGrant,
    template_id: str,
    year_from: int | None,
    year_to: int | None,
) -> list[dict]:
    try:
        validate_report_request(template_id, year_from, year_to)
    except ReportRequestError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    try:
        connection = get_connection()
    except Module2DatabaseConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Module II database configuration is unavailable.",
        ) from error
    try:
        with connection.cursor() as cursor:
            return fetch_report_rows(
                cursor,
                template_id,
                grant.departments,
                {
                    key: value
                    for key, value in {
                        "year_from": year_from,
                        "year_to": year_to,
                    }.items()
                    if value is not None
                },
            )
    except ReportRequestError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    except PermissionError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No Module II department scope is configured.",
        ) from error
    except ReportSizeLimitError as error:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(error),
        ) from error
    except (Module2DatabaseConfigurationError, psycopg.Error) as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Module II report data is temporarily unavailable.",
        ) from error
    finally:
        connection.close()


@router.get("/templates")
def get_report_templates(
    grant: Annotated[
        Module2AccessGrant,
        Depends(get_module2_access_grant),
    ],
) -> dict:
    _authorize_report(grant)
    return list_report_templates()


@router.post("/preview")
def preview_report(
    request: ReportPreviewRequest,
    grant: Annotated[
        Module2AccessGrant,
        Depends(get_module2_access_grant),
    ],
) -> dict:
    _authorize_report(grant)
    rows = _fetch_rows(
        grant,
        request.template_id,
        request.year_from,
        request.year_to,
    )
    filters = {
        key: value
        for key, value in {
            "year_from": request.year_from,
            "year_to": request.year_to,
        }.items()
        if value is not None
    }
    metadata = report_metadata(
        request.template_id,
        grant.departments,
        filters,
        rows,
    )
    metadata["preview_rows"] = report_preview_rows(request.template_id, rows)
    return metadata


@router.post("/generate")
def generate_report(
    request: ReportGenerateRequest,
    grant: Annotated[
        Module2AccessGrant,
        Depends(get_module2_access_grant),
    ],
) -> Response:
    _authorize_report(grant)
    normalized_format = request.format.lower().strip().lstrip(".")
    if normalized_format not in REPORT_FORMAT_MODULES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The requested report format is not supported.",
        )
    supported_formats, _ = available_report_formats()
    if normalized_format not in supported_formats:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The requested report format is unavailable on this server.",
        )
    rows = _fetch_rows(
        grant,
        request.template_id,
        request.year_from,
        request.year_to,
    )
    filters = {
        key: value
        for key, value in {
            "year_from": request.year_from,
            "year_to": request.year_to,
        }.items()
        if value is not None
    }
    generated_at = datetime.now(timezone.utc)
    metadata = report_metadata(
        request.template_id,
        grant.departments,
        filters,
        rows,
        generated_at,
    )
    try:
        content, media_type, extension = render_report(
            request.template_id,
            rows,
            metadata,
            normalized_format,
        )
    except ReportRequestError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    except ReportFormatUnavailable as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The requested report format is unavailable on this server.",
        ) from error
    except ModuleNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The requested report format is unavailable on this server.",
        ) from error
    except (ImportError, OSError) as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The report could not be generated with the configured format.",
        ) from error

    filename = (
        f"departmentai-draft-{request.template_id}-"
        f"{generated_at.strftime('%Y%m%dT%H%M%SZ')}.{extension}"
    )
    return Response(
        content=content,
        media_type=media_type or REPORT_MIME_TYPES[normalized_format],
        headers={
            "Content-Disposition": f'attachment; filename="{quote(filename)}"',
            "Cache-Control": "no-store",
            "Pragma": "no-cache",
            "X-Report-Status": "DRAFT_NOT_OFFICIAL",
            "X-Report-Generated-At": generated_at.isoformat(),
            "X-Report-Record-Count": str(len(rows)),
            "X-Report-Max-Rows": str(REPORT_MAX_ROWS),
        },
    )

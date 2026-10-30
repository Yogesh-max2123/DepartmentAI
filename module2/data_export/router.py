"""Authenticated, permission-scoped Module II dataset export routes."""
from __future__ import annotations

from typing import Annotated
from urllib.parse import quote

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response

from module2.authorization import (
    Module2AccessGrant,
    authorize_module2_permission,
    get_module2_access_grant,
)
from module2.data_export.service import (
    DEFAULT_EXPORT_ROWS,
    EXPORT_DATASETS,
    MAX_EXPORT_ROWS,
    SUPPORTED_FORMATS,
    fetch_dataset,
    list_export_datasets,
    render_export,
)
from module2.database.connection import Module2DatabaseConfigurationError


router = APIRouter()


def _require_export_access(grant: Module2AccessGrant) -> None:
    if not any(
        dataset.permission in grant.permissions
        for dataset in EXPORT_DATASETS.values()
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No Module II export dataset is configured for this account.",
        )


def _database_unavailable(error: Exception) -> HTTPException:
    if isinstance(error, Module2DatabaseConfigurationError):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Module II database configuration is unavailable.",
        )
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Module II export service is temporarily unavailable.",
    )


@router.get("/datasets")
def get_export_datasets(
    grant: Annotated[
        Module2AccessGrant,
        Depends(get_module2_access_grant),
    ],
) -> dict:
    _require_export_access(grant)
    return {
        "datasets": list_export_datasets(grant.permissions),
        "formats": sorted(SUPPORTED_FORMATS),
        "max_rows": MAX_EXPORT_ROWS,
    }


@router.get("/{dataset}/download")
def download_dataset(
    dataset: str,
    grant: Annotated[
        Module2AccessGrant,
        Depends(get_module2_access_grant),
    ],
    format: str = Query(..., min_length=3, max_length=4),
    limit: int = Query(
        DEFAULT_EXPORT_ROWS,
        ge=1,
        le=MAX_EXPORT_ROWS,
    ),
    columns: list[str] | None = Query(None, max_length=20),
) -> Response:
    definition = EXPORT_DATASETS.get(dataset)
    if definition is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The requested export dataset is not available.",
        )
    authorize_module2_permission(grant, definition.permission)

    file_format = format.lower().strip().lstrip(".")
    if file_format not in SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unsupported export format.",
        )
    try:
        selected_columns, rows, truncated = fetch_dataset(
            dataset,
            departments=grant.departments,
            limit=limit,
            columns=columns,
        )
        content, media_type, extension = render_export(
            dataset,
            selected_columns,
            rows,
            file_format,
        )
    except LookupError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except PermissionError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error),
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    except (Module2DatabaseConfigurationError, psycopg.Error) as error:
        raise _database_unavailable(error) from error

    filename = f"{dataset}.{extension}"
    headers = {
        "Content-Disposition": f'attachment; filename="{quote(filename)}"',
        "X-Export-Row-Count": str(len(rows)),
        "X-Export-Truncated": "true" if truncated else "false",
    }
    return Response(content=content, media_type=media_type, headers=headers)

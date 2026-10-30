"""Allowlisted, department-scoped Module II export queries and renderers."""
from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Iterable, Sequence


SUPPORTED_FORMATS = frozenset({"csv", "xlsx", "pdf", "docx"})
MAX_EXPORT_ROWS = 10_000
DEFAULT_EXPORT_ROWS = 1_000


@dataclass(frozen=True)
class ExportDataset:
    permission: str
    columns: tuple[str, ...]
    query: str


EXPORT_DATASETS = {
    "faculty_profiles": ExportDataset(
        permission="module2.export.faculty_profiles",
        columns=(
            "id",
            "full_name",
            "designation",
            "department",
            "qualification",
            "area_of_interest",
            "profile_url",
            "source_url",
            "source_name",
            "verification_status",
        ),
        query="SELECT {columns} FROM public.m2_faculties AS f "
        "WHERE f.is_active IS TRUE AND f.department = ANY(%s) "
        "ORDER BY lower(f.full_name), f.id LIMIT %s",
    ),
    "publications": ExportDataset(
        permission="module2.export.publications",
        columns=(
            "title",
            "publication_type",
            "journal_or_conference",
            "publisher",
            "publication_date",
            "publication_year",
            "doi",
            "authors",
            "source_url",
            "department",
            "faculty_name",
        ),
        query=(
            "SELECT {columns} FROM public.m2_publications AS p "
            "JOIN public.m2_faculty_publications AS fp "
            "ON fp.publication_id = p.id "
            "JOIN public.m2_faculties AS f ON f.id = fp.faculty_id "
            "WHERE f.is_active IS TRUE AND f.department = ANY(%s) "
            "ORDER BY p.publication_year DESC NULLS LAST, p.id, f.id LIMIT %s"
        ),
    ),
}

_EXPORT_COLUMN_SQL = {
    "faculty_profiles": {
        "id": "f.id",
        "full_name": "f.full_name",
        "designation": "f.designation",
        "department": "f.department",
        "qualification": "f.qualification",
        "area_of_interest": "f.area_of_interest",
        "profile_url": "f.profile_url",
        "source_url": "f.source_url",
        "source_name": "f.source_name",
        "verification_status": "f.verification_status",
    },
    "publications": {
        "title": "p.title",
        "publication_type": "p.publication_type",
        "journal_or_conference": "p.journal_or_conference",
        "publisher": "p.publisher",
        "publication_date": "p.publication_date",
        "publication_year": "p.publication_year",
        "doi": "p.doi",
        "authors": "p.authors",
        "source_url": "p.source_url",
        "department": "f.department",
        "faculty_name": "f.full_name",
    },
}


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, default=str)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return str(value)


def _spreadsheet_text(value: str) -> str:
    if value.lstrip().startswith(("=", "+", "-", "@")):
        return f"'{value}"
    return value


def list_export_datasets(permissions: Iterable[str]) -> list[dict[str, Any]]:
    """Return only static datasets granted to this server-authorized principal."""
    permission_set = frozenset(permissions)
    return [
        {"name": name, "columns": list(dataset.columns)}
        for name, dataset in EXPORT_DATASETS.items()
        if dataset.permission in permission_set
    ]


def fetch_dataset(
    dataset: str,
    departments: Sequence[str],
    limit: int = DEFAULT_EXPORT_ROWS,
    columns: Sequence[str] | None = None,
) -> tuple[list[str], list[tuple[Any, ...]], bool]:
    """Fetch allowlisted fields inside the caller's configured department scope."""
    definition = EXPORT_DATASETS.get(dataset)
    if definition is None:
        raise LookupError("The requested export dataset is not available.")
    if not departments:
        raise PermissionError("No Module II department scope is configured.")
    if isinstance(limit, bool) or not isinstance(limit, int) or not (
        1 <= limit <= MAX_EXPORT_ROWS
    ):
        raise ValueError(f"limit must be between 1 and {MAX_EXPORT_ROWS}.")

    selected_columns = tuple(columns) if columns is not None else definition.columns
    if (
        not selected_columns
        or len(set(selected_columns)) != len(selected_columns)
        or any(column not in definition.columns for column in selected_columns)
    ):
        raise ValueError("One or more requested columns are not allowed.")

    from psycopg import sql
    from module2.database.connection import get_connection

    selected_sql = sql.SQL(", ").join(
        sql.SQL(_EXPORT_COLUMN_SQL[dataset][column])
        for column in selected_columns
    )
    query = sql.SQL(definition.query).format(columns=selected_sql)
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(query, (list(departments), limit + 1))
            fetched_rows = cursor.fetchall()
        truncated = len(fetched_rows) > limit
        return (
            list(selected_columns),
            fetched_rows[:limit],
            truncated,
        )
    finally:
        connection.close()


def render_export(
    dataset: str,
    columns: Sequence[str],
    rows: Iterable[Sequence[Any]],
    file_format: str,
) -> tuple[bytes, str, str]:
    """Return (file_bytes, MIME type, extension) for a supported format."""
    if dataset not in EXPORT_DATASETS:
        raise ValueError("The requested export dataset is not available.")
    fmt = file_format.lower().strip().lstrip(".")
    if fmt not in SUPPORTED_FORMATS:
        raise ValueError("Unsupported export format.")
    if any(column not in EXPORT_DATASETS[dataset].columns for column in columns):
        raise ValueError("One or more requested columns are not allowed.")

    headers = [str(column) for column in columns]
    data = [[_text(value) for value in row] for row in rows]

    if fmt == "csv":
        stream = io.StringIO(newline="")
        writer = csv.writer(stream, lineterminator="\r\n")
        writer.writerow(headers)
        writer.writerows(
            [_spreadsheet_text(value) for value in row]
            for row in data
        )
        return stream.getvalue().encode("utf-8-sig"), "text/csv; charset=utf-8", "csv"

    if fmt == "xlsx":
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill
        from openpyxl.utils import get_column_letter

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Export"
        sheet.append(headers)
        for cell in sheet[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="244062")
        for row in data:
            sheet.append([_spreadsheet_text(value) for value in row])
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for index, header in enumerate(headers, start=1):
            values = [len(header)] + [
                len(row[index - 1])
                for row in data
                if index - 1 < len(row)
            ]
            sheet.column_dimensions[get_column_letter(index)].width = min(
                max(max(values, default=12) + 2, 12), 48
            )
        buffer = io.BytesIO()
        workbook.save(buffer)
        return (
            buffer.getvalue(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "xlsx",
        )

    if fmt == "docx":
        from docx import Document
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.shared import Inches, Pt, RGBColor

        document = Document()
        section = document.sections[0]
        section.top_margin = Inches(0.55)
        section.bottom_margin = Inches(0.55)
        section.left_margin = Inches(0.55)
        section.right_margin = Inches(0.55)
        title = document.add_heading(f"DepartmentAI — {dataset}", level=1)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        document.add_paragraph(f"Records exported: {len(data)}")
        if headers:
            table = document.add_table(rows=1, cols=len(headers))
            table.style = "Table Grid"
            for cell, header in zip(table.rows[0].cells, headers):
                cell.text = header
                for run in cell.paragraphs[0].runs:
                    run.bold = True
                    run.font.color.rgb = RGBColor(255, 255, 255)
            for row in data:
                cells = table.add_row().cells
                for cell, value in zip(cells, row):
                    cell.text = value
                    for paragraph in cell.paragraphs:
                        for run in paragraph.runs:
                            run.font.size = Pt(8)
        buffer = io.BytesIO()
        document.save(buffer)
        return (
            buffer.getvalue(),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "docx",
        )

    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        LongTable,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        TableStyle,
    )

    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=10 * mm,
        rightMargin=10 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
        title=f"DepartmentAI — {dataset}",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ExportTitle",
        parent=styles["Title"],
        fontSize=15,
        leading=18,
        alignment=TA_CENTER,
        spaceAfter=8,
    )
    cell_style = ParagraphStyle(
        "ExportCell",
        parent=styles["BodyText"],
        fontSize=6,
        leading=7,
        wordWrap="CJK",
    )
    story = [
        Paragraph(f"DepartmentAI — {dataset}", title_style),
        Paragraph(f"Records exported: {len(data)}", styles["Normal"]),
        Spacer(1, 5 * mm),
    ]
    if headers:
        table_data = [
            [Paragraph(_escape_xml(header), cell_style) for header in headers]
        ]
        table_data.extend(
            [
                [Paragraph(_escape_xml(value), cell_style) for value in row]
                for row in data
            ]
        )
        available_width = landscape(A4)[0] - 20 * mm
        col_width = available_width / max(len(headers), 1)
        table = LongTable(
            table_data,
            colWidths=[col_width] * len(headers),
            repeatRows=1,
            hAlign="LEFT",
        )
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#244062")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 3),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        story.append(table)
    document.build(story)
    return buffer.getvalue(), "application/pdf", "pdf"


def _escape_xml(value: str) -> str:
    """Escape text before placing it inside a ReportLab Paragraph."""
    import xml.sax.saxutils

    return xml.sax.saxutils.escape(value)

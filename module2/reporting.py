"""Allow-listed configurable-draft Module II report templates and renderers."""
from __future__ import annotations

import html
import importlib.util
import io
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from decimal import Decimal
from typing import Any, Mapping, Sequence


REPORT_PERMISSION = "module2.reports.generate"
REPORT_TEMPLATE_VERSION = "1.0"
REPORT_MAX_ROWS = 2_000
REPORT_PREVIEW_MAX_ROWS = 20
REPORT_QUERY_TIMEOUT_MS = 5_000
REPORT_MAX_CELL_CHARACTERS = 4_000
REPORT_FORMAT_MODULES = {
    "docx": "docx",
    "xlsx": "openpyxl",
    "pdf": "reportlab",
}
REPORT_MIME_TYPES = {
    "docx": (
        "application/vnd.openxmlformats-officedocument."
        "wordprocessingml.document"
    ),
    "xlsx": (
        "application/vnd.openxmlformats-officedocument."
        "spreadsheetml.sheet"
    ),
    "pdf": "application/pdf",
}


class ReportRequestError(ValueError):
    """Raised when a template or its supported filters are invalid."""


class ReportSizeLimitError(RuntimeError):
    """Raised instead of returning or generating a partial report."""


class ReportFormatUnavailable(RuntimeError):
    """Raised when a report renderer dependency is unavailable."""


@dataclass(frozen=True)
class ReportTemplate:
    title: str
    description: str
    query: str
    columns: tuple[tuple[str, str], ...]
    year_expression: str | None
    limitation: str


REPORT_TEMPLATES: dict[str, ReportTemplate] = {
    "faculty_directory": ReportTemplate(
        title="Configurable Draft — Faculty Directory",
        description="Active faculty profiles in your authorized department scope.",
        query=(
            "SELECT f.id AS record_id, f.full_name, f.designation, "
            "f.department, f.qualification, f.area_of_interest, "
            "f.verification_status, f.profile_url, f.source_name, f.source_url "
            "FROM public.m2_faculties AS f "
            "WHERE f.is_active IS TRUE AND f.department = ANY(%s)"
        ),
        columns=(
            ("record_id", "Record ID"),
            ("full_name", "Faculty name"),
            ("designation", "Designation"),
            ("department", "Department"),
            ("qualification", "Qualification"),
            ("area_of_interest", "Area of interest"),
            ("verification_status", "Verification status"),
            ("profile_url", "Profile URL"),
            ("source_name", "Source name"),
            ("source_url", "Source URL"),
        ),
        year_expression=None,
        limitation=(
            "This directory is based on persisted active faculty profiles and "
            "is not a verified institutional staff census."
        ),
    ),
    "publications_summary": ReportTemplate(
        title="Configurable Draft — Publications Summary",
        description="Persisted publications linked to active in-scope faculty.",
        query=(
            "SELECT p.id AS record_id, p.title, p.publication_type, "
            "p.journal_or_conference, p.publisher, p.publication_date, "
            "p.publication_year, p.doi, p.authors, "
            "string_agg(DISTINCT f.full_name, '; ' ORDER BY f.full_name) "
            "AS faculty_names, "
            "string_agg(DISTINCT f.department, '; ' ORDER BY f.department) "
            "AS departments, p.source_url "
            "FROM public.m2_publications AS p "
            "JOIN public.m2_faculty_publications AS fp "
            "ON fp.publication_id = p.id "
            "JOIN public.m2_faculties AS f ON f.id = fp.faculty_id "
            "WHERE f.is_active IS TRUE AND f.department = ANY(%s)"
        ),
        columns=(
            ("record_id", "Record ID"),
            ("title", "Title"),
            ("publication_type", "Publication type"),
            ("journal_or_conference", "Journal or conference"),
            ("publisher", "Publisher"),
            ("publication_date", "Publication date"),
            ("publication_year", "Publication year"),
            ("doi", "DOI"),
            ("authors", "Authors"),
            ("faculty_names", "Associated faculty"),
            ("departments", "Departments"),
            ("source_url", "Source URL"),
        ),
        year_expression=(
            "COALESCE(p.publication_year, "
            "EXTRACT(YEAR FROM p.publication_date)::integer)"
        ),
        limitation=(
            "Counts persisted publication records associated with active "
            "faculty; it does not verify indexing or citation metrics."
        ),
    ),
    "projects_summary": ReportTemplate(
        title="Configurable Draft — Research Projects Summary",
        description="Persisted projects linked to active in-scope faculty.",
        query=(
            "SELECT p.id AS record_id, p.title, p.funding_agency, "
            "p.reference_number, p.start_date, p.end_date, p.status, "
            "string_agg(DISTINCT f.full_name, '; ' ORDER BY f.full_name) "
            "AS faculty_names, "
            "string_agg(DISTINCT f.department, '; ' ORDER BY f.department) "
            "AS departments, p.source_url "
            "FROM public.m2_projects AS p "
            "JOIN public.m2_faculty_projects AS fp ON fp.project_id = p.id "
            "JOIN public.m2_faculties AS f ON f.id = fp.faculty_id "
            "WHERE f.is_active IS TRUE AND f.department = ANY(%s)"
        ),
        columns=(
            ("record_id", "Record ID"),
            ("title", "Title"),
            ("funding_agency", "Funding agency"),
            ("reference_number", "Reference number"),
            ("start_date", "Start date"),
            ("end_date", "End date"),
            ("status", "Status"),
            ("faculty_names", "Associated faculty"),
            ("departments", "Departments"),
            ("source_url", "Source URL"),
        ),
        year_expression="EXTRACT(YEAR FROM p.start_date)::integer",
        limitation=(
            "Projects are included through active faculty associations; "
            "financial amounts are intentionally excluded."
        ),
    ),
    "achievements_summary": ReportTemplate(
        title="Configurable Draft — Achievements Summary",
        description="Persisted achievements belonging to active in-scope faculty.",
        query=(
            "SELECT a.id AS record_id, a.category, a.title, a.description, "
            "a.organization, a.venue, a.role, a.event_date, a.start_date, "
            "a.end_date, a.year, a.status, f.full_name AS faculty_name, "
            "f.department, a.source_url "
            "FROM public.m2_achievements AS a "
            "JOIN public.m2_faculties AS f ON f.id = a.faculty_id "
            "WHERE f.is_active IS TRUE AND f.department = ANY(%s)"
        ),
        columns=(
            ("record_id", "Record ID"),
            ("category", "Category"),
            ("title", "Title"),
            ("description", "Description"),
            ("organization", "Organization"),
            ("venue", "Venue"),
            ("role", "Role"),
            ("event_date", "Event date"),
            ("start_date", "Start date"),
            ("end_date", "End date"),
            ("year", "Year"),
            ("status", "Status"),
            ("faculty_name", "Faculty"),
            ("department", "Department"),
            ("source_url", "Source URL"),
        ),
        year_expression=(
            "COALESCE(a.year, EXTRACT(YEAR FROM a.event_date)::integer)"
        ),
        limitation=(
            "Includes only persisted achievement records; it does not assert "
            "external verification or institutional recognition."
        ),
    ),
    "department_research_overview": ReportTemplate(
        title="Configurable Draft — Department Research Overview",
        description=(
            "Persisted publication, project, and achievement counts for your "
            "authorized department scope."
        ),
        query=(
            "SELECT 'Publications' AS record_category, "
            "(SELECT COUNT(DISTINCT p.id) "
            "FROM public.m2_publications AS p "
            "JOIN public.m2_faculty_publications AS fp "
            "ON fp.publication_id = p.id "
            "JOIN public.m2_faculties AS f ON f.id = fp.faculty_id "
            "WHERE f.is_active IS TRUE AND f.department = ANY(%s)) AS count "
            "UNION ALL "
            "SELECT 'Projects' AS record_category, "
            "(SELECT COUNT(DISTINCT p.id) "
            "FROM public.m2_projects AS p "
            "JOIN public.m2_faculty_projects AS fp ON fp.project_id = p.id "
            "JOIN public.m2_faculties AS f ON f.id = fp.faculty_id "
            "WHERE f.is_active IS TRUE AND f.department = ANY(%s)) AS count "
            "UNION ALL "
            "SELECT 'Achievements' AS record_category, "
            "(SELECT COUNT(*) FROM public.m2_achievements AS a "
            "JOIN public.m2_faculties AS f ON f.id = a.faculty_id "
            "WHERE f.is_active IS TRUE AND f.department = ANY(%s)) AS count"
        ),
        columns=(
            ("record_category", "Persisted record category"),
            ("count", "Record count"),
        ),
        year_expression=None,
        limitation=(
            "Counts persisted records only. Patents, consultancy, supervision, "
            "external reporting definitions, and official accreditation "
            "requirements are not included."
        ),
    ),
}


def available_report_formats() -> tuple[list[str], dict[str, str]]:
    available = []
    unavailable = {}
    for file_format, module_name in REPORT_FORMAT_MODULES.items():
        try:
            found = importlib.util.find_spec(module_name) is not None
        except (ImportError, ValueError):
            found = False
        if found:
            available.append(file_format)
        else:
            unavailable[file_format] = (
                f"The optional {module_name} rendering dependency is not installed."
            )
    return available, unavailable


def list_report_templates() -> dict[str, Any]:
    supported_formats, unavailable_formats = available_report_formats()
    templates = []
    for template_id, template in REPORT_TEMPLATES.items():
        templates.append(
            {
                "id": template_id,
                "title": template.title,
                "version": REPORT_TEMPLATE_VERSION,
                "description": template.description,
                "columns": [
                    {"key": key, "label": label}
                    for key, label in template.columns
                ],
                "filters": ["year_from", "year_to"]
                if template.year_expression
                else [],
                "supported_formats": supported_formats,
                "unavailable_formats": unavailable_formats,
                "limitation": template.limitation,
                "status": "DRAFT_NOT_OFFICIAL",
            }
        )
    return {"templates": templates}


def validate_report_request(
    template_id: str,
    year_from: int | None,
    year_to: int | None,
) -> tuple[ReportTemplate, dict[str, int]]:
    template = REPORT_TEMPLATES.get(template_id)
    if template is None:
        raise ReportRequestError("The requested report template is not available.")
    if (
        year_from is not None
        and (isinstance(year_from, bool) or not 1900 <= year_from <= 2100)
    ) or (
        year_to is not None
        and (isinstance(year_to, bool) or not 1900 <= year_to <= 2100)
    ):
        raise ReportRequestError("Report years must be between 1900 and 2100.")
    if year_from is not None and year_to is not None and year_from > year_to:
        raise ReportRequestError("year_from must not be later than year_to.")
    if (year_from is not None or year_to is not None) and not template.year_expression:
        raise ReportRequestError(
            "The selected report template does not support reporting-period filters."
        )
    filters = {}
    if year_from is not None:
        filters["year_from"] = year_from
    if year_to is not None:
        filters["year_to"] = year_to
    return template, filters


def fetch_report_rows(
    cursor: Any,
    template_id: str,
    departments: Sequence[str],
    filters: Mapping[str, int],
) -> list[dict[str, Any]]:
    template, validated_filters = validate_report_request(
        template_id,
        filters.get("year_from"),
        filters.get("year_to"),
    )
    if not departments:
        raise PermissionError("No Module II department scope is configured.")
    cursor.execute(
        "SELECT set_config('statement_timeout', %s, true)",
        (f"{REPORT_QUERY_TIMEOUT_MS}ms",),
    )
    query = template.query
    parameters: list[Any]
    if template_id == "department_research_overview":
        parameters = [
            list(departments),
            list(departments),
            list(departments),
        ]
    else:
        parameters = [list(departments)]
    if template.year_expression:
        if "year_from" in validated_filters:
            query += f" AND {template.year_expression} >= %s"
            parameters.append(validated_filters["year_from"])
        if "year_to" in validated_filters:
            query += f" AND {template.year_expression} <= %s"
            parameters.append(validated_filters["year_to"])
    if template_id in {"publications_summary", "projects_summary"}:
        query += " GROUP BY p.id"
    if template_id == "publications_summary":
        query += " ORDER BY p.publication_year DESC NULLS LAST, p.id"
    elif template_id == "projects_summary":
        query += " ORDER BY p.start_date DESC NULLS LAST, p.id"
    elif template_id == "achievements_summary":
        query += " ORDER BY COALESCE(a.year, EXTRACT(YEAR FROM a.event_date)) DESC, a.id"
    elif template_id == "faculty_directory":
        query += " ORDER BY lower(f.full_name), f.id"
    cursor.execute(query + " LIMIT %s", (*parameters, REPORT_MAX_ROWS + 1))
    rows = cursor.fetchall()
    if len(rows) > REPORT_MAX_ROWS:
        raise ReportSizeLimitError(
            "The matching dataset exceeds the report size limit. Narrow the supported year filter or contact an administrator."
        )
    columns = [description.name for description in cursor.description]
    return [dict(zip(columns, row)) for row in rows]


def report_metadata(
    template_id: str,
    departments: Sequence[str],
    filters: Mapping[str, int],
    rows: Sequence[Mapping[str, Any]],
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    template = REPORT_TEMPLATES[template_id]
    timestamp = generated_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    summary: dict[str, Any] = {"record_count": len(rows)}
    if template_id == "department_research_overview":
        summary["total_persisted_records"] = sum(
            int(row["count"]) for row in rows
        )
    return {
        "template_id": template_id,
        "template_title": template.title,
        "template_version": REPORT_TEMPLATE_VERSION,
        "status": "DRAFT_NOT_OFFICIAL",
        "generated_at": timestamp.astimezone(timezone.utc).isoformat(),
        "scope": {
            "description": "Authenticated account's server-authorized departments",
            "departments": list(departments),
        },
        "filters": dict(filters),
        "summary": summary,
        "columns": [
            {"key": key, "label": label} for key, label in template.columns
        ],
        "limitations": [
            template.limitation,
            "Generated output is a configurable draft, not an approved institutional, Ministry, or accreditation report.",
        ],
    }


def report_preview_rows(
    template_id: str,
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, str]]:
    template = REPORT_TEMPLATES[template_id]
    return [
        {
            key: _format_cell(row.get(key))
            for key, _ in template.columns
        }
        for row in rows[:REPORT_PREVIEW_MAX_ROWS]
    ]


def _format_cell(value: Any) -> str:
    if value is None:
        text = ""
    elif isinstance(value, (datetime, date, time)):
        text = value.isoformat()
    elif isinstance(value, Decimal):
        text = str(value)
    else:
        text = str(value)
    if len(text) > REPORT_MAX_CELL_CHARACTERS:
        return text[: REPORT_MAX_CELL_CHARACTERS - 14] + " [truncated]"
    return text


def _report_table(
    template_id: str,
    rows: Sequence[Mapping[str, Any]],
) -> tuple[list[str], list[list[str]]]:
    template = REPORT_TEMPLATES[template_id]
    headers = [label for _, label in template.columns]
    data = [
        [_format_cell(row.get(key)) for key, _ in template.columns]
        for row in rows
    ]
    return headers, data


def render_report(
    template_id: str,
    rows: Sequence[Mapping[str, Any]],
    metadata: Mapping[str, Any],
    file_format: str,
) -> tuple[bytes, str, str]:
    if template_id not in REPORT_TEMPLATES:
        raise ReportRequestError("The requested report template is not available.")
    normalized_format = file_format.lower().strip().lstrip(".")
    available_formats, unavailable = available_report_formats()
    if normalized_format not in REPORT_FORMAT_MODULES:
        raise ReportRequestError("The requested report format is not supported.")
    if normalized_format not in available_formats:
        raise ReportFormatUnavailable(
            unavailable.get(normalized_format, "The report format is unavailable.")
        )

    template = REPORT_TEMPLATES[template_id]
    headers, data = _report_table(template_id, rows)
    generated_at = str(metadata["generated_at"])
    scope = ", ".join(metadata["scope"]["departments"])
    applied_filters = metadata["filters"]
    filter_text = (
        ", ".join(f"{key}: {value}" for key, value in applied_filters.items())
        if applied_filters
        else "None"
    )
    summary = metadata["summary"]
    summary_text = ", ".join(f"{key}: {value}" for key, value in summary.items())
    status_text = "DRAFT — NOT OFFICIAL OR APPROVED"

    if normalized_format == "xlsx":
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter
        from module2.data_export.service import _spreadsheet_text

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Configurable Draft"
        sheet.append([template.title])
        sheet.append([f"Template: {template_id} · Version {REPORT_TEMPLATE_VERSION}"])
        sheet.append([status_text])
        sheet.append([f"Generated at (UTC): {generated_at}"])
        sheet.append([f"Authorized department scope: {scope}"])
        sheet.append([f"Applied filters: {filter_text}"])
        sheet.append([f"Summary: {summary_text}"])
        sheet.append([f"Limitation: {template.limitation}"])
        sheet.append([])
        header_row = sheet.max_row + 1
        sheet.append(headers)
        for row in data:
            sheet.append([_spreadsheet_text(value) for value in row])
        for cell in sheet[1]:
            cell.font = Font(size=16, bold=True, color="244062")
        for cell in sheet[header_row]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="244062")
            cell.alignment = Alignment(wrap_text=True, vertical="top")
        sheet.freeze_panes = f"A{header_row + 1}"
        sheet.auto_filter.ref = (
            f"A{header_row}:{get_column_letter(len(headers))}{sheet.max_row}"
        )
        for index, header in enumerate(headers, start=1):
            lengths = [len(header)] + [
                len(row[index - 1])
                for row in data
                if index - 1 < len(row)
            ]
            sheet.column_dimensions[get_column_letter(index)].width = min(
                max(max(lengths, default=12) + 2, 12), 48
            )
        buffer = io.BytesIO()
        workbook.save(buffer)
        return (
            buffer.getvalue(),
            REPORT_MIME_TYPES[normalized_format],
            normalized_format,
        )

    if normalized_format == "docx":
        from docx import Document
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.shared import Inches, Pt, RGBColor

        document = Document()
        section = document.sections[0]
        section.top_margin = Inches(0.55)
        section.bottom_margin = Inches(0.55)
        section.left_margin = Inches(0.55)
        section.right_margin = Inches(0.55)
        title = document.add_heading(template.title, level=1)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for line in (
            f"Template: {template_id} · Version {REPORT_TEMPLATE_VERSION}",
            status_text,
            f"Generated at (UTC): {generated_at}",
            f"Authorized department scope: {scope}",
            f"Applied filters: {filter_text}",
            f"Summary: {summary_text}",
            f"Limitation: {template.limitation}",
        ):
            paragraph = document.add_paragraph(line)
            paragraph.paragraph_format.space_after = Pt(3)
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
                            run.font.size = Pt(7)
        buffer = io.BytesIO()
        document.save(buffer)
        return (
            buffer.getvalue(),
            REPORT_MIME_TYPES[normalized_format],
            normalized_format,
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
        title=template.title,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontSize=15,
        leading=18,
        alignment=TA_CENTER,
        spaceAfter=8,
    )
    metadata_style = ParagraphStyle(
        "ReportMetadata",
        parent=styles["BodyText"],
        fontSize=8,
        leading=10,
    )
    cell_style = ParagraphStyle(
        "ReportCell",
        parent=styles["BodyText"],
        fontSize=6,
        leading=7,
        wordWrap="CJK",
    )
    story = [
        Paragraph(html.escape(template.title), title_style),
        Paragraph(html.escape(status_text), metadata_style),
        Paragraph(
            html.escape(
                f"Template: {template_id} · Version {REPORT_TEMPLATE_VERSION}"
            ),
            metadata_style,
        ),
        Paragraph(html.escape(f"Generated at (UTC): {generated_at}"), metadata_style),
        Paragraph(
            html.escape(f"Authorized department scope: {scope}"),
            metadata_style,
        ),
        Paragraph(html.escape(f"Applied filters: {filter_text}"), metadata_style),
        Paragraph(html.escape(f"Summary: {summary_text}"), metadata_style),
        Paragraph(
            html.escape(f"Limitation: {template.limitation}"),
            metadata_style,
        ),
        Spacer(1, 5 * mm),
    ]
    if headers:
        table_data = [
            [Paragraph(html.escape(header), cell_style) for header in headers]
        ]
        table_data.extend(
            [
                [Paragraph(html.escape(value), cell_style) for value in row]
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
    return buffer.getvalue(), REPORT_MIME_TYPES[normalized_format], normalized_format

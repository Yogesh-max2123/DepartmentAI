"""Data discovery and file generation for Module II exports.

Only ordinary tables in PostgreSQL's public schema whose names begin with
m2_ are eligible. Table identifiers are validated against the live catalog
and quoted with psycopg.sql.Identifier.
"""
from __future__ import annotations

import csv
import io
import json
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Iterable, Sequence


SUPPORTED_FORMATS = {"csv", "xlsx", "pdf", "docx"}
MAX_EXPORT_ROWS = 100_000


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


def _validate_dataset_name(dataset: str) -> str:
    # Do not accept arbitrary SQL identifiers or non-Module-II tables.
    if not dataset.startswith("m2_") or not dataset.replace("_", "").isalnum():
        raise ValueError("Invalid dataset. Only m2_* tables can be exported.")
    return dataset


def list_export_datasets() -> list[dict[str, Any]]:
    """Return exportable Module II tables and their column names."""
    from module2.database.connection import get_connection

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT t.table_name, c.column_name, c.ordinal_position
                FROM information_schema.tables AS t
                JOIN information_schema.columns AS c
                  ON c.table_schema = t.table_schema
                 AND c.table_name = t.table_name
                WHERE t.table_schema = 'public'
                  AND t.table_type = 'BASE TABLE'
                  AND left(t.table_name, 3) = 'm2_'
                ORDER BY t.table_name, c.ordinal_position;
                """
            )
            records = cur.fetchall()
        datasets: dict[str, list[str]] = {}
        for table_name, column_name, _ordinal in records:
            datasets.setdefault(table_name, []).append(column_name)
        return [
            {"name": name, "columns": columns}
            for name, columns in datasets.items()
        ]
    finally:
        conn.close()


def fetch_dataset(dataset: str, limit: int | None = None) -> tuple[list[str], list[tuple[Any, ...]], bool]:
    """Fetch a dataset. If no limit is supplied, reject oversized exports.

    Returns (column_names, rows, truncated). An explicit limit intentionally
    permits exporting only the first N rows; without one, no rows are silently
    omitted.
    """
    dataset = _validate_dataset_name(dataset)
    if limit is not None and (limit < 1 or limit > MAX_EXPORT_ROWS):
        raise ValueError(f"limit must be between 1 and {MAX_EXPORT_ROWS}.")

    from psycopg import sql
    from module2.database.connection import get_connection

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_type = 'BASE TABLE'
                  AND table_name = %s
                  AND left(table_name, 3) = 'm2_';
                """,
                (dataset,),
            )
            if cur.fetchone() is None:
                raise LookupError(f"Exportable dataset '{dataset}' was not found.")

            query_limit = limit if limit is not None else MAX_EXPORT_ROWS + 1
            cur.execute(
                sql.SQL("SELECT * FROM {}.{} LIMIT %s").format(
                    sql.Identifier("public"), sql.Identifier(dataset)
                ),
                (query_limit,),
            )
            columns = [description.name for description in cur.description]
            rows = cur.fetchall()
        if limit is None and len(rows) > MAX_EXPORT_ROWS:
            raise OverflowError(
                f"Dataset '{dataset}' contains more than {MAX_EXPORT_ROWS:,} rows. "
                "Use an explicit limit to export a subset, or increase "
                "MAX_EXPORT_ROWS after reviewing resource requirements."
            )
        truncated = limit is not None and len(rows) == limit
        return columns, rows, truncated
    finally:
        conn.close()


def render_export(
    dataset: str,
    columns: Sequence[str],
    rows: Iterable[Sequence[Any]],
    file_format: str,
) -> tuple[bytes, str, str]:
    """Return (file_bytes, MIME type, extension) for the requested format."""
    fmt = file_format.lower().strip().lstrip(".")
    if fmt not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported format '{file_format}'. Choose csv, xlsx, pdf, or docx.")

    safe_dataset = _validate_dataset_name(dataset)
    headers = [str(c) for c in columns]
    data = [[_text(v) for v in row] for row in rows]

    if fmt == "csv":
        stream = io.StringIO(newline="")
        writer = csv.writer(stream, lineterminator="\r\n")
        writer.writerow(headers)
        writer.writerows(data)
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
            sheet.append(row)
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for index, header in enumerate(headers, start=1):
            values = [len(header)] + [len(row[index - 1]) for row in data if index - 1 < len(row)]
            sheet.column_dimensions[get_column_letter(index)].width = min(max(max(values, default=12) + 2, 12), 48)
        buffer = io.BytesIO()
        workbook.save(buffer)
        return buffer.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"

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
        title = document.add_heading(f"DepartmentAI — {safe_dataset}", level=1)
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
                # Word table cell shading is optional; text remains readable if unsupported.
                try:
                    from docx.oxml import OxmlElement
                    from docx.oxml.ns import qn
                    shading = OxmlElement("w:shd")
                    shading.set(qn("w:fill"), "244062")
                    cell._tc.get_or_add_tcPr().append(shading)
                except Exception:
                    pass
            for row in data:
                cells = table.add_row().cells
                for cell, value in zip(cells, row):
                    cell.text = value
                    for paragraph in cell.paragraphs:
                        for run in paragraph.runs:
                            run.font.size = Pt(8)
        buffer = io.BytesIO()
        document.save(buffer)
        return buffer.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx"

    # PDF: ReportLab Platypus keeps content as selectable text and allows
    # tables to flow across pages.
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, LongTable, TableStyle

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        leftMargin=10 * mm, rightMargin=10 * mm,
        topMargin=10 * mm, bottomMargin=10 * mm,
        title=f"DepartmentAI — {safe_dataset}",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ExportTitle", parent=styles["Title"], fontSize=15,
        leading=18, alignment=TA_CENTER, spaceAfter=8,
    )
    cell_style = ParagraphStyle(
        "ExportCell", parent=styles["BodyText"], fontSize=6,
        leading=7, wordWrap="CJK",
    )
    story = [
        Paragraph(f"DepartmentAI — {safe_dataset}", title_style),
        Paragraph(f"Records exported: {len(data)}", styles["Normal"]),
        Spacer(1, 5 * mm),
    ]
    if headers:
        table_data = [[Paragraph(_escape_xml(h), cell_style) for h in headers]]
        table_data.extend([
            [Paragraph(_escape_xml(v), cell_style) for v in row]
            for row in data
        ])
        available_width = landscape(A4)[0] - 20 * mm
        col_width = available_width / max(len(headers), 1)
        table = LongTable(
            table_data, colWidths=[col_width] * len(headers),
            repeatRows=1, hAlign="LEFT",
        )
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#244062")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(table)
    doc.build(story)
    return buffer.getvalue(), "application/pdf", "pdf"


def _escape_xml(value: str) -> str:
    """Escape text before placing it inside a ReportLab Paragraph."""
    import xml.sax.saxutils
    return xml.sax.saxutils.escape(value)

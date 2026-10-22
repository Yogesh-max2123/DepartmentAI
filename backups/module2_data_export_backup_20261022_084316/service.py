"""Data discovery and polished file generation for Module II exports.

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

# Shared visual identity for human-readable exports.
NAVY = "183153"
BLUE = "245A81"
TEAL = "167D8D"
PALE_BLUE = "EAF2F8"
PALE_TEAL = "E8F5F5"
LIGHT_GREY = "F4F6F8"
MID_GREY = "D7E0E8"
DARK_TEXT = "243447"


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


def _pretty_name(dataset: str) -> str:
    """Convert an internal table name to a readable report heading."""
    return " ".join(part.capitalize() for part in dataset.removeprefix("m2_").split("_") if part)


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
        return [{"name": name, "columns": columns} for name, columns in datasets.items()]
    finally:
        conn.close()


def fetch_dataset(dataset: str, limit: int | None = None) -> tuple[list[str], list[tuple[Any, ...]], bool]:
    """Fetch a dataset and return (column_names, rows, truncated)."""
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
    report_name = _pretty_name(safe_dataset)
    headers = [str(c) for c in columns]
    data = [[_text(v) for v in row] for row in rows]
    generated_at = datetime.now().astimezone().strftime("%d %b %Y, %I:%M %p %Z")

    # CSV is intentionally kept interoperable and data-only. CSV has no
    # formatting capability; use XLSX/PDF/DOCX for styled presentation.
    if fmt == "csv":
        stream = io.StringIO(newline="")
        writer = csv.writer(stream, lineterminator="\r\n")
        writer.writerow(headers)
        writer.writerows(data)
        return stream.getvalue().encode("utf-8-sig"), "text/csv; charset=utf-8", "csv"

    if fmt == "xlsx":
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
        from openpyxl.worksheet.table import Table, TableStyleInfo
        from openpyxl.utils import get_column_letter

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Module II Data"
        sheet.sheet_view.showGridLines = False

        # Report title and compact metadata banner.
        last_col = max(len(headers), 1)
        sheet.merge_cells(start_row=1, start_column=1, end_row=1, end_column=last_col)
        title_cell = sheet.cell(1, 1, f"DEPARTMENTAI  |  {report_name.upper()}")
        title_cell.font = Font(name="Aptos Display", size=16, bold=True, color="FFFFFF")
        title_cell.fill = PatternFill("solid", fgColor=NAVY)
        title_cell.alignment = Alignment(vertical="center")
        sheet.row_dimensions[1].height = 34

        sheet.merge_cells(start_row=2, start_column=1, end_row=2, end_column=last_col)
        meta_cell = sheet.cell(2, 1, f"Module II data export  •  {len(data):,} records  •  Generated {generated_at}")
        meta_cell.font = Font(name="Aptos", size=10, color="FFFFFF")
        meta_cell.fill = PatternFill("solid", fgColor=TEAL)
        meta_cell.alignment = Alignment(vertical="center")
        sheet.row_dimensions[2].height = 23
        sheet.row_dimensions[3].height = 8

        header_row = 4
        for col_idx, header in enumerate(headers, start=1):
            cell = sheet.cell(header_row, col_idx, header.replace("_", " ").title())
            cell.font = Font(name="Aptos", bold=True, color="FFFFFF", size=10)
            cell.fill = PatternFill("solid", fgColor=BLUE)
            cell.alignment = Alignment(vertical="center", wrap_text=True)
            cell.border = Border(bottom=Side(style="medium", color=TEAL))
        sheet.row_dimensions[header_row].height = 28

        for row_idx, row in enumerate(data, start=header_row + 1):
            for col_idx, value in enumerate(row, start=1):
                cell = sheet.cell(row_idx, col_idx, value)
                cell.font = Font(name="Aptos", size=10, color=DARK_TEXT)
                cell.alignment = Alignment(vertical="top", wrap_text=True)
                if row_idx % 2:
                    cell.fill = PatternFill("solid", fgColor=LIGHT_GREY)
                cell.border = Border(bottom=Side(style="hair", color=MID_GREY))

        if headers and data:
            table_ref = f"A{header_row}:{get_column_letter(len(headers))}{header_row + len(data)}"
            table = Table(displayName="ModuleIIExport", ref=table_ref)
            table.tableStyleInfo = TableStyleInfo(
                name="TableStyleMedium2", showFirstColumn=False,
                showLastColumn=False, showRowStripes=True, showColumnStripes=False,
            )
            sheet.add_table(table)
            sheet.auto_filter.ref = table_ref
        elif headers:
            sheet.auto_filter.ref = f"A{header_row}:{get_column_letter(len(headers))}{header_row}"

        sheet.freeze_panes = "A5"
        sheet.sheet_properties.pageSetUpPr.fitToPage = True
        sheet.page_setup.orientation = "landscape"
        sheet.page_setup.fitToWidth = 1
        sheet.page_setup.fitToHeight = 0
        sheet.print_title_rows = f"1:{header_row}"
        sheet.sheet_properties.outlinePr.summaryBelow = True
        sheet.oddHeader.center.text = "&BDepartmentAI — Module II Data Export"
        sheet.oddFooter.right.text = "Page &[Page] of &[Pages]"

        for index, header in enumerate(headers, start=1):
            values = [len(header.replace("_", " "))] + [
                len(row[index - 1]) for row in data if index - 1 < len(row)
            ]
            sheet.column_dimensions[get_column_letter(index)].width = min(
                max(max(values, default=12) + 3, 14), 42
            )

        workbook.properties.title = f"DepartmentAI — {report_name}"
        workbook.properties.subject = "Module II database export"
        workbook.properties.creator = "DepartmentAI"
        buffer = io.BytesIO()
        workbook.save(buffer)
        return buffer.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"

    if fmt == "docx":
        from docx import Document
        from docx.enum.section import WD_SECTION
        from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn
        from docx.shared import Inches, Pt, RGBColor

        document = Document()
        section = document.sections[0]
        section.top_margin = Inches(0.65)
        section.bottom_margin = Inches(0.6)
        section.left_margin = Inches(0.6)
        section.right_margin = Inches(0.6)

        header_para = section.header.paragraphs[0]
        header_para.text = "DEPARTMENTAI  /  MODULE II"
        header_para.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        for run in header_para.runs:
            run.font.name = "Aptos"
            run.font.size = Pt(8)
            run.font.bold = True
            run.font.color.rgb = RGBColor.from_string(TEAL)

        title = document.add_heading(report_name, level=1)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for run in title.runs:
            run.font.name = "Aptos Display"
            run.font.color.rgb = RGBColor.from_string(NAVY)
            run.font.size = Pt(23)

        subtitle = document.add_paragraph()
        subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = subtitle.add_run("MODULE II DATA EXPORT")
        run.bold = True
        run.font.size = Pt(9)
        run.font.color.rgb = RGBColor.from_string(TEAL)

        meta = document.add_paragraph()
        meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = meta.add_run(f"{len(data):,} records  •  Generated {generated_at}")
        run.font.size = Pt(9)
        run.font.color.rgb = RGBColor.from_string("667788")
        document.add_paragraph()

        if headers:
            table = document.add_table(rows=1, cols=len(headers))
            table.style = "Table Grid"
            table.alignment = WD_TABLE_ALIGNMENT.CENTER
            table.autofit = True
            header_row = table.rows[0]
            header_row.height = Inches(0.32)
            # Repeat the table header when the table spans pages.
            tr_pr = header_row._tr.get_or_add_trPr()
            repeat = OxmlElement("w:tblHeader")
            repeat.set(qn("w:val"), "true")
            tr_pr.append(repeat)

            for cell, header in zip(header_row.cells, headers):
                cell.text = header.replace("_", " ").title()
                cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
                shading = OxmlElement("w:shd")
                shading.set(qn("w:fill"), NAVY)
                cell._tc.get_or_add_tcPr().append(shading)
                for paragraph in cell.paragraphs:
                    paragraph.paragraph_format.space_after = Pt(2)
                    for run in paragraph.runs:
                        run.bold = True
                        run.font.name = "Aptos"
                        run.font.size = Pt(8)
                        run.font.color.rgb = RGBColor(255, 255, 255)

            for row_index, row in enumerate(data):
                cells = table.add_row().cells
                for cell, value in zip(cells, row):
                    cell.text = value
                    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP
                    if row_index % 2 == 1:
                        shading = OxmlElement("w:shd")
                        shading.set(qn("w:fill"), LIGHT_GREY)
                        cell._tc.get_or_add_tcPr().append(shading)
                    for paragraph in cell.paragraphs:
                        paragraph.paragraph_format.space_after = Pt(2)
                        for run in paragraph.runs:
                            run.font.name = "Aptos"
                            run.font.size = Pt(8)
                            run.font.color.rgb = RGBColor.from_string(DARK_TEXT)

        footer = section.footer.paragraphs[0]
        footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
        footer_run = footer.add_run("DepartmentAI • Official database export • Verify source records before external submission")
        footer_run.font.size = Pt(8)
        footer_run.font.color.rgb = RGBColor.from_string("667788")

        document.core_properties.title = f"DepartmentAI — {report_name}"
        document.core_properties.subject = "Module II database export"
        document.core_properties.author = "DepartmentAI"
        buffer = io.BytesIO()
        document.save(buffer)
        return buffer.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx"

    # PDF: styled, searchable report with repeating column headings and page footer.
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, LongTable, TableStyle

    navy = colors.HexColor(f"#{NAVY}")
    blue = colors.HexColor(f"#{BLUE}")
    teal = colors.HexColor(f"#{TEAL}")
    pale = colors.HexColor(f"#{PALE_BLUE}")
    grid = colors.HexColor(f"#{MID_GREY}")
    dark = colors.HexColor(f"#{DARK_TEXT}")

    buffer = io.BytesIO()
    page_size = landscape(A4)
    doc = SimpleDocTemplate(
        buffer, pagesize=page_size,
        leftMargin=12 * mm, rightMargin=12 * mm,
        topMargin=19 * mm, bottomMargin=17 * mm,
        title=f"DepartmentAI — {report_name}",
        author="DepartmentAI",
        subject="Module II database export",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ExportTitle", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=19, leading=23, textColor=navy, alignment=TA_CENTER,
        spaceAfter=3 * mm,
    )
    subtitle_style = ParagraphStyle(
        "ExportSubtitle", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=8, leading=10, textColor=teal, alignment=TA_CENTER,
        spaceAfter=2 * mm,
    )
    meta_style = ParagraphStyle(
        "ExportMeta", parent=styles["Normal"], fontSize=8,
        leading=10, textColor=colors.HexColor("#667788"), alignment=TA_CENTER,
    )
    cell_style = ParagraphStyle(
        "ExportCell", parent=styles["BodyText"], fontName="Helvetica",
        fontSize=7, leading=8.5, textColor=dark, wordWrap="CJK",
    )
    header_style = ParagraphStyle(
        "ExportHeader", parent=cell_style, fontName="Helvetica-Bold",
        fontSize=7, leading=8, textColor=colors.white,
    )
    story = [
        Paragraph("DEPARTMENTAI  /  MODULE II", subtitle_style),
        Paragraph(_escape_xml(report_name), title_style),
        Paragraph(f"{len(data):,} records &nbsp; • &nbsp; Generated {_escape_xml(generated_at)}", meta_style),
        Spacer(1, 7 * mm),
    ]

    if headers:
        table_data = [[Paragraph(_escape_xml(h.replace("_", " ").title()), header_style) for h in headers]]
        table_data.extend([
            [Paragraph(_escape_xml(v) or "—", cell_style) for v in row]
            for row in data
        ])
        available_width = page_size[0] - 24 * mm
        # Allocate more room to columns with longer headings, but prevent any
        # one column from dominating. Long cell content can wrap across lines.
        weights = [max(1, min(len(h), 28)) ** 0.65 for h in headers]
        total_weight = sum(weights) or 1
        col_widths = [available_width * weight / total_weight for weight in weights]
        table = LongTable(
            table_data, colWidths=col_widths,
            repeatRows=1, hAlign="LEFT",
        )
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), navy),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, pale]),
            ("GRID", (0, 0), (-1, -1), 0.35, grid),
            ("LINEBELOW", (0, 0), (-1, 0), 1.1, teal),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(table)

    def draw_page(canvas, document_obj):
        canvas.saveState()
        width, height = page_size
        canvas.setFillColor(navy)
        canvas.rect(0, height - 8 * mm, width, 8 * mm, fill=1, stroke=0)
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.drawString(12 * mm, height - 5.2 * mm, "DEPARTMENTAI")
        canvas.setStrokeColor(teal)
        canvas.setLineWidth(0.8)
        canvas.line(12 * mm, 12 * mm, width - 12 * mm, 12 * mm)
        canvas.setFillColor(colors.HexColor("#667788"))
        canvas.setFont("Helvetica", 7)
        canvas.drawString(12 * mm, 7.5 * mm, "Module II • Database export")
        canvas.drawRightString(width - 12 * mm, 7.5 * mm, f"Page {document_obj.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
    return buffer.getvalue(), "application/pdf", "pdf"


def _escape_xml(value: str) -> str:
    """Escape text before placing it inside a ReportLab Paragraph."""
    import xml.sax.saxutils
    return xml.sax.saxutils.escape(value)

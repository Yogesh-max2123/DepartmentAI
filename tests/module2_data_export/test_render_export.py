from io import BytesIO
from zipfile import ZipFile

import pytest

from module2.data_export.service import render_export


COLUMNS = ["id", "full_name", "area_of_interest"]
ROWS = [
    (1, "Faculty One", "Research, AI"),
    (2, "Faculty Two", None),
]


@pytest.mark.parametrize("fmt,extension,signature", [
    ("csv", "csv", b"\xef\xbb\xbf"),
    ("xlsx", "xlsx", b"PK"),
    ("docx", "docx", b"PK"),
    ("pdf", "pdf", b"%PDF"),
])
def test_export_creates_expected_file(fmt, extension, signature):
    content, mime, actual_extension = render_export(
        "faculty_profiles", COLUMNS, ROWS, fmt
    )
    assert content.startswith(signature)
    assert actual_extension == extension
    assert mime


def test_csv_contains_all_headers_and_rows():
    content, _, _ = render_export("faculty_profiles", COLUMNS, ROWS, "csv")
    text = content.decode("utf-8-sig")
    assert "id,full_name,area_of_interest" in text
    assert "Faculty One" in text
    assert "Research, AI" in text
    assert "Faculty Two" in text


def test_xlsx_contains_all_rows_and_columns():
    from openpyxl import load_workbook
    content, _, _ = render_export("faculty_profiles", COLUMNS, ROWS, "xlsx")
    sheet = load_workbook(BytesIO(content), read_only=True).active
    assert list(sheet.values) == [
        ("id", "full_name", "area_of_interest"),
        ("1", "Faculty One", "Research, AI"),
        ("2", "Faculty Two", None),
    ]


def test_docx_contains_data():
    from docx import Document
    content, _, _ = render_export("faculty_profiles", COLUMNS, ROWS, "docx")
    document = Document(BytesIO(content))
    text = "\n".join(p.text for p in document.paragraphs)
    cells = [cell.text for table in document.tables for row in table.rows for cell in row.cells]
    assert "faculty_profiles" in text
    assert "Faculty One" in cells
    assert "Research, AI" in cells


def test_pdf_is_readable_and_contains_data():
    import fitz
    content, _, _ = render_export("faculty_profiles", COLUMNS, ROWS, "pdf")
    document = fitz.open(stream=content, filetype="pdf")
    text = "\n".join(page.get_text() for page in document)
    assert "faculty_profiles" in text
    assert "Faculty One" in text


def test_unsupported_format_is_rejected():
    with pytest.raises(ValueError):
        render_export("faculty_profiles", COLUMNS, ROWS, "json")


def test_unapproved_module2_table_is_rejected():
    with pytest.raises(ValueError):
        render_export("m2_test_records", COLUMNS, ROWS, "csv")


def test_sensitive_columns_are_rejected():
    with pytest.raises(ValueError):
        render_export(
            "faculty_profiles",
            ["id", "phone"],
            [(1, "555-0100")],
            "csv",
        )


@pytest.mark.parametrize("fmt", ["csv", "xlsx"])
def test_spreadsheet_exports_escape_formula_values(fmt):
    content, _, _ = render_export(
        "faculty_profiles",
        ["id", "full_name"],
        [(1, "=HYPERLINK(\"https://example.invalid\",\"click\")")],
        fmt,
    )
    if fmt == "csv":
        assert "'=HYPERLINK" in content.decode("utf-8-sig")
        return

    from openpyxl import load_workbook

    sheet = load_workbook(BytesIO(content), read_only=True).active
    assert list(sheet.values)[1][1].startswith("'=HYPERLINK")

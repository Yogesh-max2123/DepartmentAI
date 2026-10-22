from io import BytesIO

import pytest

from module2.data_export.service import render_export


COLUMNS = ["id", "name", "note"]
ROWS = [(1, "Faculty One", "Research, AI"), (2, "Faculty Two", None)]


@pytest.mark.parametrize("fmt,extension,signature", [
    ("csv", "csv", b"\xef\xbb\xbf"),
    ("xlsx", "xlsx", b"PK"),
    ("docx", "docx", b"PK"),
    ("pdf", "pdf", b"%PDF"),
])
def test_export_creates_expected_file(fmt, extension, signature):
    content, mime, actual_extension = render_export("m2_test_records", COLUMNS, ROWS, fmt)
    assert content.startswith(signature)
    assert actual_extension == extension
    assert mime


def test_csv_contains_all_headers_and_rows():
    content, _, _ = render_export("m2_test_records", COLUMNS, ROWS, "csv")
    text = content.decode("utf-8-sig")
    assert "id,name,note" in text
    assert "Faculty One" in text
    assert "Research, AI" in text
    assert "Faculty Two" in text


def test_xlsx_contains_all_rows_and_columns_and_styling():
    from openpyxl import load_workbook
    content, _, _ = render_export("m2_test_records", COLUMNS, ROWS, "xlsx")
    workbook = load_workbook(BytesIO(content), read_only=False)
    sheet = workbook.active
    assert sheet["A1"].value == "DEPARTMENTAI  |  TEST RECORDS"
    assert "2 records" in sheet["A2"].value
    assert [sheet.cell(4, col).value for col in range(1, 4)] == ["Id", "Name", "Note"]
    assert [sheet.cell(5, col).value for col in range(1, 4)] == ["1", "Faculty One", "Research, AI"]
    assert [sheet.cell(6, col).value for col in range(1, 4)] == ["2", "Faculty Two", None]
    assert sheet.freeze_panes == "A5"
    assert sheet["A4"].fill.fgColor.rgb.endswith("245A81")
    assert len(sheet.tables) == 1


def test_docx_contains_data_and_presentation_styling():
    from docx import Document
    content, _, _ = render_export("m2_test_records", COLUMNS, ROWS, "docx")
    document = Document(BytesIO(content))
    text = "\n".join(p.text for p in document.paragraphs)
    cells = [cell.text for table in document.tables for row in table.rows for cell in row.cells]
    assert "Test Records" in text
    assert "2 records" in text
    assert "Faculty One" in cells
    assert "Research, AI" in cells
    assert "Id" in cells


def test_pdf_is_readable_and_contains_data():
    import fitz
    content, _, _ = render_export("m2_test_records", COLUMNS, ROWS, "pdf")
    document = fitz.open(stream=content, filetype="pdf")
    text = "\n".join(page.get_text() for page in document)
    assert "Test Records" in text
    assert "2 records" in text
    assert "Faculty One" in text
    assert "Page 1" in text


def test_unsupported_format_is_rejected():
    with pytest.raises(ValueError):
        render_export("m2_test_records", COLUMNS, ROWS, "json")


def test_non_module2_table_is_rejected():
    with pytest.raises(ValueError):
        render_export("users", COLUMNS, ROWS, "csv")

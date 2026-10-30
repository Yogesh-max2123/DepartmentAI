from datetime import datetime, timezone
from io import BytesIO

import pytest

from module2.reporting import (
    REPORT_MAX_ROWS,
    REPORT_TEMPLATES,
    ReportRequestError,
    ReportSizeLimitError,
    fetch_report_rows,
    list_report_templates,
    render_report,
    report_metadata,
    report_preview_rows,
    validate_report_request,
)


class Description:
    def __init__(self, name):
        self.name = name


class ReportCursor:
    def __init__(self, columns, rows):
        self.description = [Description(name) for name in columns]
        self.rows = rows
        self.calls = []

    def execute(self, query, parameters=None):
        self.calls.append((query, parameters))

    def fetchall(self):
        return self.rows


@pytest.mark.parametrize(
    "template_id,required_column",
    [
        ("faculty_directory", "profile_url"),
        ("publications_summary", "publication_type"),
        ("projects_summary", "funding_agency"),
        ("achievements_summary", "category"),
        ("department_research_overview", "record_category"),
    ],
)
def test_template_catalogue_uses_supported_persisted_sources(
    template_id, required_column
):
    template = REPORT_TEMPLATES[template_id]
    assert required_column in {key for key, _ in template.columns}
    assert "public.m2_" in template.query
    assert "Configurable Draft" in template.title


def test_catalogue_marks_all_templates_as_drafts_and_reports_optional_formats():
    catalogue = list_report_templates()

    assert len(catalogue["templates"]) == 5
    assert all(
        template["status"] == "DRAFT_NOT_OFFICIAL"
        for template in catalogue["templates"]
    )
    assert all("version" in template for template in catalogue["templates"])
    assert all("unavailable_formats" in template for template in catalogue["templates"])
    assert not any(
        "Ministry-approved" in template["title"]
        or "accreditation-approved" in template["title"]
        for template in catalogue["templates"]
    )


def test_template_filter_validation_rejects_unsupported_and_invalid_ranges():
    with pytest.raises(ReportRequestError, match="not available"):
        validate_report_request("patents", None, None)
    with pytest.raises(ReportRequestError, match="does not support"):
        validate_report_request("faculty_directory", 2020, None)
    with pytest.raises(ReportRequestError, match="not be later"):
        validate_report_request("publications_summary", 2025, 2020)

    _, filters = validate_report_request("publications_summary", 2020, 2024)
    assert filters == {"year_from": 2020, "year_to": 2024}


def test_report_query_binds_authenticated_scope_filters_and_row_limit():
    columns = ["record_id", "title"]
    cursor = ReportCursor(columns, [(9, "Synthetic publication")])

    rows = fetch_report_rows(
        cursor,
        "publications_summary",
        ["Synthetic Department"],
        {"year_from": 2020, "year_to": 2025},
    )

    assert rows == [{"record_id": 9, "title": "Synthetic publication"}]
    assert cursor.calls[0] == (
        "SELECT set_config('statement_timeout', %s, true)",
        ("5000ms",),
    )
    query, parameters = cursor.calls[1]
    assert "f.department = ANY(%s)" in query
    assert "COALESCE(p.publication_year" in query
    assert parameters == (["Synthetic Department"], 2020, 2025, REPORT_MAX_ROWS + 1)
    assert "DROP" not in query.upper()


def test_report_query_refuses_unsupported_filter_before_database_query():
    cursor = ReportCursor([], [])

    with pytest.raises(ReportRequestError):
        fetch_report_rows(
            cursor,
            "faculty_directory",
            ["Synthetic Department"],
            {"year_from": 2020},
        )

    assert cursor.calls == []


def test_report_refuses_over_limit_result_instead_of_returning_partial_rows():
    cursor = ReportCursor(
        ["record_id"],
        [(index,) for index in range(REPORT_MAX_ROWS + 1)],
    )

    with pytest.raises(ReportSizeLimitError):
        fetch_report_rows(
            cursor,
            "faculty_directory",
            ["Synthetic Department"],
            {},
        )


def test_preview_metadata_uses_real_scoped_records_and_labels_draft_status():
    metadata = report_metadata(
        "department_research_overview",
        ["Synthetic Department"],
        {},
        [
            {"record_category": "Publications", "count": 3},
            {"record_category": "Projects", "count": 2},
            {"record_category": "Achievements", "count": 1},
        ],
        datetime(2026, 10, 28, tzinfo=timezone.utc),
    )

    assert metadata["summary"] == {
        "record_count": 3,
        "total_persisted_records": 6,
    }
    assert metadata["template_version"] == "1.0"
    assert metadata["status"] == "DRAFT_NOT_OFFICIAL"
    assert metadata["scope"]["departments"] == ["Synthetic Department"]
    assert metadata["generated_at"] == "2026-10-28T00:00:00+00:00"
    assert any("not an approved" in item.lower() for item in metadata["limitations"])


def test_preview_rows_use_fixed_template_columns_and_are_bounded():
    rows = [
        {"record_id": index, "title": f"Paper {index}", "unknown": "not allowed"}
        for index in range(25)
    ]

    preview = report_preview_rows("publications_summary", rows)

    assert len(preview) == 20
    assert preview[0]["record_id"] == "0"
    assert preview[0]["title"] == "Paper 0"
    assert "unknown" not in preview[0]


@pytest.mark.parametrize("file_format,signature", [
    ("docx", b"PK"),
    ("xlsx", b"PK"),
    ("pdf", b"%PDF"),
])
def test_supported_report_formats_include_metadata_and_persisted_row(
    file_format, signature
):
    template_id = "faculty_directory"
    rows = [
        {
            "record_id": 18,
            "full_name": "Synthetic Faculty",
            "designation": "Professor",
            "department": "Synthetic Department",
            "qualification": "Ph.D.",
            "area_of_interest": "Robotics",
            "verification_status": "VERIFIED",
            "profile_url": "https://example.invalid/profile",
            "source_name": "Synthetic source",
            "source_url": "https://example.invalid/source",
        }
    ]
    metadata = report_metadata(
        template_id,
        ["Synthetic Department"],
        {},
        rows,
        datetime(2026, 10, 28, tzinfo=timezone.utc),
    )

    content, mime_type, extension = render_report(
        template_id,
        rows,
        metadata,
        file_format,
    )

    assert content.startswith(signature)
    assert mime_type
    assert extension == file_format
    if file_format == "docx":
        from docx import Document

        document = Document(BytesIO(content))
        paragraph_text = "\n".join(paragraph.text for paragraph in document.paragraphs)
        cell_text = " ".join(
            cell.text for table in document.tables for row in table.rows for cell in row.cells
        )
        assert "DRAFT" in paragraph_text
        assert "Synthetic Faculty" in cell_text
        assert "Synthetic Department" in paragraph_text
    elif file_format == "xlsx":
        from openpyxl import load_workbook

        sheet = load_workbook(BytesIO(content), read_only=True).active
        values = [value for row in sheet.iter_rows(values_only=True) for value in row]
        assert any("DRAFT" in str(value) for value in values if value)
        assert "Synthetic Faculty" in values
        assert "Faculty name" in values
    else:
        import fitz

        document = fitz.open(stream=content, filetype="pdf")
        text = "\n".join(page.get_text() for page in document)
        assert "DRAFT" in text
        assert "Synthetic Faculty" in text
        assert "Synthetic Department" in text


def test_report_spreadsheet_output_escapes_formula_values():
    row = {
        "record_id": 19,
        "full_name": '=HYPERLINK("https://example.invalid","click")',
        "designation": None,
        "department": "Synthetic Department",
        "qualification": None,
        "area_of_interest": None,
        "verification_status": "DRAFT",
        "profile_url": "https://example.invalid/19",
        "source_name": "Synthetic source",
        "source_url": None,
    }
    metadata = report_metadata(
        "faculty_directory",
        ["Synthetic Department"],
        {},
        [row],
    )

    content, _, _ = render_report(
        "faculty_directory",
        [row],
        metadata,
        "xlsx",
    )

    from openpyxl import load_workbook

    sheet = load_workbook(BytesIO(content), read_only=True).active
    values = [value for row_values in sheet.iter_rows(values_only=True) for value in row_values]
    assert any(
        isinstance(value, str) and value.startswith("'=HYPERLINK")
        for value in values
    )


def test_report_renderer_rejects_unsupported_template_or_format():
    with pytest.raises(ReportRequestError):
        render_report(
            "patents",
            [],
            {},
            "pdf",
        )
    metadata = report_metadata("faculty_directory", [], {}, [])
    with pytest.raises(ReportRequestError):
        render_report(
            "faculty_directory",
            [],
            metadata,
            "csv",
        )

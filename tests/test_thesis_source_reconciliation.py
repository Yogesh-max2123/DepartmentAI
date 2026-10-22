import sys
import types
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

# The parser module imports the project DB connection. Tests exercise only
# parsing, so provide a harmless stub rather than requiring a live database.
connection_module = types.ModuleType("module2.database.connection")
connection_module.get_connection = lambda: None
sys.modules.setdefault("module2.database.connection", connection_module)

# Parsing tests do not need profile discovery; use a stub only if the project
# module is unavailable in the test environment.
profile_module = types.ModuleType("module2.ingestion.faculty_profile")
profile_module.discover_profile_components = lambda *args, **kwargs: []
sys.modules.setdefault("module2.ingestion.faculty_profile", profile_module)

from module2.ingestion.faculty_missing_sections import extract_theses, _parse_source_years
from module2.repair_thesis_supervision import (
    normalize_record_text, record_key, is_unknown_level,
    validate_reference_source_counts,
)


HTML = """
<html><body>
<h3>Ph.D. Completed</h3>
<table>
<tr><th>S.No.</th><th>Research Topic</th><th>Name of Student</th><th>Completion/Registration Year</th></tr>
<tr><td>1</td><td>Robust Vision Models</td><td>A Student</td><td>2023</td></tr>
</table>
<h3>Ph.D. Ongoing</h3>
<table>
<tr><th>S.No.</th><th>Research Topic</th><th>Name of Student</th><th>Completion/Registration Year</th></tr>
<tr><td>1</td><td>Graph Learning</td><td>B Student</td><td>September 2020</td></tr>
</table>
<table>
<tr><td colspan="4">M.Tech Students</td></tr>
<tr><th>S.No.</th><th>Research Topic</th><th>Name of Student</th><th>Completion/Registration Year</th></tr>
<tr><td>1</td><td>1. Secure Routing</td><td>C Student</td><td>2018-20</td></tr>
</table>
</body></html>
"""


class ThesisParserTests(unittest.TestCase):
    def test_explicit_headings_set_programme_and_status(self):
        rows = extract_theses(HTML)
        self.assertEqual(len(rows), 3)
        by_student = {row["student_name"]: row for row in rows}

        completed = by_student["A Student"]
        self.assertEqual(completed["program_level"], "Ph.D.")
        self.assertEqual(completed["status"], "Completed")
        self.assertEqual(completed["completion_year"], 2023)

        ongoing = by_student["B Student"]
        self.assertEqual(ongoing["program_level"], "Ph.D.")
        self.assertEqual(ongoing["status"], "Ongoing")
        self.assertEqual(ongoing["registration_year"], 2020)
        self.assertIsNone(ongoing["completion_year"])

        mtech = by_student["C Student"]
        self.assertEqual(mtech["program_level"], "M.Tech")
        self.assertIsNone(mtech["status"])  # not inferred from a cohort range
        self.assertEqual(mtech["registration_year"], 2018)
        self.assertEqual(mtech["completion_year"], 2020)

    def test_table_row_section_heading_is_recognized(self):
        html = """
        <table>
          <tr><td colspan="4">Ph.D. Completed</td></tr>
          <tr><td>S.No.</td><td>Research Topic</td><td>Name of Student</td><td>Year</td></tr>
          <tr><td>1</td><td>AI</td><td>Student X</td><td>2021</td></tr>
        </table>
        """
        row = extract_theses(html)[0]
        self.assertEqual(row["program_level"], "Ph.D.")
        self.assertEqual(row["status"], "Completed")
        self.assertEqual(row["completion_year"], 2021)


    def test_reference_profile_sections_total_112(self):
        pieces = []
        sections = [
            ("Ph.D. Completed", "Ph.D. Completed", 16, "2023"),
            ("Ph.D. Ongoing", "Ph.D. Ongoing", 4, "September 2020"),
            ("M.Tech Students", "M.Tech Students", 92, "2018-20"),
        ]
        for heading, _, count, year in sections:
            pieces.append(f"<h3>{heading}</h3><table>")
            pieces.append(
                "<tr><th>S.No.</th><th>Research Topic</th>"
                "<th>Name of Student</th><th>Completion/Registration Year</th></tr>"
            )
            for index in range(1, count + 1):
                pieces.append(
                    f"<tr><td>{index}</td><td>Topic {heading} {index}</td>"
                    f"<td>Student {heading} {index}</td><td>{year}</td></tr>"
                )
            pieces.append("</table>")
        rows = extract_theses("".join(pieces))
        self.assertEqual(len(rows), 112)
        from collections import Counter
        counts = Counter(row["source_section"] for row in rows)
        self.assertEqual(counts["Ph.D. Completed"], 16)
        self.assertEqual(counts["Ph.D. Ongoing"], 4)
        self.assertEqual(counts["M.Tech Students"], 92)

        groups = [{
            "faculty_id": 4,
            "faculty_name": "Prof. Rama Shankar Yadav",
            "source_url": "https://mnnit.ac.in/profile/previewt.php?id=1687",
            "records": rows,
        }]
        check = validate_reference_source_counts(groups)
        self.assertEqual(len(check), 1)
        self.assertTrue(check[0]["passed"])


    def test_orphan_table_cells_from_official_profile_set_sections(self):
        # The official MNNIT page emits section cells without an enclosing <tr>.
        # Python HTMLParser does not repair that invalid markup automatically.
        html = """
        <table style="table-layout: fixed;" border="1">
          <tr><th>S.No</th><th>Research Topic</th><th>Name of Student</th><th>Completion/Registration Year</th></tr>
          <td colspan="4"><b>Ph.D. Completed:</b></td>
          <tr><td>1</td><td>Completed topic</td><td>Completed student</td><td>2017</td></tr>
          <td colspan="4"><b>Ph.D. Ongoing</b></td>
          <tr><td>1</td><td>Ongoing topic</td><td>Ongoing student</td><td>Sept 2020</td></tr>
          <td colspan="4"><b>M.Tech Students</b></td>
          <tr><td>1</td><td>MTech topic</td><td>MTech student</td><td>2018-20</td></tr>
        </table>
        """
        rows = extract_theses(html)
        self.assertEqual(len(rows), 3)
        by_student = {row["student_name"]: row for row in rows}
        self.assertEqual(by_student["Completed student"]["source_section"], "Ph.D. Completed")
        self.assertEqual(by_student["Completed student"]["program_level"], "Ph.D.")
        self.assertEqual(by_student["Completed student"]["status"], "Completed")
        self.assertEqual(by_student["Ongoing student"]["source_section"], "Ph.D. Ongoing")
        self.assertEqual(by_student["Ongoing student"]["status"], "Ongoing")
        self.assertEqual(by_student["MTech student"]["source_section"], "M.Tech Students")
        self.assertEqual(by_student["MTech student"]["program_level"], "M.Tech")

    def test_year_range_parsing(self):
        self.assertEqual(_parse_source_years("2018-20"), (2018, 2020))
        self.assertEqual(_parse_source_years("2004–2008"), (2004, 2008))
        self.assertEqual(_parse_source_years("Sept 2020"), (2020, 2020))
        self.assertEqual(_parse_source_years("no year"), (None, None))

    def test_record_match_normalization(self):
        self.assertEqual(
            record_key("A. Student", "8. Secure Routing"),
            record_key("A Student", "Secure Routing"),
        )

    def test_unknown_level_is_not_treated_as_phd(self):
        self.assertTrue(is_unknown_level("Not classified from source heading"))
        self.assertFalse(is_unknown_level("Ph.D."))


if __name__ == "__main__":
    unittest.main(verbosity=2)

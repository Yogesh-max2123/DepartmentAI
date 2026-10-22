"""Offline regression tests for the thesis classification parser and query intent."""

import importlib.util
import unittest
from pathlib import Path

from module2.ingestion.repair_thesis_classification import parse_thesis_page, classify_heading
from module2.retrieval.faculty_search import resolve_faculty, normalize_person_name
from module2.retrieval.faculty_assistant import asks_phd_scope, asks_thesis_list


SAMPLE = """
<html><body>
<h2>Thesis Supervised</h2>
<table>
<tr><th>S.No</th><th>Research Topic</th><th>Name of Student</th><th>Completion/Registration Year</th></tr>
<tr><td colspan="4">Ph.D. Ongoing</td></tr>
<tr><td>1</td><td>Video Understanding</td><td>Student A</td><td>2023</td></tr>
<tr><td colspan="4">Ph.D. Completed</td></tr>
<tr><td>1</td><td>Image Classification</td><td>Student B</td><td>2021</td></tr>
<tr><td colspan="4">M.Tech Students</td></tr>
<tr><td>1</td><td>Network Security</td><td>Student C</td><td>2024</td></tr>
</table></body></html>
"""


class ThesisParserTests(unittest.TestCase):
    def test_category_and_year_role(self):
        rows = parse_thesis_page(SAMPLE, "https://example.test/previewt.php?id=1")
        self.assertEqual(len(rows), 3)
        self.assertEqual((rows[0]["program_level"], rows[0]["status"], rows[0]["source_year"]), ("Ph.D.", "Ongoing", 2023))
        self.assertEqual((rows[1]["program_level"], rows[1]["status"], rows[1]["source_year"]), ("Ph.D.", "Completed", 2021))
        self.assertEqual((rows[2]["program_level"], rows[2]["status"]), ("M.Tech", None))

    def test_heading_variants(self):
        self.assertEqual(classify_heading("Ph.D. Ongoing"), ("Ph.D.", "Ongoing"))
        self.assertEqual(classify_heading("Ph.D. Completed"), ("Ph.D.", "Completed"))
        self.assertEqual(classify_heading("M.Tech Students"), ("M.Tech", None))


class FacultyResolutionTests(unittest.TestCase):
    def test_duplicate_database_profile_ids_are_retained_not_lost(self):
        records = [
            {"faculty_name": "Prof MANOJ MADHAVA GORE", "faculty_id": 1},
            {"faculty_name": "Prof MANOJ MADHAVA GORE", "faculty_id": 3},
        ]
        ids, name, status = resolve_faculty("List PhD students supervised by Prof. Manoj Madhava Gore", records)
        self.assertEqual(ids, {1, 3})
        self.assertEqual(status, "matched")
        self.assertEqual(normalize_person_name(name), "manoj madhava gore")

    def test_full_faculty_name_resolves(self):
        records = [{"faculty_name": "Prof. Rama Shankar Yadav", "faculty_id": 4}]
        ids, _, status = resolve_faculty("List PhD students supervised by Prof. Rama Shankar Yadav", records)
        self.assertEqual(ids, {4})
        self.assertEqual(status, "matched")


class QueryIntentTests(unittest.TestCase):
    def test_phd_spellings(self):
        for query in ("PhD students", "Ph.D. students", "doctoral students"):
            self.assertTrue(asks_phd_scope(query), query)

    def test_student_list_intent(self):
        self.assertTrue(asks_thesis_list("Who are the PhD students supervised by Dr. X?"))


if __name__ == "__main__":
    unittest.main()

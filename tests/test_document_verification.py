import json
import unittest
from unittest.mock import patch

from backend.api import workflow_routes


class DocumentVerificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.request_context = patch(
            "backend.api.workflow_routes.retrieve_for_recommendation",
            return_value=[
                {
                    "chunk_text": (
                        "A make-up examination request requires a Medical "
                        "Certificate and Form MP-03."
                    ),
                    "source_file": "M.Tech ordinance",
                }
            ],
        )
        self.source_context = patch(
            "backend.api.workflow_routes.format_sources",
            return_value=[{"source_file": "M.Tech ordinance"}],
        )
        self.request_context.start()
        self.source_context.start()
        self.addCleanup(self.request_context.stop)
        self.addCleanup(self.source_context.stop)

    def make_request(self, *files: workflow_routes.UploadedFile):
        return workflow_routes.AnalyzeDraftRequest(
            category="Examination",
            subject="Make-up Exam",
            description="Request for a make-up examination.",
            uploaded_files=list(files),
        )

    def run_analysis(self, request, response: dict):
        with patch(
            "backend.api.workflow_routes.generate_text",
            return_value=json.dumps(response),
        ):
            return workflow_routes._analyze_draft(request)

    def test_placeholder_file_is_rejected_even_if_model_calls_it_valid(self) -> None:
        request = self.make_request(
            workflow_routes.UploadedFile(
                file_name="dummy.txt",
                content_type="text/plain",
                extracted_text="test",
            )
        )
        result = self.run_analysis(
            request,
            {
                "required_documents": [
                    {"id": "medical", "name": "Medical Certificate"}
                ],
                "file_assessments": [
                    {
                        "file_index": 0,
                        "valid": True,
                        "matched_requirement_ids": ["medical"],
                        "reason_code": "valid",
                    }
                ],
                "deficiencies": [],
            },
        )

        self.assertFalse(result["can_submit"])
        self.assertTrue(
            any(
                "dummy.txt" in item
                and "placeholder" in item
                and "Medical Certificate" in item
                and "Make-up Exam" in item
                for item in result["deficiencies"]
            )
        )

    def test_mismatched_document_is_rejected_and_named(self) -> None:
        request = self.make_request(
            workflow_routes.UploadedFile(
                file_name="medical-certificate.pdf",
                content_type="application/pdf",
                extracted_text="Official Grade Card: Semester 2, CGPA 8.4.",
            )
        )
        result = self.run_analysis(
            request,
            {
                "required_documents": [
                    {"id": "medical", "name": "Medical Certificate"}
                ],
                "file_assessments": [
                    {
                        "file_index": 0,
                        "valid": False,
                        "matched_requirement_ids": [],
                        "reason_code": "mismatched_document",
                    }
                ],
                "deficiencies": [],
            },
        )

        self.assertFalse(result["can_submit"])
        self.assertTrue(
            any(
                "medical-certificate.pdf" in item
                and "does not match the required document type" in item
                for item in result["deficiencies"]
            )
        )

    def test_missing_file_assessment_fails_closed(self) -> None:
        request = self.make_request(
            workflow_routes.UploadedFile(
                file_name="certificate.txt",
                content_type="text/plain",
                extracted_text=(
                    "Medical certificate issued by City Hospital for the student."
                ),
            )
        )
        result = self.run_analysis(
            request,
            {
                "required_documents": [
                    {"id": "medical", "name": "Medical Certificate"}
                ],
                "file_assessments": [],
                "deficiencies": [],
            },
        )

        self.assertFalse(result["can_submit"])
        self.assertTrue(
            any("certificate.txt" in item for item in result["deficiencies"])
        )
        self.assertTrue(
            any("Medical Certificate" in item for item in result["deficiencies"])
        )

    def test_every_mandatory_document_requires_a_valid_file_match(self) -> None:
        request = self.make_request(
            workflow_routes.UploadedFile(
                file_name="medical-certificate.txt",
                content_type="text/plain",
                extracted_text=(
                    "Medical Certificate issued by City Hospital for the student "
                    "on 12 October. Signed by the attending physician."
                ),
            )
        )
        result = self.run_analysis(
            request,
            {
                "required_documents": [
                    {"id": "medical", "name": "Medical Certificate"},
                    {"id": "mp03", "name": "Form MP-03"},
                ],
                "file_assessments": [
                    {
                        "file_index": 0,
                        "valid": True,
                        "matched_requirement_ids": ["medical"],
                        "reason_code": "valid",
                    }
                ],
                "deficiencies": [],
            },
        )

        self.assertFalse(result["can_submit"])
        self.assertTrue(
            any("Form MP-03" in item for item in result["deficiencies"])
        )

    def test_valid_matched_document_can_pass(self) -> None:
        request = self.make_request(
            workflow_routes.UploadedFile(
                file_name="medical-certificate.txt",
                content_type="text/plain",
                extracted_text=(
                    "Medical Certificate issued by City Hospital for the student "
                    "on 12 October. Signed by the attending physician."
                ),
            )
        )
        result = self.run_analysis(
            request,
            {
                "required_documents": [
                    {"id": "medical", "name": "Medical Certificate"}
                ],
                "file_assessments": [
                    {
                        "file_index": 0,
                        "valid": True,
                        "matched_requirement_ids": ["medical"],
                        "reason_code": "valid",
                    }
                ],
                "deficiencies": [],
            },
        )

        self.assertTrue(result["can_submit"])
        self.assertEqual(result["deficiencies"], [])


if __name__ == "__main__":
    unittest.main()

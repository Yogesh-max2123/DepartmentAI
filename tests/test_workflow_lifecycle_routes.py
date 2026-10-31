import unittest
from unittest.mock import patch

from fastapi import HTTPException

from backend.api import workflow_routes as routes


class WorkflowLifecycleRouteTests(unittest.TestCase):
    def test_analysis_and_submission_accept_multiple_uploads(self) -> None:
        uploads = [
            routes.UploadedFile(file_name="medical.pdf", extracted_text="Certificate"),
            routes.UploadedFile(file_name="form.txt", extracted_text="Form MP-03"),
        ]
        request = routes.AnalyzeDraftRequest(
            category="Examination",
            subject="Make-up Exam",
            description="Application description.",
            uploaded_files=uploads,
        )
        analyzed = {
            "can_submit": True,
            "deficiencies": [],
            "sources": [],
            "uploaded_files": [
                {"file_name": "medical.pdf"},
                {"file_name": "form.txt"},
            ],
        }
        with patch.object(routes, "_analyze_draft", return_value=analyzed) as analyze:
            response = routes.student_analyze_draft(
                request,
                {"username": "MTECH20233359", "role": "student"},
            )
        self.assertTrue(response["can_submit"])
        self.assertEqual(len(analyze.call_args.args[0].uploaded_files), 2)

        with (
            patch.object(routes, "_analyze_draft", return_value=analyzed),
            patch.object(
                routes.db, "create_application", return_value={"id": 41}
            ) as create,
        ):
            result = routes.student_submit(
                request,
                {"username": "MTECH20233359", "role": "student"},
            )
        self.assertTrue(result["ok"])
        self.assertEqual(len(create.call_args.args[0]["uploaded_files"]), 2)

    def test_resubmit_checks_ownership_and_appends_verified_files(self) -> None:
        application = {
            "id": 41,
            "student_reg_no": "MTECH20233359",
            "student_name": "Test Student",
            "category": "Examination",
            "subject": "Make-up Exam",
            "description": "Application description.",
            "status": "DEFICIENCY_FOUND",
        }
        request = routes.StudentResubmitRequest(
            uploaded_files=[
                routes.UploadedFile(
                    file_name="medical.pdf",
                    extracted_text="Medical certificate",
                ),
                routes.UploadedFile(
                    file_name="form.txt",
                    extracted_text="Completed Form MP-03",
                ),
            ],
            student_remarks="Added the requested documents.",
        )
        analyzed = {
            "can_submit": True,
            "deficiencies": [],
            "sources": [{"source_file": "ordinance.pdf"}],
            "uploaded_files": [
                {"file_name": "medical.pdf"},
                {"file_name": "form.txt"},
            ],
        }
        with (
            patch.object(routes, "_get_application_or_404", return_value=application),
            patch.object(routes, "_analyze_draft", return_value=analyzed) as analyze,
            patch.object(
                routes.db, "resubmit_application", return_value={"id": 41}
            ) as save,
        ):
            result = routes.student_resubmit(
                41,
                request,
                {"username": "MTECH20233359", "role": "student"},
            )

        self.assertTrue(result["ok"])
        self.assertEqual(len(analyze.call_args.args[0].uploaded_files), 2)
        self.assertEqual(save.call_args.args[0:2], (41, "MTECH20233359"))
        self.assertEqual(save.call_args.args[2], analyzed["uploaded_files"])
        self.assertEqual(save.call_args.args[3], "Added the requested documents.")

    def test_resubmit_requires_own_deficient_application(self) -> None:
        application = {
            "id": 41,
            "student_reg_no": "OTHER",
            "status": "DEFICIENCY_FOUND",
        }
        request = routes.StudentResubmitRequest(
            uploaded_files=[routes.UploadedFile(file_name="new.txt", extracted_text="file")]
        )
        with (
            patch.object(routes, "_get_application_or_404", return_value=application),
            patch.object(routes, "_analyze_draft") as analyze,
        ):
            with self.assertRaises(HTTPException) as raised:
                routes.student_resubmit(
                    41,
                    request,
                    {"username": "MTECH20233359", "role": "student"},
                )
        self.assertEqual(raised.exception.status_code, 403)
        analyze.assert_not_called()

    def test_resubmit_blocks_when_document_gate_fails(self) -> None:
        application = {
            "id": 41,
            "student_reg_no": "MTECH20233359",
            "category": "Examination",
            "subject": "Make-up Exam",
            "description": "Application description.",
            "status": "DEFICIENCY_FOUND",
        }
        request = routes.StudentResubmitRequest(
            uploaded_files=[routes.UploadedFile(file_name="test.txt", extracted_text="test")]
        )
        with (
            patch.object(routes, "_get_application_or_404", return_value=application),
            patch.object(
                routes,
                "_analyze_draft",
                return_value={
                    "can_submit": False,
                    "deficiencies": ["Invalid file."],
                    "sources": [],
                },
            ),
            patch.object(routes.db, "resubmit_application") as save,
        ):
            with self.assertRaises(HTTPException) as raised:
                routes.student_resubmit(
                    41,
                    request,
                    {"username": "MTECH20233359", "role": "student"},
                )
        self.assertEqual(raised.exception.status_code, 422)
        save.assert_not_called()

    def test_official_can_return_application_with_required_remarks(self) -> None:
        application = {
            "id": 41,
            "status": "CLAIMED_BY_OFFICIAL",
            "claimed_by": "OFFICIAL01",
        }
        request = routes.OfficialDecisionRequest(
            decision="send_back_deficiency",
            official_remarks="Attach a signed Medical Certificate.",
        )
        with (
            patch.object(routes, "_get_application_or_404", return_value=application),
            patch.object(
                routes.db,
                "send_application_back_for_deficiency",
                return_value={"id": 41, "status": "DEFICIENCY_FOUND"},
            ) as send_back,
        ):
            result = routes.official_decision(
                41, request, {"username": "OFFICIAL01", "role": "official"}
            )
        self.assertEqual(result["application"]["status"], "DEFICIENCY_FOUND")
        self.assertEqual(send_back.call_args.args[2], request.official_remarks)

    def test_official_can_mark_application_under_review(self) -> None:
        application = {
            "id": 41,
            "status": "CLAIMED_BY_OFFICIAL",
            "claimed_by": "OFFICIAL01",
        }
        request = routes.OfficialDecisionRequest(
            decision="mark_under_review",
            official_remarks="Reviewing the supporting evidence.",
        )
        with (
            patch.object(routes, "_get_application_or_404", return_value=application),
            patch.object(
                routes.db,
                "mark_application_under_review",
                return_value={"id": 41, "status": "UNDER_REVIEW"},
            ) as mark_review,
        ):
            result = routes.official_decision(
                41, request, {"username": "OFFICIAL01", "role": "official"}
            )
        self.assertEqual(result["application"]["status"], "UNDER_REVIEW")
        self.assertEqual(mark_review.call_args.args[2], request.official_remarks)

    def test_official_cannot_return_for_deficiency_without_remarks(self) -> None:
        application = {
            "id": 41,
            "status": "CLAIMED_BY_OFFICIAL",
            "claimed_by": "OFFICIAL01",
        }
        request = routes.OfficialDecisionRequest(
            decision="send_back_deficiency",
            official_remarks="  ",
        )
        with (
            patch.object(routes, "_get_application_or_404", return_value=application),
            patch.object(routes.db, "send_application_back_for_deficiency") as send_back,
        ):
            with self.assertRaises(HTTPException) as raised:
                routes.official_decision(
                    41, request, {"username": "OFFICIAL01", "role": "official"}
                )
        self.assertEqual(raised.exception.status_code, 422)
        send_back.assert_not_called()

    def test_dmpc_can_request_reschedule_with_remark(self) -> None:
        application = {
            "id": 41,
            "status": "MEETING_PROPOSED",
        }
        request = routes.MeetingApprovalRequest(
            action="request_reschedule",
            hod_comment="Please propose a date after the examination period.",
        )
        with (
            patch.object(routes, "_get_application_or_404", return_value=application),
            patch.object(
                routes.db,
                "request_meeting_reschedule",
                return_value={"id": 41, "status": "RESCHEDULE_REQUESTED"},
            ) as reschedule,
            patch.object(routes.scheduling_agent, "approve_meeting") as approve,
        ):
            result = routes.dmpc_approve_meeting(
                41, request, {"username": "DMPC01", "role": "dmpc"}
            )
        self.assertEqual(
            result["application"]["status"],
            "RESCHEDULE_REQUESTED",
        )
        self.assertEqual(reschedule.call_args.args[2], request.hod_comment)
        approve.assert_not_called()

    def test_dmpc_cannot_request_reschedule_without_remark(self) -> None:
        application = {"id": 41, "status": "MEETING_PROPOSED"}
        request = routes.MeetingApprovalRequest(
            action="request_reschedule",
            hod_comment="  ",
        )
        with (
            patch.object(routes, "_get_application_or_404", return_value=application),
            patch.object(routes.db, "request_meeting_reschedule") as reschedule,
        ):
            with self.assertRaises(HTTPException) as raised:
                routes.dmpc_approve_meeting(
                    41, request, {"username": "DMPC01", "role": "dmpc"}
                )
        self.assertEqual(raised.exception.status_code, 422)
        reschedule.assert_not_called()


if __name__ == "__main__":
    unittest.main()

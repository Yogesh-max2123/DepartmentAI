from pathlib import Path

import fitz
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.api import auth_routes, routes
from backend.main import app
from backend.services import document_classifier
from backend.services.auth_service import AuthenticatedUser


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection
        self.result = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, parameters):
        normalized_query = " ".join(query.split()).lower()
        if normalized_query.startswith("select id, application_id"):
            document_id = parameters[0]
            requested_application_id = parameters[1] if len(parameters) == 2 else None
            if document_id == self.connection.document_id and (
                requested_application_id is None
                or requested_application_id == self.connection.document[1]
            ):
                self.result = self.connection.document
            else:
                self.result = None
        elif normalized_query.startswith("update application_documents"):
            self.connection.updated_document_type = parameters[0]
        else:
            raise AssertionError(f"Unexpected SQL: {normalized_query}")

    def fetchone(self):
        return self.result


class FakeConnection:
    def __init__(self, document_id, document):
        self.document_id = document_id
        self.document = document
        self.updated_document_type = None
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def make_pdf(path: Path, text: str) -> None:
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 72), text)
    pdf.save(path)
    pdf.close()


def make_connection(path: Path, file_name: str, mime_type: str):
    document = (7, 12, file_name, str(path), path.stat().st_size, mime_type)
    connection = FakeConnection(7, document)
    return connection


def test_classifies_pdf_from_content_and_not_upload_label(tmp_path, monkeypatch):
    path = tmp_path / "marks.pdf"
    make_pdf(path, "UNIVERSITY MARKSHEET\nSemester Grade Report\nCGPA: 8.5")
    connection = make_connection(path, "marks.pdf", "application/pdf")
    monkeypatch.setattr(document_classifier, "get_connection", lambda: connection)

    result = document_classifier.classify_document(7, 12)

    assert result["document_type"] == "MARKSHEET"
    assert result["classification_status"] == "CLASSIFIED"
    assert result["matched_categories"] == ["MARKSHEET"]
    assert result["valid"] is True
    assert connection.updated_document_type == "MARKSHEET"
    assert connection.committed is True
    assert connection.closed is True


def test_ambiguous_pdf_is_flagged_for_review(tmp_path, monkeypatch):
    path = tmp_path / "mixed.pdf"
    make_pdf(path, "Application Form\nCertificate of completion")
    connection = make_connection(path, "mixed.pdf", "application/pdf")
    monkeypatch.setattr(document_classifier, "get_connection", lambda: connection)

    result = document_classifier.classify_document(7, 12)

    assert result["document_type"] == "OTHER"
    assert result["classification_status"] == "NEEDS_REVIEW"
    assert set(result["matched_categories"]) == {
        "APPLICATION_FORM",
        "CERTIFICATE",
    }


def test_valid_image_is_not_misclassified_without_ocr(tmp_path, monkeypatch):
    path = tmp_path / "proof.png"
    Image.new("RGB", (40, 40), color="white").save(path)
    connection = make_connection(path, "proof.png", "image/png")
    monkeypatch.setattr(document_classifier, "get_connection", lambda: connection)

    result = document_classifier.classify_document(7, 12)

    assert result["valid"] is True
    assert result["document_type"] == "OTHER"
    assert result["classification_status"] == "NEEDS_REVIEW"
    assert result["classification_method"] == "image_requires_ocr"


@pytest.mark.parametrize(
    ("file_name", "mime_type", "content", "error"),
    [
        ("invalid.pdf", "application/pdf", b"not a PDF", "not a valid PDF"),
        ("invalid.png", "image/png", b"not an image", "Image file is corrupt"),
        ("invalid.exe", "application/octet-stream", b"content", "Unsupported document"),
    ],
)
def test_rejects_invalid_files_without_updating_document_type(
    tmp_path,
    monkeypatch,
    file_name,
    mime_type,
    content,
    error,
):
    path = tmp_path / file_name
    path.write_bytes(content)
    connection = make_connection(path, file_name, mime_type)
    monkeypatch.setattr(document_classifier, "get_connection", lambda: connection)

    with pytest.raises(ValueError, match=error):
        document_classifier.classify_document(7, 12)

    assert connection.updated_document_type is None
    assert connection.committed is False
    assert connection.rolled_back is True
    assert connection.closed is True


def test_application_scoped_lookup_does_not_classify_another_app_document(
    tmp_path,
    monkeypatch,
):
    path = tmp_path / "marks.pdf"
    make_pdf(path, "MARKSHEET")
    connection = make_connection(path, "marks.pdf", "application/pdf")
    monkeypatch.setattr(document_classifier, "get_connection", lambda: connection)

    with pytest.raises(document_classifier.DocumentNotFoundError):
        document_classifier.classify_document(7, 99)

    assert connection.updated_document_type is None
    assert connection.committed is False


def test_classification_endpoint_returns_result_and_scopes_document(
    tmp_path,
    monkeypatch,
):
    path = tmp_path / "identity.pdf"
    make_pdf(path, "Passport Identity Proof")
    connection = make_connection(path, "identity.pdf", "application/pdf")
    monkeypatch.setattr(document_classifier, "get_connection", lambda: connection)
    monkeypatch.setattr(routes, "require_application_access", lambda *_args: None)
    app.dependency_overrides[auth_routes.get_current_user] = lambda: AuthenticatedUser(
        id=1,
        username="synthetic-student",
        role="STUDENT",
        subject_identifier="SYNTHETIC",
    )
    try:
        with TestClient(app) as client:
            response = client.post("/applications/12/documents/7/classify")
            assert response.status_code == 200
            assert response.json()["document_type"] == "IDENTITY_PROOF"

            other_application_response = client.post(
                "/applications/99/documents/7/classify"
            )
            assert other_application_response.status_code == 404
    finally:
        app.dependency_overrides.clear()

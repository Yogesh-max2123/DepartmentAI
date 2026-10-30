import fitz
import pytest

from backend.services import document_extractor


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection
        self.inserted_extraction = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, _parameters):
        self.inserted_extraction = "INSERT INTO document_extractions" in query

    def fetchone(self):
        if self.inserted_extraction:
            return (12,)
        if not self.connection.document_found:
            return None
        return (
            3,
            str(self.connection.file_path),
            self.connection.mime_type,
        )


class FakeConnection:
    def __init__(self, file_path, mime_type, document_found=True):
        self.file_path = file_path
        self.mime_type = mime_type
        self.document_found = document_found

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


def test_extract_pdf_text_when_generic_mime_type_is_stored(tmp_path, monkeypatch):
    file_path = tmp_path / "synthetic.pdf"
    with fitz.open() as pdf:
        page = pdf.new_page()
        page.insert_text((72, 72), "Synthetic fixture")
        pdf.save(file_path)

    monkeypatch.setattr(
        document_extractor,
        "get_connection",
        lambda: FakeConnection(file_path, "application/octet-stream"),
    )

    result = document_extractor.extract_document_text(3, 5)

    assert result["extraction_id"] == 12
    assert result["document_id"] == 3
    assert result["extraction_status"] == "COMPLETED"
    assert "Synthetic fixture" in result["extracted_text"]


def test_extraction_rejects_documents_outside_the_application_scope(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        document_extractor,
        "get_connection",
        lambda: FakeConnection(tmp_path / "unused.pdf", "application/pdf", False),
    )

    with pytest.raises(document_extractor.DocumentExtractionNotFoundError):
        document_extractor.extract_document_text(3, 5)


def test_extraction_rejects_pdf_over_size_limit(tmp_path, monkeypatch):
    file_path = tmp_path / "oversized.pdf"
    file_path.write_bytes(b"x" * (document_extractor.MAX_DOCUMENT_SIZE_BYTES + 1))
    monkeypatch.setattr(
        document_extractor,
        "get_connection",
        lambda: FakeConnection(file_path, "application/pdf"),
    )

    with pytest.raises(ValueError, match="10 MiB"):
        document_extractor.extract_document_text(3, 5)


def test_extraction_rejects_pdf_over_page_limit(tmp_path, monkeypatch):
    file_path = tmp_path / "too-many-pages.pdf"
    with fitz.open() as pdf:
        pdf.new_page()
        pdf.save(file_path)
    monkeypatch.setattr(document_extractor, "MAX_PDF_PAGES", 0)
    monkeypatch.setattr(
        document_extractor,
        "get_connection",
        lambda: FakeConnection(file_path, "application/pdf"),
    )

    with pytest.raises(ValueError, match="0-page"):
        document_extractor.extract_document_text(3, 5)


def test_extraction_rejects_excessive_text_length(tmp_path, monkeypatch):
    file_path = tmp_path / "too-much-text.pdf"
    with fitz.open() as pdf:
        page = pdf.new_page()
        page.insert_text((72, 72), "Synthetic text exceeds the test limit.")
        pdf.save(file_path)
    monkeypatch.setattr(document_extractor, "MAX_EXTRACTED_TEXT_CHARS", 1)
    monkeypatch.setattr(
        document_extractor,
        "get_connection",
        lambda: FakeConnection(file_path, "application/pdf"),
    )

    with pytest.raises(ValueError, match="1-character"):
        document_extractor.extract_document_text(3, 5)

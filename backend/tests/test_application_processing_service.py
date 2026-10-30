from backend.services import application_processing_service as processing


class FakeCursor:
    def __init__(self, rows=None):
        self.rows = rows if rows is not None else [
            (1,),
            (2,),
            (3,),
        ]

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, _query, _parameters):
        pass

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, rows=None):
        self.rows = rows

    def cursor(self):
        return FakeCursor(self.rows)

    def close(self):
        pass


def test_process_application_documents_runs_validation_classification_and_pdf_text(
    monkeypatch,
):
    validated = []
    classified = []
    extracted = []
    monkeypatch.setattr(processing, "get_connection", FakeConnection)
    monkeypatch.setattr(
        processing,
        "validate_document",
        lambda document_id: (
            validated.append(document_id)
            or {
                "valid": True,
                "reason": "Document passed validation.",
            }
        ),
    )
    monkeypatch.setattr(
        processing,
        "classify_document",
        lambda document_id, application_id: (
            classified.append((document_id, application_id))
            or {
                "classification_status": "CLASSIFIED"
                if document_id == 1
                else "NEEDS_REVIEW",
                "document_type": "MARKSHEET" if document_id == 1 else "OTHER",
                "classification_method": (
                    "image_requires_ocr"
                    if document_id == 2
                    else "pdf_text"
                ),
                "reason": "Synthetic classification result.",
            }
        ),
    )
    monkeypatch.setattr(
        processing,
        "extract_document_text",
        lambda document_id, _application_id: (
            extracted.append(document_id)
            or {
                "extraction_status": "COMPLETED",
                "text_length": 24,
            }
        ),
    )

    result = processing.process_application_documents(55)

    assert validated == [1, 2, 3]
    assert classified == [(1, 55), (2, 55), (3, 55)]
    assert extracted == [1, 3]
    assert result["documents_processed"] == 3
    assert result["documents"][0]["extraction_status"] == "COMPLETED"
    assert result["documents"][1]["extraction_status"] == "NOT_SUPPORTED"
    assert result["documents"][1]["classification_status"] == "NEEDS_REVIEW"
    assert result["documents"][2]["extraction_status"] == "COMPLETED"


def test_invalid_document_is_reported_without_classifying_or_extracting(
    monkeypatch,
):
    def fail_if_called(*_args):
        raise AssertionError("Invalid documents must not be processed further.")

    monkeypatch.setattr(
        processing,
        "get_connection",
        lambda: FakeConnection([(3,)]),
    )
    monkeypatch.setattr(
        processing,
        "validate_document",
        lambda _document_id: {
            "valid": False,
            "reason": "Synthetic invalid PDF.",
        },
    )
    monkeypatch.setattr(
        processing,
        "classify_document",
        fail_if_called,
    )
    monkeypatch.setattr(
        processing,
        "extract_document_text",
        fail_if_called,
    )

    result = processing.process_application_documents(55)

    assert result["documents_processed"] == 1
    assert result["documents"] == [
        {
            "document_id": 3,
            "valid": False,
            "classification_status": "NOT_RUN",
            "extraction_status": "NOT_RUN",
            "reason": "Synthetic invalid PDF.",
        }
    ]


def test_process_application_fails_closed_before_legacy_pipeline(monkeypatch):
    monkeypatch.setattr(
        processing,
        "get_application",
        lambda application_id: {"id": application_id},
    )
    monkeypatch.setattr(
        processing,
        "_load_current_snapshot",
        lambda *_args, **_kwargs: {
            "application_type": "Free text request",
            "programme_identity": {
                "status": "NOT_CONFIGURED",
                "programme": None,
            },
            "policy_registry": {"status": "UNCONFIGURED"},
        },
    )

    try:
        processing.process_application(55)
    except processing.ApplicationProcessingUnavailable as error:
        assert error.code == "PROGRAMME_IDENTITY_NOT_CONFIGURED"
        assert "No legacy default-programme retrieval" in error.message
    else:
        raise AssertionError("Unverified programme identity must block processing.")

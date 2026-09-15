from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

from backend.rag.qa_pipeline import answer_question
from backend.rag.source_formatter import format_sources
from backend.services.application_service import create_application
from backend.services.document_service import upload_document
from backend.services.document_validator import validate_document
from backend.services.document_extractor import extract_document_text
from backend.services.document_classifier import classify_document
from backend.services.application_retrieval import retrieve_ordinance_for_application

router = APIRouter()


# ============================================================
# Ordinance Assistant
# ============================================================

class AskRequest(BaseModel):
    question: str
    conversation_history: list[dict] = []


class AskResponse(BaseModel):
    answer: str
    sources: list


@router.post("/ask", response_model=AskResponse)
def ask_question(request: AskRequest):
    try:
        answer, results = answer_question(
            request.question,
            request.conversation_history
        )

        return {
            "answer": answer,
            "sources": format_sources(results)
        }

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ============================================================
# Application Processing
# ============================================================

class ApplicationCreateRequest(BaseModel):
    applicant_identifier: str
    application_type: str
    title: str | None = None
    description: str | None = None


class ApplicationCreateResponse(BaseModel):
    id: int
    application_number: str
    status: str
    created_at: object


@router.post(
    "/applications",
    response_model=ApplicationCreateResponse
)
def create_new_application(request: ApplicationCreateRequest):
    try:
        application = create_application(
            applicant_identifier=request.applicant_identifier,
            application_type=request.application_type,
            title=request.title,
            description=request.description,
        )

        return application

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ============================================================
# Application Document Management
# ============================================================

class DocumentUploadResponse(BaseModel):
    id: int
    application_id: int
    file_name: str
    document_type: str | None
    file_path: str
    file_size: int
    mime_type: str | None
    upload_status: str
    uploaded_at: object


@router.post(
    "/applications/{application_id}/documents",
    response_model=DocumentUploadResponse
)
async def upload_application_document(
    application_id: int,
    file: UploadFile = File(...),
    document_type: str | None = Form(None),
):
    try:
        file_content = await file.read()

        if not file_content:
            raise HTTPException(
                status_code=400,
                detail="Uploaded file is empty."
            )

        document = upload_document(
            application_id=application_id,
            file_name=file.filename,
            file_content=file_content,
            document_type=document_type,
            mime_type=file.content_type,
        )

        return document

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
        
# ============================================================
# Document Validation
# ============================================================

@router.get(
    "/applications/{application_id}/documents/{document_id}/validate"
)
def validate_application_document(
    application_id: int,
    document_id: int,
):
    try:
        result = validate_document(document_id)

        # Make sure the document belongs to the requested application
        if result.get("valid") and result.get("application_id") != application_id:
            raise HTTPException(
                status_code=404,
                detail="Document does not belong to this application."
            )

        if not result.get("valid"):
            raise HTTPException(
                status_code=400,
                detail=result.get("reason")
            )

        return result

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

# ============================================================
# Document Text Extraction
# ============================================================

@router.post(
    "/applications/{application_id}/documents/{document_id}/extract"
)
def extract_application_document(
    application_id: int,
    document_id: int,
):
    try:
        result = extract_document_text(document_id)

        # Make sure the document belongs to the requested application
        if result.get("document_id") != document_id:
            raise HTTPException(
                status_code=404,
                detail="Document not found."
            )

        # Verify application ownership
        from backend.database.connection import get_connection

        conn = get_connection()

        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT application_id
                    FROM application_documents
                    WHERE id = %s;
                    """,
                    (document_id,),
                )

                document = cursor.fetchone()

        finally:
            conn.close()

        if document is None or document[0] != application_id:
            raise HTTPException(
                status_code=404,
                detail="Document does not belong to this application."
            )

        return result

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
# ============================================================
# Document Classification
# ============================================================

@router.post(
    "/applications/{application_id}/documents/{document_id}/classify"
)
def classify_application_document(
    application_id: int,
    document_id: int,
):
    try:
        result = classify_document(document_id)

        if result.get("application_id") != application_id:
            raise HTTPException(
                status_code=404,
                detail="Document does not belong to this application."
            )

        return result

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
        
        
# ============================================================
# Application Ordinance Retrieval
# ============================================================

@router.get(
    "/applications/{application_id}/ordinance-retrieval"
)
def retrieve_application_ordinance(
    application_id: int,
):
    try:
        return retrieve_ordinance_for_application(
            application_id
        )

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
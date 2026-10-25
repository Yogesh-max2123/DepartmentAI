from typing import Annotated, Literal

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend.api.access import require_application_access, require_role
from backend.api.auth_routes import get_current_user
from backend.services.auth_service import (
    AuthenticatedUser,
    get_review_access,
    is_committee_member,
    list_applications_for_user,
)
from backend.rag.qa_pipeline import answer_question
from backend.rag.source_formatter import format_sources

from backend.services.application_service import (
    ALLOWED_TRANSITIONS,
    create_application,
    submit_application,
    update_application_status,
    get_application,
    get_application_status_history,
)

from backend.services.document_service import (
    get_document_download,
    upload_document,
    get_application_documents,
)

from backend.services.document_validator import validate_document
from backend.services.document_extractor import extract_document_text
from backend.services.document_classifier import classify_document
from backend.services.application_retrieval import (
    retrieve_ordinance_for_application,
)
from backend.services.eligibility_engine import (
    analyze_application_eligibility,
)
from backend.services.deficiency_detector import (
    detect_application_deficiencies,
)

from backend.services.committee_service import (
    assign_to_committee,
    record_committee_decision,
    get_committee_reviews,
)

from backend.services.ai_analysis_service import (
    generate_application_analysis,
)
from backend.services.application_processing_service import (
    process_application,
)
from backend.services.official_assignment_service import (
    claim_application,
    list_unassigned_submissions,
)

router = APIRouter(dependencies=[Depends(get_current_user)])
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]
MAX_DOCUMENT_SIZE_BYTES = 10 * 1024 * 1024


# ============================================================
# Ordinance Assistant
# ============================================================

class AskRequest(BaseModel):
    question: str
    conversation_history: list[dict] = []


class AskResponse(BaseModel):
    answer: str
    sources: list


# ============================================================
# Committee Requests
# ============================================================

class CommitteeAssignmentRequest(BaseModel):
    committee_type: Literal["DUGC", "DMPC", "DDPC"]


class CommitteeDecisionRequest(BaseModel):
    decision: str = Field(min_length=1, max_length=32)
    decision_reason: str = Field(min_length=1, max_length=2000)


# ============================================================
# Ask / RAG
# ============================================================

@router.post("/ask", response_model=AskResponse)
def ask_question(request: AskRequest):
    try:
        answer, results = answer_question(
            request.question,
            request.conversation_history,
        )

        return {
            "answer": answer,
            "sources": format_sources(results),
        }

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


# ============================================================
# Application Processing
# ============================================================

class ApplicationCreateRequest(BaseModel):
    application_type: str = Field(min_length=1, max_length=100)
    title: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=10000)


class ApplicationCreateResponse(BaseModel):
    id: int
    application_number: str
    status: str
    created_at: object


@router.get("/applications")
def list_user_applications(
    user: CurrentUser,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return {
        "items": list_applications_for_user(user, limit=limit, offset=offset),
        "limit": limit,
        "offset": offset,
    }


@router.get("/official/applications/unassigned")
def list_unassigned_official_applications(
    user: CurrentUser,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    require_role(user, "OFFICIAL")
    return {
        "items": list_unassigned_submissions(limit, offset),
        "limit": limit,
        "offset": offset,
    }


@router.post("/applications/{application_id}/submit")
def submit_student_application(application_id: int, user: CurrentUser):
    require_application_access(user, application_id, "STUDENT")
    try:
        return submit_application(application_id, submitted_by=user.username)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/applications/{application_id}/claim")
def claim_official_application(application_id: int, user: CurrentUser):
    require_role(user, "OFFICIAL")
    try:
        return claim_application(application_id, user)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post(
    "/applications",
    response_model=ApplicationCreateResponse,
)
def create_new_application(request: ApplicationCreateRequest, user: CurrentUser):
    try:
        require_role(user, "STUDENT")
        application = create_application(
            applicant_identifier=user.subject_identifier,
            application_type=request.application_type,
            title=request.title,
            description=request.description,
        )

        return application

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


# ============================================================
# Get Application
# ============================================================

@router.get("/applications/{application_id}")
def get_application_endpoint(application_id: int, user: CurrentUser):
    try:
        require_application_access(user, application_id)
        application = get_application(application_id)

        if application is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Application with id {application_id} "
                    f"does not exist."
                ),
            )

        if user.role == "OFFICIAL":
            application["allowed_transitions"] = sorted(
                ALLOWED_TRANSITIONS.get(application["status"], set())
            )
        return application

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


# ============================================================
# Application Document Management
# ============================================================

class DocumentUploadResponse(BaseModel):
    id: int
    application_id: int
    file_name: str
    document_type: str | None
    file_size: int
    mime_type: str | None
    upload_status: str
    uploaded_at: object


@router.post(
    "/applications/{application_id}/documents",
    response_model=DocumentUploadResponse,
)
async def upload_application_document(
    application_id: int,
    user: CurrentUser,
    file: UploadFile = File(...),
    document_type: str | None = Form(None),
):
    try:
        require_application_access(user, application_id, "STUDENT")
        if not file.filename or not file.filename.strip():
            raise HTTPException(
                status_code=400,
                detail="A document file name is required.",
            )
        file_content = await file.read(MAX_DOCUMENT_SIZE_BYTES + 1)

        if not file_content:
            raise HTTPException(
                status_code=400,
                detail="Uploaded file is empty.",
            )
        if len(file_content) > MAX_DOCUMENT_SIZE_BYTES:
            raise HTTPException(
                status_code=413,
                detail="Uploaded document exceeds the 10 MB limit.",
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
            detail=str(e),
        )

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


@router.get(
    "/applications/{application_id}/documents"
)
def get_documents_for_application(application_id: int, user: CurrentUser):
    try:
        require_application_access(user, application_id)
        application = get_application(application_id)

        if application is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Application with id {application_id} "
                    f"does not exist."
                ),
            )

        return {
            "application_id": application_id,
            "documents": get_application_documents(
                application_id
            ),
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


@router.get(
    "/applications/{application_id}/documents/{document_id}/download"
)
def download_application_document(
    application_id: int,
    document_id: int,
    user: CurrentUser,
):
    require_application_access(user, application_id)
    try:
        document = get_document_download(application_id, document_id)
    except FileNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail="Document content is unavailable.",
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=500,
            detail="Stored document path is invalid.",
        ) from error
    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )
    return FileResponse(
        document["file_path"],
        filename=document["file_name"],
        media_type="application/octet-stream",
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
    user: CurrentUser,
):
    try:
        require_application_access(user, application_id, "STUDENT")
        result = validate_document(document_id)

        # Make sure the document belongs to the requested application
        if (
            result.get("valid")
            and result.get("application_id") != application_id
        ):
            raise HTTPException(
                status_code=404,
                detail="Document does not belong to this application.",
            )

        if not result.get("valid"):
            raise HTTPException(
                status_code=400,
                detail=result.get("reason"),
            )

        return result

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
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
    user: CurrentUser,
):
    try:
        require_application_access(user, application_id, "STUDENT")
        result = extract_document_text(document_id)

        # Make sure the returned document ID matches
        if result.get("document_id") != document_id:
            raise HTTPException(
                status_code=404,
                detail="Document not found.",
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

        if document is None:
            raise HTTPException(
                status_code=404,
                detail="Document not found.",
            )

        if document[0] != application_id:
            raise HTTPException(
                status_code=404,
                detail="Document does not belong to this application.",
            )

        return result

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
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
    user: CurrentUser,
):
    try:
        require_application_access(user, application_id, "STUDENT")
        result = classify_document(document_id)

        if result.get("application_id") != application_id:
            raise HTTPException(
                status_code=404,
                detail="Document does not belong to this application.",
            )

        return result

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


# ============================================================
# Application Ordinance Retrieval
# ============================================================

@router.get(
    "/applications/{application_id}/ordinance-retrieval"
)
def retrieve_application_ordinance(
    application_id: int,
    user: CurrentUser,
):
    try:
        require_application_access(user, application_id)
        return retrieve_ordinance_for_application(
            application_id
        )

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


# ============================================================
# Eligibility Analysis
# ============================================================

@router.get(
    "/applications/{application_id}/eligibility"
)
def analyze_application(application_id: int, user: CurrentUser):
    try:
        require_application_access(user, application_id, "STUDENT")
        return analyze_application_eligibility(
            application_id
        )

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


# ============================================================
# Deficiency Detection
# ============================================================

@router.get(
    "/applications/{application_id}/deficiencies"
)
def detect_deficiencies(application_id: int, user: CurrentUser):
    try:
        require_application_access(user, application_id, "STUDENT")
        return detect_application_deficiencies(
            application_id
        )

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


# ============================================================
# Application Status
# ============================================================

class ApplicationStatusUpdateRequest(BaseModel):
    new_status: str
    reason: str | None = None


@router.patch(
    "/applications/{application_id}/status"
)
def update_status(
    application_id: int,
    request: ApplicationStatusUpdateRequest,
    user: CurrentUser,
):
    try:
        require_application_access(user, application_id, "OFFICIAL")
        return update_application_status(
            application_id=application_id,
            new_status=request.new_status,
            changed_by=user.username,
            reason=request.reason,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


# ============================================================
# Application Status History
# ============================================================

@router.get(
    "/applications/{application_id}/status-history"
)
def get_status_history(application_id: int, user: CurrentUser):
    try:
        require_application_access(user, application_id)
        application = get_application(application_id)

        if application is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Application with id {application_id} "
                    f"does not exist."
                ),
            )

        return {
            "application_id": application_id,
            "history": [
                {
                    key: value
                    for key, value in record.items()
                    if key != "changed_by" or user.role != "STUDENT"
                }
                for record in get_application_status_history(application_id)
            ],
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


# ============================================================
# Committee Assignment
# ============================================================

@router.post(
    "/applications/{application_id}/committee"
)
def assign_application_to_committee(
    application_id: int,
    request: CommitteeAssignmentRequest,
    user: CurrentUser,
):
    try:
        require_application_access(user, application_id, "OFFICIAL")
        return assign_to_committee(
            application_id=application_id,
            committee_type=request.committee_type,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


# ============================================================
# Committee Reviews
# ============================================================

@router.get(
    "/applications/{application_id}/committee-reviews"
)
def get_application_committee_reviews(
    application_id: int,
    user: CurrentUser,
):
    try:
        require_application_access(user, application_id)
        reviews = get_committee_reviews(application_id)
        if user.role == "DUGC":
            reviews = [
                review
                for review in reviews
                if is_committee_member(user, review["committee_type"])
            ]
        elif user.role == "STUDENT":
            reviews = [
                {
                    key: value
                    for key, value in review.items()
                    if key != "decided_by"
                }
                for review in reviews
            ]
        return {
            "application_id": application_id,
            "reviews": reviews,
        }

    except HTTPException:
        raise

    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e),
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


# ============================================================
# Committee Decision
# ============================================================

@router.patch(
    "/committee-reviews/{review_id}/decision"
)
def record_application_committee_decision(
    review_id: int,
    request: CommitteeDecisionRequest,
    user: CurrentUser,
):
    try:
        if user.role != "DUGC":
            raise HTTPException(
                status_code=403,
                detail="Only assigned DUGC members may record a committee decision.",
            )
        application_id = get_review_access(user, review_id)
        if application_id is None:
            raise HTTPException(
                status_code=404,
                detail="Committee review not found.",
            )
        return record_committee_decision(
            review_id=review_id,
            decision=request.decision,
            decision_reason=request.decision_reason,
            decided_by=user.username,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


# ============================================================
# Audit Logs
# ============================================================

@router.get(
    "/applications/{application_id}/audit-logs"
)
def get_application_audit_logs_endpoint(
    application_id: int,
    user: CurrentUser,
):
    require_application_access(user, application_id, "OFFICIAL", "DUGC")
    raise HTTPException(
        status_code=403,
        detail="Audit visibility policy is not configured.",
    )


# ============================================================
# AI-Assisted Application Analysis
# ============================================================

@router.post(
    "/applications/{application_id}/ai-analysis"
)
def generate_application_analysis_endpoint(
    application_id: int,
    user: CurrentUser,
):
    try:
        require_application_access(user, application_id, "STUDENT")
        result = generate_application_analysis(
            application_id
        )

        return result

    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e),
        )

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


# ============================================================
# Complete Application Processing
# ============================================================

@router.post(
    "/applications/{application_id}/process"
)
def process_application_endpoint(
    application_id: int,
    user: CurrentUser,
):
    try:
        require_application_access(user, application_id, "OFFICIAL")
        return process_application(application_id)

    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e),
        )

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )

# DEPARTMENTAI_MODULE2_DATA_EXPORT_ROUTER
from module2.data_export.router import router as module2_data_export_router
router.include_router(module2_data_export_router, prefix="/module2/export", tags=["Module II Data Export"])

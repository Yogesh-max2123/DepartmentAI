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
from pydantic import BaseModel, ConfigDict, Field

from backend.api.access import require_application_access, require_role
from backend.api.auth_routes import (
    get_current_user,
    get_programme_identity_provider,
)
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
    ApplicationValidationError,
    InvalidApplicationState,
    create_application,
    submit_application,
    update_application,
    update_application_status,
    get_application,
    get_application_status_history,
)

from backend.services.document_service import (
    DocumentUploadStateError,
    get_document_download,
    upload_document,
    get_application_documents,
)

from backend.services.document_validator import validate_document
from backend.services.document_extractor import (
    DocumentExtractionNotFoundError,
    extract_document_text,
)
from backend.services.document_classifier import (
    DocumentNotFoundError,
    classify_document,
)
from backend.services.application_retrieval import (
    retrieve_ordinance_for_application,
)
from backend.services.eligibility_engine import (
    analyze_application_eligibility,
    get_stored_eligibility_results,
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
    ApplicationProcessingUnavailable,
    process_application,
)
from backend.services.application_readiness_service import (
    ReadinessAnalysisStateError,
    ReadinessSubmissionError,
    analyze_application_readiness,
    get_application_readiness,
)
from backend.services.yogesh_integration_service import (
    YogeshIntegrationError,
    generate_application_advisory,
    get_latest_application_advisory,
)
from backend.services.knowledge_retrieval_service import (
    KnowledgeRetrievalUnavailable,
    list_knowledge_sources,
    retrieve_knowledge,
)
from backend.services.application_policy_registry import (
    load_application_policy_registry,
    resolve_application_policy,
)
from backend.services.programme_identity import resolve_programme_identity
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
    conversation_history: list[dict] = Field(default_factory=list)
    programme: Literal["UG", "MTECH", "PHD"] = "UG"


class KnowledgeSearchRequest(BaseModel):
    domain: Literal["ORDINANCE"] = "ORDINANCE"
    query: str = Field(min_length=1, max_length=2000)
    programme: Literal["UG", "MTECH", "PHD"] | None = None
    application_id: int | None = Field(default=None, gt=0)
    source_ids: list[str] | None = Field(default=None, max_length=10)
    source_types: list[Literal["ORDINANCE"]] = Field(
        default_factory=lambda: ["ORDINANCE"],
        max_length=3,
    )
    source_version: str | None = Field(default=None, max_length=128)
    section_numbers: list[str] | None = Field(default=None, max_length=20)
    limit: int = Field(default=5, ge=1, le=5)


class AskResponse(BaseModel):
    answer: str
    sources: list


# ============================================================
# Committee Requests
# ============================================================

class CommitteeAssignmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    committee_type: Literal["DUGC", "DMPC", "DDPC"]


class CommitteeDecisionRequest(BaseModel):
    decision: str = Field(min_length=1, max_length=32)
    decision_reason: str = Field(min_length=1, max_length=2000)


# ============================================================
# Ask / RAG
# ============================================================

@router.get("/knowledge/sources")
def read_knowledge_sources(user: CurrentUser):
    try:
        return list_knowledge_sources()
    except KnowledgeRetrievalUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail={"code": error.code, "message": error.message},
        ) from error


@router.post("/knowledge/search")
def search_knowledge(
    request: KnowledgeSearchRequest,
    user: CurrentUser,
    identity_provider=Depends(get_programme_identity_provider),
):
    source_ids = request.source_ids
    programme = request.programme
    application_scoped = request.application_id is not None
    if application_scoped:
        try:
            require_application_access(user, request.application_id)
        except HTTPException:
            raise
        application = get_application(request.application_id)
        if application is None:
            raise HTTPException(
                status_code=404,
                detail="Application not found.",
            )
        identity = resolve_programme_identity(
            application["applicant_identifier"],
            identity_provider,
        )
        if identity.status != "VERIFIED":
            raise HTTPException(
                status_code=409,
                detail={
                    "code": f"PROGRAMME_IDENTITY_{identity.status}",
                    "message": (
                        "A verified programme identity is required for "
                        "application-scoped knowledge retrieval."
                    ),
                },
            )
        policy = resolve_application_policy(
            application["application_type"],
            identity.programme,
            load_application_policy_registry(),
        )
        if policy["status"] != "RESOLVED":
            raise HTTPException(
                status_code=409,
                detail={
                    "code": f"APPLICATION_POLICY_{policy['status']}",
                    "message": (
                        "No approved application policy is available for "
                        "this application's knowledge scope."
                    ),
                },
            )
        policy_type = policy["application_type"]
        if programme is not None and programme != policy_type["programme"]:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "PROGRAMME_SCOPE_MISMATCH",
                    "message": (
                        "The requested programme does not match the "
                        "verified application policy."
                    ),
                },
            )
        programme = policy_type["programme"]
        policy_source_ids = set(policy_type["source_ids"])
        if source_ids is not None and not set(source_ids) <= policy_source_ids:
            raise HTTPException(
                status_code=422,
                detail="A requested source is outside the approved policy.",
            )
        source_ids = source_ids or policy_type["source_ids"]
    elif programme is None:
        raise HTTPException(
            status_code=422,
            detail="An explicit programme scope is required.",
        )

    try:
        return retrieve_knowledge(
            request.query,
            programme,
            source_ids=source_ids,
            source_types=request.source_types,
            source_version=request.source_version,
            section_numbers=request.section_numbers,
            limit=request.limit,
            application_scoped=application_scoped,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except KnowledgeRetrievalUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail={"code": error.code, "message": error.message},
        ) from error


@router.post("/ask", response_model=AskResponse)
def ask_question(request: AskRequest, user: CurrentUser):
    try:
        answer, results = answer_question(
            request.question,
            request.conversation_history,
            programme=request.programme,
        )
        return {
            "answer": answer,
            "sources": format_sources(results),
        }
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except KnowledgeRetrievalUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail={"code": error.code, "message": error.message},
        ) from error
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "ACADEMIC_ASSISTANT_UNAVAILABLE",
                "message": (
                    "The Academic Assistant is temporarily unavailable."
                ),
            },
        ) from error


# ============================================================
# Application Processing
# ============================================================

class ApplicationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    application_type: str = Field(min_length=1, max_length=100)
    title: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=10000)


class ApplicationCreateResponse(BaseModel):
    id: int
    application_number: str
    status: str
    created_at: object


class ApplicationDraftUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    application_type: str = Field(min_length=1, max_length=100)
    title: str | None = Field(..., max_length=200)
    description: str | None = Field(..., max_length=10000)


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
def submit_student_application(
    application_id: int,
    user: CurrentUser,
    identity_provider=Depends(get_programme_identity_provider),
):
    require_application_access(user, application_id, "STUDENT")
    try:
        return submit_application(
            application_id,
            submitted_by=user.username,
            identity_provider=identity_provider,
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except InvalidApplicationState as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ApplicationValidationError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except ReadinessSubmissionError as error:
        raise HTTPException(
            status_code=409,
            detail={
                "code": error.state,
                "message": error.message,
            },
        ) from error


@router.get("/applications/{application_id}/readiness")
def read_application_readiness(
    application_id: int,
    user: CurrentUser,
    identity_provider=Depends(get_programme_identity_provider),
):
    require_application_access(user, application_id)
    try:
        return get_application_readiness(application_id, identity_provider)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/applications/{application_id}/analysis")
def read_application_analysis(
    application_id: int,
    user: CurrentUser,
    identity_provider=Depends(get_programme_identity_provider),
):
    require_application_access(user, application_id)
    try:
        readiness = get_application_readiness(
            application_id,
            identity_provider,
        )
        eligibility = get_stored_eligibility_results(application_id)
    except (LookupError, ValueError) as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return {
        "schema_version": 1,
        "application_id": application_id,
        "analysis_status": readiness["readiness_status"],
        "freshness_status": (
            "STALE" if readiness.get("is_stale") else "CURRENT"
        ),
        "readiness": readiness,
        "eligibility": eligibility,
        "eligibility_freshness": "NOT_TRACKED",
        "advisory": True,
        "formal_decision": False,
        "yogesh_advisory": get_latest_application_advisory(application_id),
    }


@router.post("/applications/{application_id}/yogesh-advisory")
def run_yogesh_application_advisory(
    application_id: int,
    user: CurrentUser,
    identity_provider=Depends(get_programme_identity_provider),
):
    require_application_access(user, application_id, "STUDENT")
    application = get_application(application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found.")
    if application["status"] != "DRAFT":
        raise HTTPException(
            status_code=409,
            detail="Ordinance advisory is available only for a draft application.",
        )

    identity = resolve_programme_identity(
        application["applicant_identifier"],
        identity_provider,
    )
    if identity.status != "VERIFIED" or identity.programme not in {"MTECH", "PHD"}:
        raise HTTPException(
            status_code=409,
            detail="A verified M.Tech or PhD programme identity is required.",
        )
    policy = resolve_application_policy(
        application["application_type"],
        identity.programme,
        load_application_policy_registry(),
    )
    if (
        policy["status"] != "RESOLVED"
        or policy["application_type"].get("activation_scope") != "TEST_ONLY"
    ):
        raise HTTPException(
            status_code=409,
            detail="The draft does not have a resolved test-only application policy.",
        )
    try:
        return generate_application_advisory(
            application_id,
            application,
            identity.programme,
        )
    except YogeshIntegrationError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail=str(error),
        ) from error


@router.post("/applications/{application_id}/readiness/analyze")
def run_application_readiness_analysis(
    application_id: int,
    user: CurrentUser,
    identity_provider=Depends(get_programme_identity_provider),
):
    require_application_access(user, application_id, "STUDENT")
    try:
        return analyze_application_readiness(
            application_id,
            identity_provider,
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ReadinessAnalysisStateError as error:
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

    except ApplicationValidationError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        ) from e

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


@router.patch("/applications/{application_id}")
def update_student_draft(
    application_id: int,
    request: ApplicationDraftUpdateRequest,
    user: CurrentUser,
):
    try:
        require_application_access(user, application_id, "STUDENT")
        return update_application(
            application_id,
            application_type=request.application_type,
            title=request.title,
            description=request.description,
            updated_by=user.username,
        )
    except HTTPException:
        raise
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except InvalidApplicationState as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ApplicationValidationError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


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

    except DocumentUploadStateError as e:
        raise HTTPException(
            status_code=409,
            detail=str(e),
        ) from e

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
        result = extract_document_text(document_id, application_id)

        # Make sure the returned document ID matches
        if result.get("document_id") != document_id:
            raise HTTPException(
                status_code=404,
                detail="Document not found.",
            )

        return result

    except DocumentExtractionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

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
        result = classify_document(document_id, application_id)

        if result.get("application_id") != application_id:
            raise HTTPException(
                status_code=404,
                detail="Document does not belong to this application.",
            )

        return result

    except DocumentNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e),
        ) from e

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
    identity_provider=Depends(get_programme_identity_provider),
):
    try:
        require_application_access(user, application_id)
        application = get_application(application_id)
        if application is None:
            raise HTTPException(
                status_code=404,
                detail="Application not found.",
            )
        identity = resolve_programme_identity(
            application["applicant_identifier"],
            identity_provider,
        )
        if identity.status != "VERIFIED":
            raise HTTPException(
                status_code=409,
                detail={
                    "code": f"PROGRAMME_IDENTITY_{identity.status}",
                    "message": (
                        "A verified programme identity is required before "
                        "retrieving application-specific ordinance rules."
                    ),
                },
            )
        policy = resolve_application_policy(
            application["application_type"],
            identity.programme,
            load_application_policy_registry(),
        )
        if policy["status"] != "RESOLVED":
            raise HTTPException(
                status_code=409,
                detail={
                    "code": f"APPLICATION_POLICY_{policy['status']}",
                    "message": (
                        "No approved application-type-to-policy mapping is "
                        "configured for this application."
                    ),
                },
            )
        result = retrieve_ordinance_for_application(
            application_id,
            programme=policy["application_type"]["programme"],
            source_ids=policy["application_type"]["source_ids"],
        )
        result["policy_source_ids"] = policy["application_type"]["source_ids"]
        return result

    except KnowledgeRetrievalUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail={"code": error.code, "message": error.message},
        ) from error
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


@router.get(
    "/applications/{application_id}/eligibility/results"
)
def get_application_eligibility_results(
    application_id: int,
    user: CurrentUser,
):
    try:
        require_application_access(user, application_id)
        return get_stored_eligibility_results(application_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        ) from error


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
            assigned_by=user.username,
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
    identity_provider=Depends(get_programme_identity_provider),
):
    try:
        require_application_access(user, application_id, "OFFICIAL")
        return process_application(application_id, identity_provider)

    except ApplicationProcessingUnavailable as error:
        raise HTTPException(
            status_code=409,
            detail={"code": error.code, "message": error.message},
        ) from error
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

from typing import Annotated, Literal

import psycopg
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from backend.database.connection import get_connection
from backend.services.auth_service import (
    AuthenticatedUser,
    SESSION_LIFETIME,
    authenticate_user,
    require_development_authentication,
    resolve_session,
    revoke_session,
)
from backend.services.local_demo import (
    LocalDemoProgrammeIdentityProvider,
    local_demo_enabled,
)
from backend.services.programme_identity import resolve_programme_identity


router = APIRouter()
bearer_scheme = HTTPBearer(auto_error=False)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)


class AuthenticatedUserResponse(BaseModel):
    username: str
    role: str
    subject_identifier: str
    programme_identity_status: Literal[
        "VERIFIED",
        "UNVERIFIED",
        "NOT_CONFIGURED",
        "UNAVAILABLE",
        "CONFLICT",
    ] | None = None
    verified_programme: str | None = None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: AuthenticatedUserResponse


def get_programme_identity_provider():
    if local_demo_enabled():
        return LocalDemoProgrammeIdentityProvider()
    return None


def _user_response(
    user: AuthenticatedUser,
    identity_provider=None,
) -> AuthenticatedUserResponse:
    identity = (
        resolve_programme_identity(
            user.subject_identifier,
            identity_provider,
        )
        if user.role == "STUDENT"
        else None
    )
    return AuthenticatedUserResponse(
        username=user.username,
        role=user.role,
        subject_identifier=user.subject_identifier,
        programme_identity_status=identity.status if identity else None,
        verified_programme=(
            identity.programme
            if identity and identity.status == "VERIFIED"
            else None
        ),
    )


def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
) -> AuthenticatedUser:
    try:
        require_development_authentication()
    except (RuntimeError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid bearer session is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        user = resolve_session(credentials.credentials)
    except psycopg.Error as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is temporarily unavailable.",
        ) from error
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The session is invalid, expired, or revoked.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


@router.post("/auth/login", response_model=LoginResponse)
def login(
    request: LoginRequest,
    identity_provider=Depends(get_programme_identity_provider),
):
    try:
        result = authenticate_user(request.username, request.password)
    except (RuntimeError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    except psycopg.Error as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is temporarily unavailable.",
        ) from error

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token, user = result
    return LoginResponse(
        access_token=token,
        expires_in=int(SESSION_LIFETIME.total_seconds()),
        user=_user_response(user, identity_provider),
    )


@router.get("/auth/me", response_model=AuthenticatedUserResponse)
def current_user(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    identity_provider=Depends(get_programme_identity_provider),
):
    return _user_response(user, identity_provider)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    credentials: Annotated[
        HTTPAuthorizationCredentials,
        Depends(bearer_scheme),
    ],
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
):
    try:
        revoke_session(credentials.credentials)
    except psycopg.Error as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is temporarily unavailable.",
        ) from error
    return None


@router.get("/health/live")
def live_health():
    return {"status": "ok"}


@router.get("/health/ready")
def readiness():
    try:
        connection = get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        to_regclass('public.applications'),
                        to_regclass('public.auth_users'),
                        to_regclass('public.auth_sessions'),
                        to_regclass('public.official_application_assignments'),
                        to_regclass('public.committee_memberships');
                    """
                )
                tables = cursor.fetchone()
                if not all(tables):
                    raise RuntimeError("Required application schema is missing.")
        finally:
            connection.close()
    except (RuntimeError, ValueError, psycopg.Error) as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database readiness check failed.",
        ) from error
    return {"status": "ready"}

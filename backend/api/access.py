from fastapi import HTTPException, status

from backend.services.auth_service import AuthenticatedUser, get_application_access


def require_role(user: AuthenticatedUser, *allowed_roles: str) -> None:
    if user.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is not permitted to perform this action.",
        )


def require_application_access(
    user: AuthenticatedUser,
    application_id: int,
    *allowed_roles: str,
) -> None:
    if allowed_roles:
        require_role(user, *allowed_roles)
    if not get_application_access(user, application_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found.",
        )

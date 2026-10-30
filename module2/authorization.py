import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Callable

from fastapi import Depends, HTTPException, status

from backend.api.auth_routes import get_current_user
from backend.services.auth_service import AuthenticatedUser


MODULE2_PERMISSION_POLICY_ENV = "DEPARTMENTAI_MODULE2_PERMISSION_POLICY"
MAX_DEPARTMENTS_PER_GRANT = 25
MAX_POLICY_BYTES = 64 * 1024
SUPPORTED_PERMISSIONS = frozenset(
    {
        "module2.faculty.read",
        "module2.research.read",
        "module2.research.statistics.read",
        "module2.data_quality.read",
        "module2.reports.generate",
        "module2.export.faculty_profiles",
        "module2.export.publications",
    }
)


class Module2PermissionConfigurationError(RuntimeError):
    """Raised when an explicitly configured Module II permission policy is invalid."""


@dataclass(frozen=True)
class Module2AccessGrant:
    user_id: int
    permissions: frozenset[str]
    departments: tuple[str, ...]


def _read_permission_grants() -> dict[int, Module2AccessGrant]:
    policy_path = os.getenv(MODULE2_PERMISSION_POLICY_ENV)
    if not policy_path:
        return {}

    path = Path(policy_path)
    try:
        if path.stat().st_size > MAX_POLICY_BYTES:
            raise Module2PermissionConfigurationError(
                "The Module II permission policy exceeds its size limit."
            )
        policy = json.loads(path.read_text(encoding="utf-8"))
    except Module2PermissionConfigurationError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise Module2PermissionConfigurationError(
            "The configured Module II permission policy is unavailable or invalid."
        ) from error

    if not isinstance(policy, dict) or set(policy) != {"users"}:
        raise Module2PermissionConfigurationError(
            "The Module II permission policy must contain only a users object."
        )
    users = policy["users"]
    if not isinstance(users, dict) or len(users) > 500:
        raise Module2PermissionConfigurationError(
            "The Module II permission policy users value is invalid."
        )

    grants: dict[int, Module2AccessGrant] = {}
    for raw_user_id, entry in users.items():
        try:
            user_id = int(raw_user_id)
        except (TypeError, ValueError) as error:
            raise Module2PermissionConfigurationError(
                "Module II permission policy keys must be user IDs."
            ) from error
        if user_id <= 0 or str(user_id) != str(raw_user_id):
            raise Module2PermissionConfigurationError(
                "Module II permission policy keys must be positive user IDs."
            )
        if not isinstance(entry, dict) or set(entry) != {
            "permissions",
            "departments",
        }:
            raise Module2PermissionConfigurationError(
                "Each Module II user grant must define permissions and departments."
            )
        permissions = entry["permissions"]
        departments = entry["departments"]
        if (
            not isinstance(permissions, list)
            or any(
                not isinstance(permission, str)
                or permission not in SUPPORTED_PERMISSIONS
                for permission in permissions
            )
        ):
            raise Module2PermissionConfigurationError(
                "The Module II permission policy contains an unsupported permission."
            )
        if (
            not isinstance(departments, list)
            or not departments
            or len(departments) > MAX_DEPARTMENTS_PER_GRANT
            or any(
                not isinstance(department, str)
                or not department.strip()
                or department.strip() == "*"
                or department != department.strip()
                or len(department) > 200
                for department in departments
            )
        ):
            raise Module2PermissionConfigurationError(
                "The Module II permission policy contains an invalid department scope."
            )
        if len(set(departments)) != len(departments):
            raise Module2PermissionConfigurationError(
                "The Module II permission policy contains duplicate departments."
            )
        grants[user_id] = Module2AccessGrant(
            user_id=user_id,
            permissions=frozenset(permissions),
            departments=tuple(departments),
        )
    return grants


def get_module2_access_grant(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> Module2AccessGrant:
    try:
        grant = _read_permission_grants().get(user.id)
    except Module2PermissionConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Module II permission configuration is unavailable.",
        ) from error
    if grant is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No Module II access is configured for this account.",
        )
    return grant


def authorize_module2_permission(
    grant: Module2AccessGrant,
    permission: str,
) -> None:
    if permission not in SUPPORTED_PERMISSIONS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This Module II capability is not configured.",
        )
    if permission not in grant.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This Module II operation is not permitted.",
        )
    if not grant.departments:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No Module II department scope is configured for this account.",
        )


def require_module2_permission(permission: str) -> Callable:
    def check_permission(
        grant: Annotated[Module2AccessGrant, Depends(get_module2_access_grant)],
    ) -> Module2AccessGrant:
        authorize_module2_permission(grant, permission)
        return grant

    return check_permission

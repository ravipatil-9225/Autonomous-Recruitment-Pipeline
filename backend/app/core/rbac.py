"""
Role-Based Access Control (RBAC)
──────────────────────────────────
Provides FastAPI dependencies for permission enforcement.

Role hierarchy (descending privilege):
  admin > recruiter > hiring_manager > viewer

Usage in a router:
    @router.post("/jobs/{id}/close")
    async def close_job(
        job_id: UUID,
        _: User = Depends(require_roles(UserRole.recruiter, UserRole.admin)),
        ...
    ):
"""
from fastapi import Depends, HTTPException, status

from backend.app.models.user import User, UserRole

# Define role ordering (higher index = higher privilege)
_ROLE_RANK: dict[UserRole, int] = {
    UserRole.viewer: 0,
    UserRole.hiring_manager: 1,
    UserRole.recruiter: 2,
    UserRole.admin: 3,
}


def require_roles(*roles: UserRole):
    """
    Dependency factory that raises 403 if the current user's role
    is not one of the allowed roles.

    Usage:
        Depends(require_roles(UserRole.recruiter, UserRole.admin))
    """
    allowed = set(roles)

    async def _check(current_user: User = Depends(_get_current_user_placeholder)) -> User:
        if current_user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Insufficient permissions. Required: {[r.value for r in roles]}. "
                    f"Your role: {current_user.role.value}"
                ),
            )
        return current_user

    return _check


def require_min_role(min_role: UserRole):
    """
    Dependency factory that requires at least the given role level.
    E.g., require_min_role(UserRole.recruiter) allows recruiter AND admin.
    """
    min_rank = _ROLE_RANK[min_role]

    async def _check(current_user: User = Depends(_get_current_user_placeholder)) -> User:
        if _ROLE_RANK.get(current_user.role, -1) < min_rank:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Minimum role '{min_role.value}' required. "
                    f"Your role: {current_user.role.value}"
                ),
            )
        return current_user

    return _check


# ── Placeholder — replaced by real dependency in dependencies.py ──────────────
# This avoids a circular import; dependencies.py overrides this at app startup.

async def _get_current_user_placeholder() -> User:  # pragma: no cover
    raise NotImplementedError("Inject get_current_active_user from dependencies.py")

"""
Admin Router  (admin-only endpoints)
──────────────────────────────────────
Endpoints:
  POST /admin/users       — create a new user (admin only)
  GET  /admin/users       — list all users
  PUT  /admin/users/{id}/deactivate — deactivate user
  GET  /admin/health      — deep health check (DB, Redis, S3, Chroma)
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, text

from backend.app.auth.service import AuthService
from backend.app.core.rbac import require_roles
from backend.app.dependencies import CurrentUser, DBSession, Redis, get_redis
from backend.app.models.user import User, UserRole
from backend.app.schemas.auth import UserCreateRequest, UserResponse

router = APIRouter(prefix="/admin", tags=["Admin"])

_admin_only = Depends(require_roles(UserRole.admin))


@router.post("/users", response_model=UserResponse, status_code=201, summary="Create user")
async def create_user(
    body: UserCreateRequest,
    db: DBSession,
    redis: Redis,
    _: User = _admin_only,
) -> UserResponse:
    svc = AuthService(db, redis)
    user = await svc.create_user(body)
    return UserResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        role=user.role.value,
        is_active=user.is_active,
    )


@router.get("/users", response_model=list[UserResponse], summary="List all users")
async def list_users(
    db: DBSession,
    _: User = _admin_only,
) -> list[UserResponse]:
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    return [
        UserResponse(
            id=str(u.id),
            email=u.email,
            full_name=u.full_name,
            role=u.role.value,
            is_active=u.is_active,
        )
        for u in users
    ]


@router.put("/users/{user_id}/deactivate", summary="Deactivate user account")
async def deactivate_user(
    user_id: uuid.UUID,
    db: DBSession,
    _: User = _admin_only,
) -> dict:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = False
    await db.flush()
    return {"user_id": str(user_id), "is_active": False}


@router.get("/health", summary="Deep health check")
async def health_check(
    db: DBSession,
    redis: Redis,
    _: User = _admin_only,
) -> dict:
    """Checks connectivity to all backend services."""
    checks: dict[str, str] = {}

    # PostgreSQL
    try:
        await db.execute(text("SELECT 1"))
        checks["postgresql"] = "ok"
    except Exception as exc:
        checks["postgresql"] = f"error: {exc}"

    # Redis
    try:
        await redis.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"error: {exc}"

    # S3/MinIO
    try:
        from backend.app.services import storage_service
        storage_service.ensure_bucket_exists()
        checks["s3_minio"] = "ok"
    except Exception as exc:
        checks["s3_minio"] = f"error: {exc}"

    # Chroma
    try:
        from backend.app.config import settings
        import chromadb
        chroma = chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)
        chroma.heartbeat()
        checks["chroma"] = "ok"
    except Exception as exc:
        checks["chroma"] = f"error: {exc}"

    overall = "healthy" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": overall, "services": checks}

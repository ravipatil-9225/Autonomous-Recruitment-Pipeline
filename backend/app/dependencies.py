"""
FastAPI Dependencies
─────────────────────
Provides reusable dependency functions injected into route handlers:
  • get_db()               — async DB session
  • get_current_user()     — JWT → User ORM object
  • get_current_active_user() — above + is_active check
  • require_roles(...)     — RBAC wrapper
"""
import uuid
from typing import Annotated

import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.app.core import rbac
from backend.app.core.security import decode_token
from backend.app.db.session import get_db
from backend.app.models.user import User, UserRole

# OAuth2 scheme — token from Authorization: Bearer <token>
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# ── Redis client (singleton) ──────────────────────────────────────────────────
_redis_client: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """Return a shared async Redis client."""
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.redis_url, encoding="utf-8", decode_responses=True
        )
    return _redis_client


# ── Current user resolution ───────────────────────────────────────────────────

async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
) -> User:
    """
    Decode JWT, check token is not revoked (Redis blacklist),
    load and return the User from DB.
    """
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
        user_id: str | None = payload.get("sub")
        token_type: str | None = payload.get("type")
        if not user_id or token_type != "access":
            raise credentials_exc
    except JWTError:
        raise credentials_exc

    # Check token not in revocation blacklist
    if await redis.get(f"revoked:{token}"):
        raise credentials_exc

    result = await db.execute(
        select(User).where(User.id == uuid.UUID(user_id))
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exc
    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Ensure the authenticated user is active (not deactivated)."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user account",
        )
    return current_user


# ── Wire RBAC to real dependency ──────────────────────────────────────────────
# Override the placeholder in rbac.py so require_roles() works correctly.
rbac._get_current_user_placeholder = get_current_active_user  # type: ignore[assignment]


# ── Type aliases for cleaner route signatures ─────────────────────────────────
DBSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_active_user)]
Redis = Annotated[aioredis.Redis, Depends(get_redis)]

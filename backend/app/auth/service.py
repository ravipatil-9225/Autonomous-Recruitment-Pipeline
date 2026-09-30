"""
Auth Service
─────────────
Business logic for login, token management, and user creation.
Refresh tokens are stored in Redis (with TTL) for revocation support.
"""

import uuid
from datetime import timedelta

import redis.asyncio as aioredis
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from backend.app.models.user import User, UserRole
from backend.app.schemas.auth import TokenResponse, UserCreateRequest


class AuthService:
    def __init__(self, db: AsyncSession, redis: aioredis.Redis) -> None:
        self.db = db
        self.redis = redis

    # ── Login ──────────────────────────────────────────────────────────────
    async def login(self, email: str, password: str) -> TokenResponse:
        user = await self._get_user_by_email(email)
        if not user or not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Account is deactivated",
            )
        return await self._issue_tokens(user)

    # ── Refresh ────────────────────────────────────────────────────────────
    async def refresh(self, refresh_token: str) -> TokenResponse:
        from jose import JWTError

        try:
            payload = decode_token(refresh_token)
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
            )
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not a refresh token",
            )
        # Check not revoked
        if await self.redis.get(f"revoked_refresh:{refresh_token}"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has been revoked",
            )
        user_id = payload.get("sub")
        result = await self.db.execute(select(User).where(User.id == uuid.UUID(user_id)))
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

        # Rotate: revoke old refresh token, issue new pair
        await self.redis.setex(
            f"revoked_refresh:{refresh_token}",
            int(timedelta(days=settings.refresh_token_expire_days).total_seconds()),
            "1",
        )
        return await self._issue_tokens(user)

    # ── Logout ─────────────────────────────────────────────────────────────
    async def logout(self, access_token: str, refresh_token: str | None = None) -> None:
        # Blacklist access token
        try:
            payload = decode_token(access_token)
            ttl_seconds = max(0, int(payload["exp"]) - int(__import__("time").time()))
            if ttl_seconds > 0:
                await self.redis.setex(f"revoked:{access_token}", ttl_seconds, "1")
        except Exception:
            pass  # already expired — no need to blacklist

        # Revoke refresh token if provided
        if refresh_token:
            await self.redis.setex(
                f"revoked_refresh:{refresh_token}",
                int(timedelta(days=settings.refresh_token_expire_days).total_seconds()),
                "1",
            )

    # ── Create user (admin) ────────────────────────────────────────────────
    async def create_user(self, req: UserCreateRequest) -> User:
        existing = await self._get_user_by_email(req.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"User with email {req.email!r} already exists",
            )
        try:
            role = UserRole(req.role)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid role: {req.role!r}",
            )
        user = User(
            email=req.email,
            hashed_password=hash_password(req.password),
            full_name=req.full_name,
            role=role,
        )
        self.db.add(user)
        await self.db.flush()  # get ID without committing
        return user

    # ── Helpers ────────────────────────────────────────────────────────────
    async def _get_user_by_email(self, email: str) -> User | None:
        result = await self.db.execute(select(User).where(User.email == email.lower()))
        return result.scalar_one_or_none()

    async def _issue_tokens(self, user: User) -> TokenResponse:
        extra = {"role": user.role.value, "name": user.full_name}
        access = create_access_token(str(user.id), extra_claims=extra)
        refresh = create_refresh_token(str(user.id))

        # Store refresh token in Redis for validation later
        await self.redis.setex(
            f"refresh_token:{user.id}:{refresh[-16:]}",
            int(timedelta(days=settings.refresh_token_expire_days).total_seconds()),
            "valid",
        )
        return TokenResponse(
            access_token=access,
            refresh_token=refresh,
            expires_in=settings.access_token_expire_minutes * 60,
        )

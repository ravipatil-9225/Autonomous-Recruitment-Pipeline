"""
Auth Router
────────────
Endpoints:
  POST /auth/login    — email + password → JWT pair
  POST /auth/refresh  — rotate refresh token
  POST /auth/logout   — revoke tokens
  GET  /auth/me       — current user info
"""
from fastapi import APIRouter, Depends, Request
from fastapi.security import OAuth2PasswordRequestForm

from backend.app.auth.service import AuthService
from backend.app.dependencies import CurrentUser, DBSession, Redis, oauth2_scheme
from backend.app.schemas.auth import (
    RefreshRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=TokenResponse, summary="Login with email and password")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: DBSession = None,
    redis: Redis = None,
) -> TokenResponse:
    """
    Authenticate with email (username field) and password.
    Returns access + refresh JWT pair.
    """
    svc = AuthService(db, redis)
    return await svc.login(form_data.username, form_data.password)


@router.post("/refresh", response_model=TokenResponse, summary="Rotate refresh token")
async def refresh_token(
    body: RefreshRequest,
    db: DBSession = None,
    redis: Redis = None,
) -> TokenResponse:
    svc = AuthService(db, redis)
    return await svc.refresh(body.refresh_token)


@router.post("/logout", status_code=204, summary="Revoke tokens")
async def logout(
    request: Request,
    body: RefreshRequest | None = None,
    db: DBSession = None,
    redis: Redis = None,
    token: str = Depends(oauth2_scheme),
) -> None:
    svc = AuthService(db, redis)
    await svc.logout(
        access_token=token,
        refresh_token=body.refresh_token if body else None,
    )


@router.get("/me", response_model=UserResponse, summary="Current user profile")
async def me(current_user: CurrentUser) -> UserResponse:
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role.value,
        is_active=current_user.is_active,
    )

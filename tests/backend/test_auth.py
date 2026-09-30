"""
Auth Endpoints & Security Tests (§12 Security, JWT/OAuth2)
─────────────────────────────────────────────────────────────
"""

import pytest
from httpx import AsyncClient

from backend.app.core.security import decrypt_pii, encrypt_pii, hash_password
from backend.app.models.user import User, UserRole


@pytest.mark.asyncio
async def test_login_success(async_client: AsyncClient, db_session):
    # Seed user
    user = User(
        email="testuser@example.com",
        full_name="Test User",
        hashed_password=hash_password("Secret123!"),
        role=UserRole.recruiter,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    response = await async_client.post(
        "/auth/login",
        data={"username": "testuser@example.com", "password": "Secret123!"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert "expires_in" in data


@pytest.mark.asyncio
async def test_login_invalid_password(async_client: AsyncClient, db_session):
    user = User(
        email="testuser2@example.com",
        full_name="Test User 2",
        hashed_password=hash_password("Secret123!"),
        role=UserRole.recruiter,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    response = await async_client.post(
        "/auth/login",
        data={"username": "testuser2@example.com", "password": "WrongPassword"},
    )
    assert response.status_code == 401
    assert "Incorrect email or password" in response.json()["detail"]


@pytest.mark.asyncio
async def test_unauthorized_access(async_client: AsyncClient):
    response = await async_client.get("/api/v1/jobs")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_rbac_forbidden(async_client: AsyncClient, viewer_headers):
    # Viewer should not be allowed to create jobs
    headers = {"Authorization": viewer_headers["Authorization"]}
    response = await async_client.post(
        "/api/v1/jobs",
        json={"title": "Software Engineer", "raw_jd_text": "Need python dev"},
        headers=headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_pii_encryption():
    raw_email = "candidate@domain.com"
    encrypted = encrypt_pii(raw_email)
    assert encrypted != raw_email
    decrypted = decrypt_pii(encrypted)
    assert decrypted == raw_email

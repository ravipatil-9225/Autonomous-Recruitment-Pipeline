"""
Auth Schemas  (Pydantic v2)
────────────────────────────
Request / response models for the auth endpoints.
"""
from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """POST /auth/login body."""
    email: EmailStr
    password: str = Field(min_length=8)


class TokenResponse(BaseModel):
    """Successful login / token refresh response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds until access token expires


class RefreshRequest(BaseModel):
    """POST /auth/refresh body."""
    refresh_token: str


class UserCreateRequest(BaseModel):
    """POST /admin/users body (admin only)."""
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=2, max_length=255)
    role: str = "viewer"


class UserResponse(BaseModel):
    """Safe user object returned to callers (no password)."""
    id: str
    email: str
    full_name: str
    role: str
    is_active: bool

    model_config = {"from_attributes": True}

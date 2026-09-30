"""
Pytest Fixtures for Backend Tests
───────────────────────────────────
Sets up:
  • In-memory SQLite async DB session or mocked AsyncSession
  • Mocked Redis client
  • FastAPI AsyncClient with dependency overrides
  • Authenticated user tokens & headers for RBAC testing (admin, recruiter, hiring_manager, viewer)
"""

import uuid
from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.core.security import create_access_token, hash_password
from backend.app.db.base import Base
from backend.app.db.session import get_db
from backend.app.dependencies import get_redis
from backend.app.main import app
from backend.app.models.user import User, UserRole

# Async SQLite setup for test database (shared cache so in-memory DB persists across connections)
TEST_DATABASE_URL = "sqlite+aiosqlite:///file:memdb1?mode=memory&cache=shared&uri=true"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class FakeRedis:
    """In-memory Redis fake for test environment."""

    def __init__(self):
        self._store = {}

    async def get(self, key: str):
        return self._store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None):
        self._store[key] = value

    async def delete(self, key: str):
        self._store.pop(key, None)

    async def setex(self, key: str, time: int, value: str):
        self._store[key] = value

    async def ping(self):
        return True

    async def close(self):
        pass


fake_redis = FakeRedis()


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with TestingSessionLocal() as session:
        yield session


async def override_get_redis():
    return fake_redis


app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_redis] = override_get_redis


@pytest_asyncio.fixture(autouse=True)
async def init_db():
    """Create fresh database tables before each test and drop after."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with TestingSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# Helper to create test user in DB and return token headers
async def _create_test_user_and_headers(role: UserRole, email_prefix: str) -> dict:
    async with TestingSessionLocal() as session:
        user_id = uuid.uuid4()
        user = User(
            id=user_id,
            email=f"{email_prefix}@example.com",
            full_name=f"Test {email_prefix}",
            hashed_password=hash_password("password123"),
            role=role,
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

    token = create_access_token(str(user_id), {"role": role.value})
    return {"Authorization": f"Bearer {token}", "user_id": str(user_id)}


@pytest_asyncio.fixture
async def admin_headers():
    return await _create_test_user_and_headers(UserRole.admin, "admin")


@pytest_asyncio.fixture
async def recruiter_headers():
    return await _create_test_user_and_headers(UserRole.recruiter, "recruiter")


@pytest_asyncio.fixture
async def hiring_manager_headers():
    return await _create_test_user_and_headers(UserRole.hiring_manager, "hm")


@pytest_asyncio.fixture
async def viewer_headers():
    return await _create_test_user_and_headers(UserRole.viewer, "viewer")

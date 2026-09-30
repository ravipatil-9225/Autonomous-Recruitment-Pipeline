"""
Application Configuration
──────────────────────────
Centralised settings loaded from environment variables (and .env file).
All modules import `from backend.app.config import settings`.
"""
from functools import lru_cache
from typing import Literal

from pydantic import AnyUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ────────────────────────────────────────────────────────
    app_env: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    app_title: str = "ARP — Autonomous Recruitment Pipeline API"
    app_version: str = "2.0.0"
    app_description: str = (
        "FastAPI backend for the Autonomous Recruitment Pipeline. "
        "Provides REST + WebSocket APIs for job management, resume ingestion, "
        "async pipeline execution, and recruiter tooling."
    )

    # ── Database ────────────────────────────────────────────────────────────
    database_url: str = Field(
        "postgresql+asyncpg://arp:arp_password@localhost:5432/arp_db",
        description="Async SQLAlchemy URL (asyncpg driver)",
    )
    sync_database_url: str = Field(
        "postgresql+psycopg2://arp:arp_password@localhost:5432/arp_db",
        description="Sync URL for Alembic migrations",
    )
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # ── Redis ────────────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # ── Object Storage ───────────────────────────────────────────────────────
    s3_endpoint_url: str | None = None          # None → real AWS S3
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket_resumes: str = "arp-resumes"
    s3_region: str = "us-east-1"

    # ── Vector DB (Chroma) ───────────────────────────────────────────────────
    chroma_host: str = "localhost"
    chroma_port: int = 8001

    # ── MLflow ────────────────────────────────────────────────────────────────
    mlflow_tracking_uri: str = "http://localhost:5001"

    # ── Auth / Security ──────────────────────────────────────────────────────
    secret_key: str = Field(
        "dev_secret_key_change_in_production_32_bytes_long",
        min_length=32,
        description="JWT signing secret",
    )
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    pii_encryption_key: str = Field(
        "kPZ4zU7K9V1xY3m8N0b2V4c6X8z0A2s4D6f8G0h2J4k=",
        description="Base64-encoded 32-byte AES-256-GCM key",
    )

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    rate_limit_default: str = "100/minute"
    rate_limit_upload: str = "10/minute"

    # ── CORS ─────────────────────────────────────────────────────────────────
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # ── File Uploads ─────────────────────────────────────────────────────────
    max_upload_size_mb: int = 10
    allowed_extensions: list[str] = ["pdf", "docx"]

    # ── Phase 1 agent config ─────────────────────────────────────────────────
    google_api_key: str = ""
    match_threshold: float = 0.65
    min_experience_years: int = 2

    @field_validator("allowed_extensions", mode="before")
    @classmethod
    def _split_extensions(cls, v: str | list) -> list[str]:
        if isinstance(v, str):
            return [e.strip().lower() for e in v.split(",")]
        return v

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """Cached singleton – import this everywhere."""
    return Settings()


# Convenience alias
settings: Settings = get_settings()

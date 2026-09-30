"""
Job Schemas  (Pydantic v2)
───────────────────────────
Request / response models for the Job & Requisition endpoints (§11.1).
"""
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class JobCreateRequest(BaseModel):
    """POST /api/v1/jobs — create a new job requisition."""
    title: str = Field(min_length=3, max_length=255)
    raw_jd_text: str = Field(min_length=50, description="Full job description text")
    department: str | None = None
    location: str | None = None


class JobUpdateRequest(BaseModel):
    """PUT /api/v1/jobs/{id} — update a draft job."""
    title: str | None = Field(default=None, min_length=3, max_length=255)
    raw_jd_text: str | None = Field(default=None, min_length=50)
    department: str | None = None
    location: str | None = None


class JobResponse(BaseModel):
    """Full job object returned to callers."""
    id: uuid.UUID
    title: str
    department: str | None
    location: str | None
    raw_jd_text: str
    structured_requirements: dict[str, Any] | None
    status: str
    created_by: uuid.UUID | None
    published_at: datetime | None
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JobSummaryResponse(BaseModel):
    """Lightweight listing item."""
    id: uuid.UUID
    title: str
    department: str | None
    location: str | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedJobsResponse(BaseModel):
    items: list[JobSummaryResponse]
    total: int
    page: int
    page_size: int
    pages: int

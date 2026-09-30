"""
Candidate / Resume Schemas  (Pydantic v2)
──────────────────────────────────────────
Request / response models for §11.2 Resume Ingestion.
Note: PII fields (name, email, phone) are NEVER included in raw DB form —
they are always decrypted in the service layer before being placed here.
"""
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── Resume ────────────────────────────────────────────────────────────────────

class ResumeUploadResponse(BaseModel):
    """Returned immediately after upload — file stored, parse dispatched."""
    resume_id: uuid.UUID
    candidate_id: uuid.UUID
    original_filename: str
    file_size_bytes: int
    parse_task_id: str
    parse_status: str
    message: str = "Resume uploaded. Parsing in progress."


class ResumeStatusResponse(BaseModel):
    """Status check for async parse task."""
    resume_id: uuid.UUID
    parse_status: str          # pending | processing | done | failed
    parse_task_id: str | None
    parsed_at: datetime | None


class ParsedResumeResponse(BaseModel):
    """Full parsed resume data (once parse_status == done)."""
    resume_id: uuid.UUID
    candidate_id: uuid.UUID
    original_filename: str
    file_size_bytes: int
    content_type: str
    parse_status: str
    parsed_data: dict[str, Any] | None
    uploaded_at: datetime
    parsed_at: datetime | None

    model_config = {"from_attributes": True}


class BulkUploadResponse(BaseModel):
    """Response for bulk upload endpoint."""
    job_id: uuid.UUID
    total_files: int
    accepted: int
    rejected: int
    bulk_task_id: str
    resume_ids: list[uuid.UUID]
    errors: list[str]


# ── Candidate ─────────────────────────────────────────────────────────────────

class CandidateResponse(BaseModel):
    """Safe candidate view — PII already decrypted by service layer."""
    id: uuid.UUID
    name: str        # decrypted
    email: str       # decrypted
    phone: str | None  # decrypted
    is_deleted: bool
    created_at: datetime
    resumes: list[ParsedResumeResponse] = []

    model_config = {"from_attributes": False}  # manual construction in service


class DeleteCandidateResponse(BaseModel):
    """Result of right-to-deletion request."""
    candidate_id: uuid.UUID
    pii_wiped: bool
    s3_files_deleted: int
    chroma_embeddings_deleted: int
    message: str

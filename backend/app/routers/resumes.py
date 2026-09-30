"""
Resume Router  (§11.2 — Resume Ingestion)
──────────────────────────────────────────
Endpoints:
  POST   /api/v1/resumes/upload       — single PDF/DOCX upload
  POST   /api/v1/resumes/bulk-upload  — multi-file bulk upload
  GET    /api/v1/resumes/{id}         — get parsed resume
  DELETE /api/v1/resumes/candidate/{id} — GDPR right-to-deletion
"""

import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile

from backend.app.core.rbac import require_min_role, require_roles
from backend.app.dependencies import DBSession
from backend.app.models.user import User, UserRole
from backend.app.schemas.candidate import (
    BulkUploadResponse,
    DeleteCandidateResponse,
    ParsedResumeResponse,
    ResumeUploadResponse,
)
from backend.app.services.resume_service import ResumeService

router = APIRouter(prefix="/api/v1/resumes", tags=["Resumes"])


@router.post(
    "/upload",
    response_model=ResumeUploadResponse,
    status_code=202,
    summary="Upload single resume (PDF or DOCX)",
)
async def upload_resume(
    db: DBSession,
    file: UploadFile = File(..., description="Resume file (PDF or DOCX, max 10 MB)"),
    job_id: uuid.UUID | None = Form(None, description="Optional associated job ID"),
    _: User = Depends(require_min_role(UserRole.recruiter)),
) -> ResumeUploadResponse:
    """
    Upload a single resume. File is stored in S3/MinIO immediately.
    Parsing is dispatched as a background Celery task.
    Returns task_id to poll parse status.
    """
    svc = ResumeService(db)
    return await svc.upload_resume(file, job_id=job_id)


@router.post(
    "/bulk-upload",
    response_model=BulkUploadResponse,
    status_code=202,
    summary="Bulk upload resumes (up to 50 files)",
)
async def bulk_upload(
    db: DBSession,
    job_id: uuid.UUID = Form(..., description="Job ID to associate with all resumes"),
    files: list[UploadFile] = File(..., description="Up to 50 PDF/DOCX files"),
    _: User = Depends(require_min_role(UserRole.recruiter)),
) -> BulkUploadResponse:
    """
    Upload multiple resumes at once for a specific job.
    All parsing happens asynchronously (§12 Scalability NFR: bulk batches must be async).
    """
    if len(files) > 50:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="Maximum 50 files per bulk upload.")
    svc = ResumeService(db)
    return await svc.bulk_upload_resumes(files, job_id=job_id)


@router.get(
    "/{resume_id}",
    response_model=ParsedResumeResponse,
    summary="Get parsed resume data",
)
async def get_resume(
    resume_id: uuid.UUID,
    db: DBSession,
    _: User = Depends(require_min_role(UserRole.recruiter)),
) -> ParsedResumeResponse:
    svc = ResumeService(db)
    return await svc.get_resume(resume_id)


@router.delete(
    "/candidate/{candidate_id}",
    response_model=DeleteCandidateResponse,
    summary="GDPR right-to-deletion — wipe all candidate PII",
)
async def delete_candidate_pii(
    candidate_id: uuid.UUID,
    db: DBSession,
    _: User = Depends(require_roles(UserRole.admin)),
) -> DeleteCandidateResponse:
    """
    Permanently wipe all PII for a candidate:
    - Encrypts DB fields with [DELETED] sentinel
    - Deletes all resume files from S3/MinIO
    - Removes embeddings from Chroma
    Admin role required. This action is irreversible.
    """
    svc = ResumeService(db)
    return await svc.delete_candidate_pii(candidate_id)

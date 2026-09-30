"""
Job Router  (§11.1 — Job & Requisition Management)
────────────────────────────────────────────────────
Endpoints:
  GET    /api/v1/jobs              — list (paginated, filterable)
  POST   /api/v1/jobs              — create draft job
  GET    /api/v1/jobs/{id}         — get job detail
  PUT    /api/v1/jobs/{id}         — update draft job
  POST   /api/v1/jobs/{id}/publish — draft → open
  POST   /api/v1/jobs/{id}/close   — open → closed
"""

import uuid

from fastapi import APIRouter, Depends, Query

from backend.app.core.rbac import require_min_role, require_roles
from backend.app.dependencies import DBSession
from backend.app.models.user import User, UserRole
from backend.app.schemas.job import (
    JobCreateRequest,
    JobResponse,
    JobUpdateRequest,
    PaginatedJobsResponse,
)
from backend.app.services.job_service import JobService

router = APIRouter(prefix="/api/v1/jobs", tags=["Jobs"])


@router.get("", response_model=PaginatedJobsResponse, summary="List jobs")
async def list_jobs(
    db: DBSession,
    status: str | None = Query(None, description="Filter by status: draft|open|closed|archived"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: User = Depends(require_min_role(UserRole.viewer)),
) -> PaginatedJobsResponse:
    svc = JobService(db)
    return await svc.list_jobs(status_filter=status, page=page, page_size=page_size)


@router.post("", response_model=JobResponse, status_code=201, summary="Create job requisition")
async def create_job(
    body: JobCreateRequest,
    db: DBSession,
    current_user: User = Depends(require_min_role(UserRole.recruiter)),
) -> JobResponse:
    svc = JobService(db)
    return await svc.create_job(body, current_user)


@router.get("/{job_id}", response_model=JobResponse, summary="Get job detail")
async def get_job(
    job_id: uuid.UUID,
    db: DBSession,
    _: User = Depends(require_min_role(UserRole.viewer)),
) -> JobResponse:
    svc = JobService(db)
    return await svc.get_job(job_id)


@router.put("/{job_id}", response_model=JobResponse, summary="Update draft job")
async def update_job(
    job_id: uuid.UUID,
    body: JobUpdateRequest,
    db: DBSession,
    _: User = Depends(require_min_role(UserRole.recruiter)),
) -> JobResponse:
    svc = JobService(db)
    return await svc.update_job(job_id, body)


@router.post("/{job_id}/publish", response_model=JobResponse, summary="Publish job (draft → open)")
async def publish_job(
    job_id: uuid.UUID,
    db: DBSession,
    _: User = Depends(require_min_role(UserRole.recruiter)),
) -> JobResponse:
    svc = JobService(db)
    return await svc.publish_job(job_id)


@router.post("/{job_id}/close", response_model=JobResponse, summary="Close job (open → closed)")
async def close_job(
    job_id: uuid.UUID,
    db: DBSession,
    _: User = Depends(require_roles(UserRole.hiring_manager, UserRole.admin)),
) -> JobResponse:
    svc = JobService(db)
    return await svc.close_job(job_id)

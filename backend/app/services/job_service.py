"""
Job Service  (§11.1)
─────────────────────
CRUD + state machine for Job / Requisition management.
"""
import math
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.job import Job, JobStatus
from backend.app.models.user import User
from backend.app.schemas.job import (
    JobCreateRequest,
    JobResponse,
    JobSummaryResponse,
    JobUpdateRequest,
    PaginatedJobsResponse,
)


class JobService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Create ─────────────────────────────────────────────────────────────
    async def create_job(self, req: JobCreateRequest, current_user: User) -> JobResponse:
        job = Job(
            title=req.title,
            raw_jd_text=req.raw_jd_text,
            department=req.department,
            location=req.location,
            status=JobStatus.draft,
            created_by=current_user.id,
        )
        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)
        return JobResponse.model_validate(job)

    # ── List ──────────────────────────────────────────────────────────────
    async def list_jobs(
        self,
        status_filter: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedJobsResponse:
        query = select(Job)
        if status_filter:
            try:
                status_enum = JobStatus(status_filter)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Invalid status filter: {status_filter!r}",
                )
            query = query.where(Job.status == status_enum)

        # Total count
        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar_one()

        # Paginated items
        offset = (page - 1) * page_size
        result = await self.db.execute(
            query.order_by(Job.created_at.desc()).offset(offset).limit(page_size)
        )
        jobs = result.scalars().all()

        return PaginatedJobsResponse(
            items=[JobSummaryResponse.model_validate(j) for j in jobs],
            total=total,
            page=page,
            page_size=page_size,
            pages=math.ceil(total / page_size) if total else 1,
        )

    # ── Get ───────────────────────────────────────────────────────────────
    async def get_job(self, job_id: uuid.UUID) -> JobResponse:
        job = await self._get_or_404(job_id)
        return JobResponse.model_validate(job)

    # ── Update ────────────────────────────────────────────────────────────
    async def update_job(self, job_id: uuid.UUID, req: JobUpdateRequest) -> JobResponse:
        job = await self._get_or_404(job_id)
        if job.status != JobStatus.draft:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Only draft jobs can be edited. Current status: {job.status}",
            )
        update_data = req.model_dump(exclude_none=True)
        for field, value in update_data.items():
            setattr(job, field, value)
        await self.db.commit()
        await self.db.refresh(job)
        return JobResponse.model_validate(job)

    # ── Publish ───────────────────────────────────────────────────────────
    async def publish_job(self, job_id: uuid.UUID) -> JobResponse:
        job = await self._get_or_404(job_id)
        if job.status != JobStatus.draft:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Only draft jobs can be published. Current status: {job.status}",
            )
        job.status = JobStatus.open
        job.published_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(job)
        return JobResponse.model_validate(job)

    # ── Close ─────────────────────────────────────────────────────────────
    async def close_job(self, job_id: uuid.UUID) -> JobResponse:
        job = await self._get_or_404(job_id)
        if job.status != JobStatus.open:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Only open jobs can be closed. Current status: {job.status}",
            )
        job.status = JobStatus.closed
        job.closed_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(job)
        return JobResponse.model_validate(job)

    # ── Update structured requirements (called by JD Analyzer task) ───────
    async def set_structured_requirements(
        self, job_id: uuid.UUID, structured: dict, embedding_id: str | None = None
    ) -> None:
        job = await self._get_or_404(job_id)
        job.structured_requirements = structured
        if embedding_id:
            job.jd_embedding_id = embedding_id
        await self.db.commit()

    # ── Private helpers ───────────────────────────────────────────────────
    async def _get_or_404(self, job_id: uuid.UUID) -> Job:
        result = await self.db.execute(select(Job).where(Job.id == job_id))
        job = result.scalar_one_or_none()
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found",
            )
        return job

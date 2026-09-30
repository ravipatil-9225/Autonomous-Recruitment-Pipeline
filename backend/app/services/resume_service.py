"""
Resume Service  (§11.2)
────────────────────────
Orchestrates the resume upload → storage → async parsing flow.
Handles:
  • File validation (type, size)
  • PII encryption + candidate deduplication via email hash
  • S3/MinIO upload
  • Celery task dispatch
  • Right-to-deletion (PII wipe + S3 + Chroma cleanup)
"""

import hashlib
import logging
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.config import settings
from backend.app.core.security import encrypt_pii, hash_email
from backend.app.models.candidate import Candidate, Resume
from backend.app.models.consent import ConsentRecord
from backend.app.schemas.candidate import (
    BulkUploadResponse,
    DeleteCandidateResponse,
    ParsedResumeResponse,
    ResumeUploadResponse,
)
from backend.app.services import storage_service

logger = logging.getLogger(__name__)

_ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
}


class ResumeService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Single Upload ──────────────────────────────────────────────────────
    async def upload_resume(
        self,
        file: UploadFile,
        job_id: uuid.UUID | None = None,
        consent_source: str = "api",
    ) -> ResumeUploadResponse:
        # Validate
        file_bytes, content_type = await self._validate_file(file)

        # Get or create candidate via email placeholder (PII from parse)
        # We create the candidate row now with placeholder encrypted PII;
        # the parse task will update it with real extracted values.
        placeholder_email = f"pending-{uuid.uuid4()}@placeholder.arp"
        consent, candidate = await self._get_or_create_candidate(
            email=placeholder_email,
            name="Pending Parse",
            consent_source=consent_source,
        )

        # Upload to S3/MinIO
        s3_key = f"resumes/{candidate.id}/{uuid.uuid4()}_{file.filename}"
        storage_service.upload_resume(file_bytes, s3_key, content_type)

        # Create Resume row
        resume = Resume(
            candidate_id=candidate.id,
            s3_key=s3_key,
            original_filename=file.filename or "resume",
            file_size_bytes=len(file_bytes),
            content_type=content_type,
            parse_status="pending",
        )
        self.db.add(resume)
        await self.db.commit()

        # Dispatch Celery parse task
        from backend.app.tasks.resume_tasks import parse_resume_task

        task = parse_resume_task.delay(str(resume.id), s3_key, content_type)
        resume.parse_task_id = task.id
        await self.db.commit()

        logger.info(f"Resume {resume.id} uploaded, parse task {task.id} queued.")
        return ResumeUploadResponse(
            resume_id=resume.id,
            candidate_id=candidate.id,
            original_filename=resume.original_filename,
            file_size_bytes=resume.file_size_bytes,
            parse_task_id=task.id,
            parse_status=resume.parse_status,
        )

    # ── Bulk Upload ────────────────────────────────────────────────────────
    async def bulk_upload_resumes(
        self,
        files: list[UploadFile],
        job_id: uuid.UUID,
        consent_source: str = "api",
    ) -> BulkUploadResponse:
        accepted_ids: list[uuid.UUID] = []
        errors: list[str] = []

        for file in files:
            try:
                result = await self.upload_resume(file, job_id=job_id, consent_source=consent_source)
                accepted_ids.append(result.resume_id)
            except HTTPException as exc:
                errors.append(f"{file.filename}: {exc.detail}")
            except Exception as exc:
                errors.append(f"{file.filename}: unexpected error — {exc}")

        # Dispatch bulk Celery task that fans-out individual parse tasks
        from backend.app.tasks.resume_tasks import bulk_parse_task

        task = bulk_parse_task.delay(str(job_id), [str(rid) for rid in accepted_ids])

        return BulkUploadResponse(
            job_id=job_id,
            total_files=len(files),
            accepted=len(accepted_ids),
            rejected=len(errors),
            bulk_task_id=task.id,
            resume_ids=accepted_ids,
            errors=errors,
        )

    # ── Get parsed resume ─────────────────────────────────────────────────
    async def get_resume(self, resume_id: uuid.UUID) -> ParsedResumeResponse:
        resume = await self._get_resume_or_404(resume_id)
        return ParsedResumeResponse.model_validate(resume)

    # ── Right-to-deletion ─────────────────────────────────────────────────
    async def delete_candidate_pii(self, candidate_id: uuid.UUID) -> DeleteCandidateResponse:
        result = await self.db.execute(
            select(Candidate).options(selectinload(Candidate.consent)).where(Candidate.id == candidate_id)
        )
        candidate = result.scalar_one_or_none()
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")

        # 1. Wipe PII fields in DB
        candidate.name_encrypted = encrypt_pii("[DELETED]")
        candidate.email_encrypted = encrypt_pii("[DELETED]")
        candidate.phone_encrypted = None
        candidate.email_hash = hashlib.sha256(b"[DELETED]").hexdigest()
        candidate.is_deleted = True

        # Mark consent record as deleted
        if candidate.consent:
            candidate.consent.deleted_at = datetime.now(UTC)

        # 2. Delete S3 files
        s3_deleted = 0
        resume_result = await self.db.execute(select(Resume).where(Resume.candidate_id == candidate_id))
        resumes = resume_result.scalars().all()
        for resume in resumes:
            if storage_service.delete_resume(resume.s3_key):
                s3_deleted += 1
            # Wipe S3 key reference
            resume.s3_key = "[DELETED]"
            resume.parsed_data = None

        # 3. Remove Chroma embeddings
        chroma_deleted = 0
        embedding_ids = [r.embedding_id for r in resumes if r.embedding_id]
        if embedding_ids:
            try:
                import chromadb

                chroma = chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)
                collection = chroma.get_collection("resume_embeddings")
                collection.delete(ids=embedding_ids)
                chroma_deleted = len(embedding_ids)
            except Exception as exc:
                logger.warning(f"Chroma deletion failed for {candidate_id}: {exc}")

        await self.db.commit()
        logger.info(
            f"Right-to-deletion executed: candidate={candidate_id}, " f"S3={s3_deleted}, Chroma={chroma_deleted}"
        )
        return DeleteCandidateResponse(
            candidate_id=candidate_id,
            pii_wiped=True,
            s3_files_deleted=s3_deleted,
            chroma_embeddings_deleted=chroma_deleted,
            message="Candidate PII wiped successfully per GDPR right-to-deletion.",
        )

    # ── Helpers ────────────────────────────────────────────────────────────
    async def _validate_file(self, file: UploadFile) -> tuple[bytes, str]:
        content_type = file.content_type or ""
        # Normalise DOCX content-type if browser sends octet-stream
        if file.filename and file.filename.lower().endswith(".docx"):
            content_type = "application/vnd.openxmlformats-officedocument" ".wordprocessingml.document"
        if content_type not in _ALLOWED_CONTENT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"File type '{content_type}' not allowed. Upload PDF or DOCX only.",
            )
        file_bytes = await file.read()
        if len(file_bytes) > settings.max_upload_size_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds maximum size of {settings.max_upload_size_mb} MB.",
            )
        return file_bytes, content_type

    async def _get_or_create_candidate(
        self, email: str, name: str, consent_source: str
    ) -> tuple[ConsentRecord, Candidate]:
        email_h = hash_email(email)
        result = await self.db.execute(select(Candidate).where(Candidate.email_hash == email_h))
        candidate = result.scalar_one_or_none()
        if candidate:
            return candidate.consent, candidate

        # Create consent record first (FK constraint)
        consent = ConsentRecord(consent_source=consent_source)
        self.db.add(consent)
        await self.db.commit()

        candidate = Candidate(
            name_encrypted=encrypt_pii(name),
            email_encrypted=encrypt_pii(email),
            phone_encrypted=None,
            email_hash=email_h,
            consent_id=consent.id,
        )
        self.db.add(candidate)
        await self.db.commit()
        return consent, candidate

    async def _get_resume_or_404(self, resume_id: uuid.UUID) -> Resume:
        result = await self.db.execute(select(Resume).where(Resume.id == resume_id))
        resume = result.scalar_one_or_none()
        if not resume:
            raise HTTPException(status_code=404, detail=f"Resume {resume_id} not found")
        return resume

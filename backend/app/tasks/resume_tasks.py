"""
Resume Celery Tasks  (§11.2 + §10.2)
──────────────────────────────────────
parse_resume_task   — download from S3, parse, embed, persist to DB + Chroma
bulk_parse_task     — fan-out group of parse_resume_task for a batch upload
"""

import logging
import uuid
from datetime import UTC, datetime

from celery import group

from backend.app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="backend.app.tasks.resume_tasks.parse_resume_task",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    queue="parse_queue",
)
def parse_resume_task(self, resume_id: str, s3_key: str, content_type: str) -> dict:
    """
    Async task: Download resume from S3, run parsing pipeline,
    store structured data in DB and embedding in Chroma.

    Args:
        resume_id:    UUID string of the Resume row.
        s3_key:       S3 object key.
        content_type: MIME type of the file.

    Returns:
        dict with parse results summary.
    """
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from backend.app.config import settings
    from backend.app.core.security import decrypt_pii, encrypt_pii, hash_email
    from backend.app.models.candidate import Candidate, Resume
    from backend.app.services import storage_service
    from backend.app.services.parsing_pipeline import parse_resume_rule_based

    logger.info(f"[parse_resume_task] Starting for resume_id={resume_id}")

    # Sync DB session (Celery workers don't use async)
    engine = create_engine(settings.sync_database_url)

    try:
        with Session(engine) as db:
            # Mark as processing
            result = db.execute(select(Resume).where(Resume.id == uuid.UUID(resume_id)))
            resume = result.scalar_one_or_none()
            if not resume:
                logger.error(f"Resume {resume_id} not found in DB.")
                return {"status": "failed", "error": "Resume not found"}

            resume.parse_status = "processing"
            db.commit()

            # 1. Download file from S3
            file_bytes = storage_service.download_resume(s3_key)

            # 2. Rule-based parse
            parsed = parse_resume_rule_based(file_bytes, content_type)

            # 3. Update candidate PII with real extracted values
            candidate = db.execute(select(Candidate).where(Candidate.id == resume.candidate_id)).scalar_one_or_none()
            if candidate and candidate.name_encrypted:
                existing_name = decrypt_pii(candidate.name_encrypted)
                if existing_name == "Pending Parse":
                    # Update with real parsed name/email
                    candidate.name_encrypted = encrypt_pii(parsed.get("name", "Unknown"))
                    real_email = parsed.get("email")
                    if real_email:
                        candidate.email_encrypted = encrypt_pii(real_email)
                        candidate.email_hash = hash_email(real_email)
                    if parsed.get("phone"):
                        candidate.phone_encrypted = encrypt_pii(parsed["phone"])

            # 4. Generate embedding (reuse Phase-1 embedder)
            from sentence_transformers import SentenceTransformer

            embedder = SentenceTransformer("all-MiniLM-L6-v2")
            embed_text = f"{parsed.get('summary', '')} " f"{' '.join(parsed.get('skills', []))}"
            embedding = embedder.encode(embed_text).tolist()

            # 5. Store embedding in Chroma
            embedding_id = str(uuid.uuid4())
            try:
                import chromadb

                chroma = chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)
                collection = chroma.get_or_create_collection("resume_embeddings")
                collection.add(
                    ids=[embedding_id],
                    embeddings=[embedding],
                    metadatas=[
                        {
                            "resume_id": resume_id,
                            "candidate_id": str(resume.candidate_id),
                            "skills": ", ".join(parsed.get("skills", [])),
                            "experience_years": parsed.get("experience_years", 0),
                        }
                    ],
                )
                logger.info(f"Embedding stored in Chroma: {embedding_id}")
            except Exception as chroma_exc:
                logger.warning(f"Chroma unavailable, skipping embedding: {chroma_exc}")
                embedding_id = None

            # 6. Persist parsed data and update resume row
            resume.parsed_data = parsed
            resume.embedding_id = embedding_id
            resume.parse_status = "done"
            resume.parsed_at = datetime.now(UTC)
            db.commit()

            logger.info(f"[parse_resume_task] Done for resume_id={resume_id}")
            return {
                "status": "done",
                "resume_id": resume_id,
                "name": parsed.get("name"),
                "skills_count": len(parsed.get("skills", [])),
                "experience_years": parsed.get("experience_years", 0),
            }

    except Exception as exc:
        logger.error(f"[parse_resume_task] Failed for {resume_id}: {exc}")
        # Mark resume as failed in DB
        try:
            with Session(engine) as db:
                result = db.execute(select(Resume).where(Resume.id == uuid.UUID(resume_id)))
                resume = result.scalar_one_or_none()
                if resume:
                    resume.parse_status = "failed"
                    db.commit()
        except Exception:
            pass
        raise self.retry(exc=exc)
    finally:
        engine.dispose()


@celery_app.task(
    name="backend.app.tasks.resume_tasks.bulk_parse_task",
    queue="parse_queue",
)
def bulk_parse_task(job_id: str, resume_ids: list[str]) -> dict:
    """
    Fan-out task: dispatches individual parse_resume_task for each resume_id
    in the batch and waits for all to complete.

    Note: This task itself completes quickly (it's just an orchestrator).
    The individual parse tasks run in parallel.
    """
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from backend.app.config import settings
    from backend.app.models.candidate import Resume

    engine = create_engine(settings.sync_database_url)
    tasks = []

    with Session(engine) as db:
        for rid in resume_ids:
            result = db.execute(select(Resume).where(Resume.id == uuid.UUID(rid)))
            resume = result.scalar_one_or_none()
            if resume:
                tasks.append(parse_resume_task.s(rid, resume.s3_key, resume.content_type))
    engine.dispose()

    if tasks:
        # Execute all in parallel
        job = group(tasks)
        result = job.apply_async()
        logger.info(f"[bulk_parse_task] Dispatched {len(tasks)} parse tasks for job_id={job_id}")
        return {"job_id": job_id, "dispatched": len(tasks), "group_id": result.id}
    else:
        return {"job_id": job_id, "dispatched": 0}

"""
Pipeline Celery Tasks  (§10.2 + LangGraph integration)
───────────────────────────────────────────────────────
run_pipeline_task — invokes the Phase-1 LangGraph pipeline for a job,
                    persists result to DB, logs to MLflow.
"""

import logging
import uuid
from datetime import UTC, datetime

from backend.app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="backend.app.tasks.pipeline_tasks.run_pipeline_task",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    queue="pipeline_queue",
    time_limit=1800,  # 30 min hard limit (§12 Scalability NFR)
    soft_time_limit=1500,
)
def run_pipeline_task(self, run_id: str, job_id: str, resume_ids: list[str]) -> dict:
    """
    Execute the full LangGraph recruitment pipeline asynchronously.

    Args:
        run_id:      UUID string of the PipelineRun row.
        job_id:      UUID string of the Job.
        resume_ids:  List of Resume UUIDs to include.

    Returns:
        dict with pipeline summary.
    """
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from backend.app.config import settings
    from backend.app.core.security import decrypt_pii
    from backend.app.models.application import Application, PipelineRun, PipelineStatus
    from backend.app.models.candidate import Candidate, Resume
    from backend.app.models.job import Job
    from graph.orchestrator import build_graph
    from graph.state import initial_state
    from tools.mlflow_tracker import log_recruiter_decision

    engine = create_engine(settings.sync_database_url)
    logger.info(f"[run_pipeline_task] Starting run_id={run_id} job_id={job_id}")

    try:
        with Session(engine) as db:
            # 1. Load PipelineRun and mark running
            run = db.execute(select(PipelineRun).where(PipelineRun.id == uuid.UUID(run_id))).scalar_one_or_none()
            if not run:
                return {"status": "failed", "error": "PipelineRun not found"}

            run.status = PipelineStatus.running
            run.started_at = datetime.now(UTC)
            db.commit()

            # 2. Load job and resumes from DB
            job = db.execute(select(Job).where(Job.id == uuid.UUID(job_id))).scalar_one_or_none()
            if not job:
                run.status = PipelineStatus.failed
                run.error_message = "Job not found"
                db.commit()
                return {"status": "failed", "error": "Job not found"}

            # 3. Build candidate list for Phase-1 pipeline
            candidates_input = []
            for rid in resume_ids:
                resume = db.execute(select(Resume).where(Resume.id == uuid.UUID(rid))).scalar_one_or_none()
                if not resume or not resume.parsed_data:
                    continue
                candidate = db.execute(
                    select(Candidate).where(Candidate.id == resume.candidate_id)
                ).scalar_one_or_none()
                if not candidate or candidate.is_deleted:
                    continue
                parsed = resume.parsed_data
                # Inject decrypted PII into the Phase-1 format
                parsed["name"] = decrypt_pii(candidate.name_encrypted)
                parsed["email"] = decrypt_pii(candidate.email_encrypted)
                candidates_input.append(
                    {
                        "id": str(resume.candidate_id),
                        "resume_id": rid,
                        "resume_text": parsed.get("raw_text", ""),
                        **parsed,
                    }
                )

            if not candidates_input:
                run.status = PipelineStatus.failed
                run.error_message = "No parsed resumes available"
                db.commit()
                return {"status": "failed", "error": "No parsed resumes"}

            # 4. Run LangGraph pipeline (dry-run mode: no HITL pause in async worker)
            thread_id = f"pipeline-{run_id}"
            config = {"configurable": {"thread_id": thread_id}}
            graph_app = build_graph(use_checkpointer=False)

            initial = initial_state(
                job_description=job.raw_jd_text,
                candidates=candidates_input,
            )
            # Inject structured requirements if JD Analyzer already ran
            if job.structured_requirements:
                initial["jd_structured"] = job.structured_requirements

            # Set recruiter_decision to pending (HITL will be submitted via API)
            initial["recruiter_decision"] = "pending"

            final_state = graph_app.invoke(initial, config=config)

            # 5. Persist final state to PipelineRun
            run.status = PipelineStatus.completed
            run.completed_at = datetime.now(UTC)
            run.result = {
                "final_ranking": final_state.get("final_ranking", []),
                "fairness_report": final_state.get("fairness_report", {}),
                "jd_structured": final_state.get("jd_structured", {}),
                "errors": final_state.get("errors", []),
                "total_candidates": len(candidates_input),
                "shortlisted": len(final_state.get("above_threshold", [])),
            }

            # 6. Create Application rows for ranked candidates
            for ranked_cand in final_state.get("final_ranking", []):
                cand_id_str = ranked_cand.get("id")
                if not cand_id_str:
                    continue
                application = Application(
                    candidate_id=uuid.UUID(cand_id_str),
                    job_id=uuid.UUID(job_id),
                    pipeline_run_id=uuid.UUID(run_id),
                    stage="shortlisted",
                    similarity_score=ranked_cand.get("similarity_score"),
                    adjusted_score=ranked_cand.get("adjusted_score"),
                    interview_score=ranked_cand.get("interview_score"),
                    final_score=ranked_cand.get("final_score"),
                    rank=ranked_cand.get("rank"),
                    recruiter_decision="pending",
                )
                db.add(application)

            # 7. Update JD structured requirements if newly extracted
            if final_state.get("jd_structured") and not job.structured_requirements:
                job.structured_requirements = final_state["jd_structured"]

            db.commit()

            # 8. Log to MLflow (non-blocking)
            try:
                log_recruiter_decision(dict(final_state))
            except Exception as mlflow_exc:
                logger.warning(f"MLflow logging failed (non-fatal): {mlflow_exc}")

            logger.info(
                f"[run_pipeline_task] Completed run_id={run_id}, " f"ranked={len(final_state.get('final_ranking', []))}"
            )
            return {
                "status": "completed",
                "run_id": run_id,
                "total_candidates": len(candidates_input),
                "ranked": len(final_state.get("final_ranking", [])),
            }

    except Exception as exc:
        logger.error(f"[run_pipeline_task] Failed run_id={run_id}: {exc}")
        try:
            with Session(engine) as db:
                run = db.execute(select(PipelineRun).where(PipelineRun.id == uuid.UUID(run_id))).scalar_one_or_none()
                if run:
                    from backend.app.models.application import PipelineStatus

                    run.status = PipelineStatus.failed
                    run.error_message = str(exc)
                    run.completed_at = datetime.now(UTC)
                    db.commit()
        except Exception:
            pass
        raise self.retry(exc=exc)
    finally:
        engine.dispose()

"""
Pipeline Router
────────────────
Endpoints:
  POST   /api/v1/pipeline/run          — trigger pipeline for a job
  GET    /api/v1/pipeline/{run_id}     — get run status + result
  POST   /api/v1/pipeline/{run_id}/decision — submit HITL recruiter decision
  WS     /ws/pipeline/{run_id}        — live status stream (WebSocket)
"""

import asyncio
import uuid
from datetime import UTC, datetime

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.rbac import require_min_role, require_roles
from backend.app.dependencies import DBSession
from backend.app.models.application import Application, PipelineRun, PipelineStatus
from backend.app.models.user import User, UserRole
from backend.app.schemas.pipeline import (
    PipelineRunResponse,
    PipelineStatusResponse,
    PipelineTriggerRequest,
    RecruiterDecisionRequest,
)

router = APIRouter(tags=["Pipeline"])


@router.post(
    "/api/v1/pipeline/run",
    response_model=PipelineRunResponse,
    status_code=202,
    summary="Trigger pipeline run for a job",
)
async def trigger_pipeline(
    body: PipelineTriggerRequest,
    db: DBSession,
    current_user: User = Depends(require_min_role(UserRole.recruiter)),
) -> PipelineRunResponse:
    """
    Queues an async LangGraph pipeline run via Celery.
    Returns immediately with run_id for status polling.
    """
    from backend.app.tasks.pipeline_tasks import run_pipeline_task

    # Resolve resume_ids: use provided list or all parsed resumes for the job
    if not body.resume_ids:
        from backend.app.models.candidate import Resume

        result = await db.execute(select(Resume).where(Resume.parse_status == "done"))
        resumes = result.scalars().all()
        resume_ids = [r.id for r in resumes]
    else:
        resume_ids = body.resume_ids

    if not resume_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No parsed resumes available for this job. Upload and wait for parsing to complete.",
        )

    # Create PipelineRun row
    run = PipelineRun(
        job_id=body.job_id,
        status=PipelineStatus.queued,
        triggered_by=current_user.id,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    # Dispatch Celery task
    task = run_pipeline_task.delay(
        str(run.id),
        str(body.job_id),
        [str(rid) for rid in resume_ids],
    )
    run.celery_task_id = task.id
    await db.commit()
    await db.refresh(run)

    return PipelineRunResponse(
        run_id=run.id,
        job_id=body.job_id,
        celery_task_id=task.id,
        status=run.status.value,
        created_at=run.created_at,
    )


@router.get(
    "/api/v1/pipeline/{run_id}",
    response_model=PipelineStatusResponse,
    summary="Get pipeline run status",
)
async def get_pipeline_status(
    run_id: uuid.UUID,
    db: DBSession,
    _: User = Depends(require_min_role(UserRole.viewer)),
) -> PipelineStatusResponse:
    result = await db.execute(select(PipelineRun).where(PipelineRun.id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail=f"Pipeline run {run_id} not found")
    return PipelineStatusResponse.model_validate(run)


@router.post(
    "/api/v1/pipeline/{run_id}/decision",
    status_code=200,
    summary="Submit recruiter HITL decision",
)
async def submit_decision(
    run_id: uuid.UUID,
    body: RecruiterDecisionRequest,
    db: DBSession,
    _: User = Depends(require_roles(UserRole.recruiter, UserRole.admin)),
) -> dict:
    """
    Submit the recruiter's hire/no_hire decision for a completed pipeline run.
    Updates all Application rows for this run.
    """
    if body.decision not in ("hire", "no_hire"):
        raise HTTPException(status_code=422, detail="Decision must be 'hire' or 'no_hire'")
    result = await db.execute(select(PipelineRun).where(PipelineRun.id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    if run.status != PipelineStatus.completed:
        raise HTTPException(
            status_code=409,
            detail=f"Pipeline must be completed to submit decision. Current: {run.status}",
        )

    # Update all applications in this run
    apps_result = await db.execute(select(Application).where(Application.pipeline_run_id == run_id))
    apps = apps_result.scalars().all()
    for app in apps:
        app.recruiter_decision = body.decision
        app.stage = "hired" if body.decision == "hire" else "rejected"
        if body.notes:
            app.decision_notes = body.notes

    # Store decision in run result
    if run.result:
        run.result = {**run.result, "recruiter_decision": body.decision}

    await db.commit()
    return {
        "run_id": str(run_id),
        "decision": body.decision,
        "applications_updated": len(apps),
        "message": f"Decision '{body.decision}' recorded for {len(apps)} applications.",
    }


# ── WebSocket: Live Pipeline Status ──────────────────────────────────────────


@router.websocket("/ws/pipeline/{run_id}")
async def pipeline_ws(run_id: uuid.UUID, websocket: WebSocket, db: AsyncSession = Depends(lambda: None)):
    """
    WebSocket endpoint for real-time pipeline status updates.
    Polls DB every 2 seconds and pushes status changes to the client.
    Closes when pipeline reaches terminal state (completed/failed/cancelled).
    """
    await websocket.accept()
    from backend.app.db.session import async_session

    last_status = None
    try:
        while True:
            async with async_session() as session:
                result = await session.execute(select(PipelineRun).where(PipelineRun.id == run_id))
                run = result.scalar_one_or_none()

            if not run:
                await websocket.send_json({"error": f"Run {run_id} not found"})
                break

            current_status = run.status.value
            if current_status != last_status:
                payload = {
                    "run_id": str(run_id),
                    "status": current_status,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
                if run.result:
                    payload["summary"] = {
                        "ranked": len(run.result.get("final_ranking", [])),
                        "shortlisted": run.result.get("shortlisted", 0),
                    }
                if run.error_message:
                    payload["error"] = run.error_message
                await websocket.send_json(payload)
                last_status = current_status

            # Terminal states
            if current_status in ("completed", "failed", "cancelled"):
                break

            await asyncio.sleep(2)  # Poll every 2 seconds

    except WebSocketDisconnect:
        pass
    finally:
        await websocket.close()

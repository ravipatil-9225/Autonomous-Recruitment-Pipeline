"""
Pipeline Schemas  (Pydantic v2)
────────────────────────────────
Request / response models for pipeline trigger and status endpoints.
"""
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class PipelineTriggerRequest(BaseModel):
    """POST /api/v1/pipeline/run — trigger a pipeline run for a job."""
    job_id: uuid.UUID
    resume_ids: list[uuid.UUID] = []
    # If empty, all resumes associated with the job are used


class PipelineRunResponse(BaseModel):
    """Returned when a pipeline run is queued."""
    run_id: uuid.UUID
    job_id: uuid.UUID
    celery_task_id: str | None
    status: str
    created_at: datetime
    message: str = "Pipeline queued. Poll /api/v1/pipeline/{run_id} for status."


class PipelineStatusResponse(BaseModel):
    """Full pipeline run details including result."""
    id: uuid.UUID
    job_id: uuid.UUID
    status: str
    error_message: str | None = None
    result: dict[str, Any] | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime

    @property
    def run_id(self) -> uuid.UUID:
        return self.id

    model_config = {"from_attributes": True}



class RecruiterDecisionRequest(BaseModel):
    """POST /api/v1/pipeline/{run_id}/decision — submit HITL decision."""
    decision: str  # "hire" | "no_hire"
    notes: str | None = None

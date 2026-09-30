"""
ORM Models: PipelineRun & Application
───────────────────────────────────────
PipelineRun: one LangGraph execution per (job, batch of resumes).
Application: links a candidate to a job + their pipeline outcome.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, JSON, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base


class PipelineStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class ApplicationStage(str, enum.Enum):
    applied = "applied"
    screening = "screening"
    shortlisted = "shortlisted"
    interviewing = "interviewing"
    offered = "offered"
    hired = "hired"
    rejected = "rejected"
    withdrawn = "withdrawn"


class PipelineRun(Base):
    """
    Represents a single async LangGraph pipeline execution.
    Triggered via Celery; status updated by the worker.
    """

    __tablename__ = "pipeline_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Celery task identifier for status polling
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    status: Mapped[PipelineStatus] = mapped_column(
        Enum(PipelineStatus, name="pipeline_status"),
        nullable=False,
        default=PipelineStatus.queued,
    )

    # Full LangGraph final state stored as JSON/JSONB
    result: Mapped[dict | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )

    # Error message if failed
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    triggered_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    job: Mapped["Job"] = relationship("Job", back_populates="pipeline_runs", lazy="select")  # noqa: F821
    applications: Mapped[list["Application"]] = relationship(
        "Application", back_populates="pipeline_run", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<PipelineRun id={self.id} job_id={self.job_id} status={self.status}>"


class Application(Base):
    """
    Links a Candidate to a Job through a PipelineRun.
    Captures the scoring outcome and recruiter decision.
    """

    __tablename__ = "applications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    pipeline_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pipeline_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    resume_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("resumes.id", ondelete="SET NULL"),
        nullable=True,
    )

    stage: Mapped[ApplicationStage] = mapped_column(
        Enum(ApplicationStage, name="application_stage"),
        nullable=False,
        default=ApplicationStage.applied,
    )

    # Scoring outputs from the pipeline
    similarity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    adjusted_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    interview_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    final_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    rank: Mapped[int | None] = mapped_column(nullable=True)

    # Recruiter HITL decision
    recruiter_decision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    decision_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    candidate: Mapped["Candidate"] = relationship(  # noqa: F821
        "Candidate", back_populates="applications", lazy="select"
    )
    job: Mapped["Job"] = relationship("Job", lazy="select")  # noqa: F821
    pipeline_run: Mapped["PipelineRun"] = relationship(
        "PipelineRun", back_populates="applications", lazy="select"
    )

    def __repr__(self) -> str:
        return (
            f"<Application id={self.id} candidate={self.candidate_id} "
            f"job={self.job_id} stage={self.stage}>"
        )

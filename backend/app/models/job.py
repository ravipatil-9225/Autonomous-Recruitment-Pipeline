"""
ORM Model: Job / Requisition  (§11.1)
───────────────────────────────────────
Stores the raw JD text and the structured requirements extracted
by the JD Analyzer agent.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base


class JobStatus(str, enum.Enum):
    draft = "draft"
    open = "open"
    closed = "closed"
    archived = "archived"


class Job(Base):
    """A job requisition / posting."""

    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    department: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Raw JD text from recruiter dashboard (§13)
    raw_jd_text: Mapped[str] = mapped_column(Text, nullable=False)

    # Structured requirements extracted by JD Analyzer agent (JSON/JSONB variant)
    structured_requirements: Mapped[dict | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )

    # Chroma collection document ID for the JD embedding
    jd_embedding_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status"), nullable=False, default=JobStatus.draft
    )

    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    created_by_user: Mapped["User"] = relationship("User", back_populates="jobs", lazy="select")  # noqa: F821
    pipeline_runs: Mapped[list["PipelineRun"]] = relationship(  # noqa: F821
        "PipelineRun", back_populates="job", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Job id={self.id} title={self.title!r} status={self.status}>"

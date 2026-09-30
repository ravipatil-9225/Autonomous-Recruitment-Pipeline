"""
ORM Model: ConsentRecord  (§12 Privacy/GDPR)
──────────────────────────────────────────────
Tracks candidate consent and supports GDPR right-to-deletion.
Every candidate must have a consent record before PII is stored.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base


class ConsentRecord(Base):
    """GDPR consent record for a candidate."""

    __tablename__ = "consent_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Purpose / scope of data processing
    purpose: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        default="Recruitment processing and candidate evaluation",
    )

    # Consent lifecycle timestamps
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deletion_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Source of consent (email, web form, API, etc.)
    consent_source: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Notes for audit trail
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationship back to candidate
    candidate: Mapped["Candidate"] = relationship(  # noqa: F821
        "Candidate", back_populates="consent", uselist=False, lazy="select"
    )

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None and self.deleted_at is None

    @property
    def deletion_pending(self) -> bool:
        return self.deletion_requested_at is not None and self.deleted_at is None

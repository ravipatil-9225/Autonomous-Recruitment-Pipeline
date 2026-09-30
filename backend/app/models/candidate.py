"""
ORM Models: Candidate & Resume  (§11.2 + §12 PII)
────────────────────────────────────────────────────
PII fields (name, email, phone) are stored AES-256-GCM encrypted.
Decryption only happens in the service layer — never in raw DB queries.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base


class Candidate(Base):
    """
    A job candidate. PII columns are stored encrypted.
    Use CandidateService to read/write — never access encrypted columns directly.
    """

    __tablename__ = "candidates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # ── Encrypted PII (AES-256-GCM, base64 ciphertext) ─────────────────────
    name_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    email_encrypted: Mapped[str] = mapped_column(Text, nullable=False, index=False)
    phone_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Non-PII: email hash for deduplication lookups (SHA-256 of lower email)
    email_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)

    # ── GDPR consent ────────────────────────────────────────────────────────
    consent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("consent_records.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Soft-delete flag (for right-to-deletion execution)
    is_deleted: Mapped[bool] = mapped_column(default=False, nullable=False)

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
    consent: Mapped["ConsentRecord"] = relationship(  # noqa: F821
        "ConsentRecord", back_populates="candidate", lazy="select"
    )
    resumes: Mapped[list["Resume"]] = relationship(
        "Resume", back_populates="candidate", lazy="select"
    )
    applications: Mapped[list["Application"]] = relationship(  # noqa: F821
        "Application", back_populates="candidate", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Candidate id={self.id} email_hash={self.email_hash[:8]}…>"


class Resume(Base):
    """
    A single uploaded resume file associated with a candidate.
    Binary file lives in S3/MinIO; this row tracks metadata + parsed output.
    """

    __tablename__ = "resumes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # S3/MinIO object key (bucket is configured globally)
    s3_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)

    # Parsing pipeline output (JSON blob — structured profile)
    parsed_data: Mapped[dict | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )

    # Chroma vector DB document ID for the resume embedding
    embedding_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Celery task ID for async parse status tracking
    parse_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    parse_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending"
    )  # pending | processing | done | failed

    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    parsed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationship
    candidate: Mapped["Candidate"] = relationship(
        "Candidate", back_populates="resumes", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Resume id={self.id} file={self.original_filename!r} status={self.parse_status}>"

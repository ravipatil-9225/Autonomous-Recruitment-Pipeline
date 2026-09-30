"""Initial schema — all Phase 2 tables

Revision ID: 001
Revises: (none)
Create Date: 2026-09-09
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── ENUM types ────────────────────────────────────────────────────────
    op.execute("CREATE TYPE user_role AS ENUM ('admin', 'recruiter', 'hiring_manager', 'viewer')")
    op.execute("CREATE TYPE job_status AS ENUM ('draft', 'open', 'closed', 'archived')")
    op.execute("CREATE TYPE pipeline_status AS ENUM ('queued', 'running', 'completed', 'failed', 'cancelled')")
    op.execute(
        "CREATE TYPE application_stage AS ENUM ('applied', 'screening', 'shortlisted', 'interviewing', 'offered', 'hired', 'rejected', 'withdrawn')"
    )

    # ── consent_records ───────────────────────────────────────────────────
    op.create_table(
        "consent_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("purpose", sa.String(512), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deletion_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consent_source", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
    )

    # ── users ─────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("role", sa.Enum("admin", "recruiter", "hiring_manager", "viewer", name="user_role"), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ── candidates ────────────────────────────────────────────────────────
    op.create_table(
        "candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name_encrypted", sa.Text, nullable=False),
        sa.Column("email_encrypted", sa.Text, nullable=False),
        sa.Column("phone_encrypted", sa.Text, nullable=True),
        sa.Column("email_hash", sa.String(64), nullable=False, unique=True),
        sa.Column(
            "consent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("consent_records.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_candidates_email_hash", "candidates", ["email_hash"], unique=True)

    # ── jobs ──────────────────────────────────────────────────────────────
    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("department", sa.String(255), nullable=True),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("raw_jd_text", sa.Text, nullable=False),
        sa.Column("structured_requirements", postgresql.JSONB, nullable=True),
        sa.Column("jd_embedding_id", sa.String(255), nullable=True),
        sa.Column(
            "status",
            sa.Enum("draft", "open", "closed", "archived", name="job_status"),
            nullable=False,
            server_default="draft",
        ),
        sa.Column(
            "created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── resumes ───────────────────────────────────────────────────────────
    op.create_table(
        "resumes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "candidate_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("s3_key", sa.String(1024), nullable=False),
        sa.Column("original_filename", sa.String(512), nullable=False),
        sa.Column("file_size_bytes", sa.Integer, nullable=False),
        sa.Column("content_type", sa.String(128), nullable=False),
        sa.Column("parsed_data", postgresql.JSONB, nullable=True),
        sa.Column("embedding_id", sa.String(255), nullable=True),
        sa.Column("parse_task_id", sa.String(255), nullable=True),
        sa.Column("parse_status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("parsed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_resumes_candidate_id", "resumes", ["candidate_id"])

    # ── pipeline_runs ──────────────────────────────────────────────────────
    op.create_table(
        "pipeline_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("celery_task_id", sa.String(255), nullable=True),
        sa.Column(
            "status",
            sa.Enum("queued", "running", "completed", "failed", "cancelled", name="pipeline_status"),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("result", postgresql.JSONB, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column(
            "triggered_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_pipeline_runs_job_id", "pipeline_runs", ["job_id"])
    op.create_index("ix_pipeline_runs_celery_task_id", "pipeline_runs", ["celery_task_id"])

    # ── applications ──────────────────────────────────────────────────────
    op.create_table(
        "applications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "candidate_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "pipeline_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pipeline_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "resume_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("resumes.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column(
            "stage",
            sa.Enum(
                "applied",
                "screening",
                "shortlisted",
                "interviewing",
                "offered",
                "hired",
                "rejected",
                "withdrawn",
                name="application_stage",
            ),
            nullable=False,
            server_default="applied",
        ),
        sa.Column("similarity_score", sa.Float, nullable=True),
        sa.Column("adjusted_score", sa.Float, nullable=True),
        sa.Column("interview_score", sa.Float, nullable=True),
        sa.Column("final_score", sa.Float, nullable=True),
        sa.Column("rank", sa.Integer, nullable=True),
        sa.Column("recruiter_decision", sa.String(32), nullable=True),
        sa.Column("decision_notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_applications_candidate_id", "applications", ["candidate_id"])
    op.create_index("ix_applications_job_id", "applications", ["job_id"])


def downgrade() -> None:
    op.drop_table("applications")
    op.drop_table("pipeline_runs")
    op.drop_table("resumes")
    op.drop_table("jobs")
    op.drop_table("candidates")
    op.drop_table("users")
    op.drop_table("consent_records")
    op.execute("DROP TYPE IF EXISTS application_stage")
    op.execute("DROP TYPE IF EXISTS pipeline_status")
    op.execute("DROP TYPE IF EXISTS job_status")
    op.execute("DROP TYPE IF EXISTS user_role")

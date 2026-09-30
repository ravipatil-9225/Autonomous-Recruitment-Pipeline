"""
Celery Application  (§10.2 Async Task Queue)
──────────────────────────────────────────────
Redis is used as both broker (task dispatch) and result backend (task status).
Two queues:
  • parse_queue   — resume parsing tasks
  • pipeline_queue — LangGraph pipeline runs

Beat schedule stub is included for future periodic jobs (e.g., retraining).
"""

from celery import Celery

from backend.app.config import settings

celery_app = Celery(
    "arp",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "backend.app.tasks.resume_tasks",
        "backend.app.tasks.pipeline_tasks",
    ],
)

# ── Configuration ─────────────────────────────────────────────────────────────
celery_app.conf.update(
    # Serialisation
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # Timezone
    timezone="UTC",
    enable_utc=True,
    # Result expiry (24 h)
    result_expires=86400,
    # Task routing
    task_routes={
        "backend.app.tasks.resume_tasks.*": {"queue": "parse_queue"},
        "backend.app.tasks.pipeline_tasks.*": {"queue": "pipeline_queue"},
    },
    # Retry defaults
    task_acks_late=True,  # Ack only after success (safer for long tasks)
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,  # One task at a time per worker (for long tasks)
    # Beat schedule (stub — extend in Phase 3)
    beat_schedule={},
)

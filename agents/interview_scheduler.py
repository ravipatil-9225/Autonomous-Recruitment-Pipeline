"""
Agent 4 – Interview Scheduler
──────────────────────────────
Books interview slots for above-threshold candidates via the
Calendar API tool and triggers notification emails.
"""

import logging

from graph.state import RecruitmentState
from tools.calendar_tool import book_interview_slot

logger = logging.getLogger(__name__)


def interview_scheduler_node(state: RecruitmentState) -> dict:
    """
    LangGraph node: Schedule interviews for shortlisted candidates.

    Reads : state["above_threshold"]
    Writes: state["scheduled_interviews"]
    """
    logger.info("▶ Interview Scheduler: Booking interview slots...")
    candidates = state.get("above_threshold", [])
    errors = list(state.get("errors", []))
    scheduled = []

    for cand in candidates:
        cid = cand.get("id", "unknown")
        name = cand.get("name", cid)
        email = cand.get("email", "unknown@example.com")
        try:
            booking = book_interview_slot(candidate_id=cid, candidate_name=name, email=email)
            scheduled.append({**cand, "interview_slot": booking})
            logger.info(f"  ✔ Booked slot for {name}: {booking['slot']}")
        except Exception as exc:
            logger.error(f"  ✘ Scheduling failed for {name}: {exc}")
            errors.append(f"interview_scheduler[{cid}]: {exc}")

    logger.info(f"  ✔ Total interviews scheduled: {len(scheduled)}")
    return {"scheduled_interviews": scheduled, "errors": errors}

"""
Calendar API Tool (Mock)
─────────────────────────
In production, replace with Google Calendar / Calendly / Outlook API calls.
Currently returns realistic mock slot booking confirmations.
"""
import uuid
import logging
from datetime import datetime, timedelta
import random

logger = logging.getLogger(__name__)

# Mock available time slots (weekday business hours)
_SLOT_POOL = [
    "Mon 09:00–09:45",
    "Mon 14:00–14:45",
    "Tue 10:00–10:45",
    "Tue 15:00–15:45",
    "Wed 09:30–10:15",
    "Wed 13:00–13:45",
    "Thu 11:00–11:45",
    "Thu 16:00–16:45",
    "Fri 09:00–09:45",
    "Fri 11:30–12:15",
]


def book_interview_slot(
    candidate_id: str,
    candidate_name: str,
    email: str,
    failure_rate: float = 0.05,
) -> dict:
    """
    Books an interview slot for a candidate.

    Args:
        candidate_id: Unique identifier of the candidate.
        candidate_name: Full name of the candidate.
        email: Candidate email for notification.
        failure_rate: Probability [0-1] of simulated API failure (default 5%).
                      Set to 0.0 in tests to guarantee success.

    Returns:
        dict with booking confirmation details.

    Raises:
        RuntimeError: If booking fails (simulated by failure_rate).
    """
    # Simulate occasional failure for retry demonstration
    if random.random() < failure_rate:
        raise RuntimeError(f"Calendar API temporarily unavailable for {candidate_name}.")

    slot = random.choice(_SLOT_POOL)
    booking_id = str(uuid.uuid4())[:8].upper()

    booking = {
        "booking_id": booking_id,
        "candidate_id": candidate_id,
        "candidate_name": candidate_name,
        "email": email,
        "slot": slot,
        "meeting_link": f"https://meet.example.com/interview/{booking_id}",
        "status": "confirmed",
    }

    logger.info(f"  📅 Calendar booking confirmed: {booking_id} | {candidate_name} | {slot}")
    logger.info(f"  📧 Invitation sent to {email}")
    return booking

"""
Tests: Shared Pipeline State
"""
import pytest
from graph.state import RecruitmentState, initial_state


def test_initial_state_keys():
    """All required state keys must exist after initialization."""
    state = initial_state(job_description="Test JD", candidates=[])
    expected_keys = [
        "job_description", "jd_structured", "jd_embedding",
        "candidates", "parsed_candidates", "scored_candidates",
        "above_threshold", "below_threshold", "scheduled_interviews",
        "interview_scores", "final_ranking", "fairness_report",
        "recruiter_decision", "retries", "errors",
    ]
    for key in expected_keys:
        assert key in state, f"Missing key: {key}"


def test_initial_state_defaults():
    """Default values must be correct types."""
    state = initial_state("JD text", [{"id": "C1", "resume_text": "..."}])
    assert state["job_description"] == "JD text"
    assert state["recruiter_decision"] == "pending"
    assert state["retries"] == 0
    assert isinstance(state["errors"], list)
    assert len(state["candidates"]) == 1
    assert state["jd_embedding"] == []

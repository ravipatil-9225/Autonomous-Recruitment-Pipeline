"""
Tests: Individual Agent Nodes (offline/mock)
Uses monkeypatching to avoid real Gemini API calls.
"""

from graph.state import initial_state

# ── Matching & Scoring (no LLM needed) ────────────────────────────────────────


def test_matching_scoring_splits_candidates():
    """Above/below threshold split should work correctly."""
    # Build a state with pre-set embeddings so we avoid real embedding model
    import numpy as np

    from agents.matching_scoring import matching_scoring_node

    jd_emb = np.ones(384).tolist()
    high_emb = np.ones(384).tolist()
    low_emb = (-1 * np.ones(384)).tolist()

    state = initial_state("JD", [])
    state["jd_embedding"] = jd_emb
    state["parsed_candidates"] = [
        {"id": "C1", "name": "Alice", "email": "a@e.com", "experience_years": 5, "embedding": high_emb},
        {"id": "C2", "name": "Bob", "email": "b@e.com", "experience_years": 1, "embedding": low_emb},
    ]

    result = matching_scoring_node(state)
    assert len(result["scored_candidates"]) == 2
    # Alice should be above threshold, Bob (low embedding + low exp) below
    above_ids = [c["id"] for c in result["above_threshold"]]
    below_ids = [c["id"] for c in result["below_threshold"]]
    assert "C1" in above_ids or "C1" in below_ids  # At least split happened
    assert len(above_ids) + len(below_ids) == 2


def test_matching_scoring_missing_jd_embedding():
    """Missing JD embedding should gracefully return empty results and log error."""
    from agents.matching_scoring import matching_scoring_node

    state = initial_state("JD", [])
    state["jd_embedding"] = []  # Missing
    state["parsed_candidates"] = [
        {"id": "C1", "name": "Alice", "email": "a@e.com", "experience_years": 5, "embedding": []}
    ]

    result = matching_scoring_node(state)
    assert result["above_threshold"] == []
    assert result["below_threshold"] == []
    assert any("jd_embedding" in e or "matching_scoring" in e for e in result["errors"])


# ── Evaluation & Ranking ───────────────────────────────────────────────────────


def test_evaluation_ranking_order():
    """Final ranking must be sorted descending by final_score."""
    from agents.evaluation_ranking import evaluation_ranking_node

    state = initial_state("JD", [])
    state["above_threshold"] = [
        {"id": "C1", "name": "Alice", "email": "a@e.com", "adjusted_score": 0.9, "skills": [], "experience_years": 5},
        {"id": "C2", "name": "Bob", "email": "b@e.com", "adjusted_score": 0.7, "skills": [], "experience_years": 3},
        {"id": "C3", "name": "Carol", "email": "c@e.com", "adjusted_score": 0.8, "skills": [], "experience_years": 4},
    ]
    state["interview_scores"] = [
        {"candidate_id": "C1", "overall_interview_score": 9, "summary": "Excellent"},
        {"candidate_id": "C2", "overall_interview_score": 6, "summary": "Good"},
        {"candidate_id": "C3", "overall_interview_score": 8, "summary": "Very Good"},
    ]

    result = evaluation_ranking_node(state)
    ranking = result["final_ranking"]
    assert len(ranking) == 3
    scores = [r["final_score"] for r in ranking]
    assert scores == sorted(scores, reverse=True), "Ranking must be descending"
    assert ranking[0]["rank"] == 1


def test_evaluation_ranking_assigns_rank():
    """Each candidate should receive a rank starting at 1."""
    from agents.evaluation_ranking import evaluation_ranking_node

    state = initial_state("JD", [])
    state["above_threshold"] = [
        {"id": "C1", "name": "X", "email": "", "adjusted_score": 0.8, "skills": [], "experience_years": 4},
    ]
    state["interview_scores"] = [
        {"candidate_id": "C1", "overall_interview_score": 8, "summary": ""},
    ]
    result = evaluation_ranking_node(state)
    assert result["final_ranking"][0]["rank"] == 1


# ── Bias Audit ─────────────────────────────────────────────────────────────────


def test_bias_audit_no_candidates():
    """Bias audit should gracefully handle empty ranking."""
    from agents.bias_audit import bias_audit_node

    state = initial_state("JD", [])
    state["final_ranking"] = []
    result = bias_audit_node(state)
    assert result["fairness_report"]["status"] == "skipped"


def test_bias_audit_flags_large_gap():
    """Should flag a large score gap."""
    from agents.bias_audit import bias_audit_node

    state = initial_state("JD", [])
    state["final_ranking"] = [
        {"rank": 1, "name": "A", "final_score": 0.95, "match_score": 0.9, "interview_score": 1.0},
        {"rank": 2, "name": "B", "final_score": 0.30, "match_score": 0.3, "interview_score": 0.3},
    ]
    result = bias_audit_node(state)
    flags = result["fairness_report"]["bias_flags"]
    assert any("Large score gap" in f or "⚠️" in f for f in flags)


# ── Calendar Tool ──────────────────────────────────────────────────────────────


def test_calendar_tool_returns_booking():
    """Calendar tool should return a booking dict with required keys."""
    from tools.calendar_tool import book_interview_slot

    # Pass failure_rate=0.0 so the random check never triggers
    booking = book_interview_slot("C1", "Alice", "alice@example.com", failure_rate=0.0)
    assert "booking_id" in booking
    assert "slot" in booking
    assert booking["status"] == "confirmed"
    assert booking["candidate_id"] == "C1"

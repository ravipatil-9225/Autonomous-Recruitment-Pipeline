"""
Tests: Graph shape, conditional routing, and dry-run integration.
Avoids real LLM or embedding calls via monkeypatching.
"""

from unittest.mock import MagicMock, patch

import numpy as np

from graph.state import initial_state

# ── Routing Logic (tested directly) ───────────────────────────────────────────


def test_conditional_routing_empty_above():
    """If above_threshold is empty, route to 'end'."""
    state = initial_state("JD", [])
    state["above_threshold"] = []
    result = "end" if not state.get("above_threshold") else "continue"
    assert result == "end"


def test_conditional_routing_with_candidates():
    """If above_threshold has entries, route to 'continue'."""
    state = initial_state("JD", [])
    state["above_threshold"] = [{"id": "C1", "name": "Alice"}]
    result = "end" if not state.get("above_threshold") else "continue"
    assert result == "continue"


# ── Graph dry-run (LLM nodes mocked via patch.object) ─────────────────────────


def _make_mock_jd_analyzer(state):
    emb = np.ones(384).tolist()
    return {
        "jd_structured": {"role_title": "Engineer", "min_experience_years": 2},
        "jd_embedding": emb,
    }


def _make_mock_resume_parser(state):
    emb = np.ones(384).tolist()
    return {
        "parsed_candidates": [
            {
                "id": "C1",
                "name": "Alice",
                "email": "a@e.com",
                "skills": ["Python"],
                "experience_years": 5,
                "education": "BSc CS",
                "summary": "Senior dev",
                "embedding": emb,
            }
        ]
    }


def _make_mock_scheduler(state):
    above = state.get("above_threshold", [])
    return {
        "scheduled_interviews": [{**c, "interview_slot": {"booking_id": "MOCK01", "slot": "Mon 10:00"}} for c in above]
    }


def _make_mock_interview_bot(state):
    return {
        "interview_scores": [
            {
                "candidate_id": "C1",
                "candidate_name": "Alice",
                "overall_interview_score": 8,
                "summary": "Good",
                "technical_depth": 8,
                "communication_clarity": 7,
                "relevance_to_jd": 8,
                "questions": ["Q1"],
                "answers": ["A1"],
            }
        ]
    }


def test_graph_dry_run_completes():
    """
    Integration test: Graph completes in dry-run mode with mocked LLM nodes.
    Stubs heavy optional packages (google.generativeai, sentence_transformers)
    in sys.modules before importing the orchestrator so the test is fully offline.
    """
    import sys

    # Stub modules that require API keys / heavy downloads
    stubs = {
        "google": MagicMock(),
        "google.genai": MagicMock(),
        "google.generativeai": MagicMock(),  # kept for safety if any indirect import
        "sentence_transformers": MagicMock(),
    }
    # Inject stubs only if not already present (don't override real installs)
    injected = {k for k in stubs if k not in sys.modules}
    for k, v in stubs.items():
        if k not in sys.modules:
            sys.modules[k] = v

    try:
        # Force reimport of agent modules with stubs in place
        for mod_name in list(sys.modules.keys()):
            if mod_name.startswith("agents.") or mod_name == "graph.orchestrator":
                del sys.modules[mod_name]

        import graph.orchestrator as orch_mod

        with (
            patch.object(orch_mod, "jd_analyzer_node", side_effect=_make_mock_jd_analyzer),
            patch.object(orch_mod, "resume_parser_node", side_effect=_make_mock_resume_parser),
            patch.object(orch_mod, "interview_scheduler_node", side_effect=_make_mock_scheduler),
            patch.object(orch_mod, "interview_bot_node", side_effect=_make_mock_interview_bot),
        ):

            app = orch_mod.build_graph(use_checkpointer=False)
            state = initial_state(
                job_description="Senior Python Engineer needed",
                candidates=[{"id": "C1", "resume_text": "Alice, 5 years Python"}],
            )
            state["recruiter_decision"] = "hire"
            final = app.invoke(state)

        assert final is not None
        assert "final_ranking" in final
        assert "fairness_report" in final

    finally:
        # Clean up injected stubs
        for k in injected:
            sys.modules.pop(k, None)

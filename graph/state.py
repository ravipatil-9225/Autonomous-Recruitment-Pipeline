"""
Shared Pipeline State for the AI Recruitment LangGraph.

All agents read from and write to this TypedDict, which is
the single source of truth carried across every graph node.
"""
from typing import TypedDict, Optional


class RecruitmentState(TypedDict):
    # ── Input ──────────────────────────────────────────────────────────────
    job_description: str                  # Raw JD text from recruiter dashboard

    # ── JD Analyzer (Node 1) ───────────────────────────────────────────────
    jd_structured: dict                   # Extracted skills, role, requirements
    jd_embedding: list                    # Vector embedding of the JD

    # ── Resume Parser (Node 2) ─────────────────────────────────────────────
    candidates: list                      # Raw resume data (list of dicts)
    parsed_candidates: list               # Structured: name, skills, exp, edu

    # ── Matching & Scoring (Node 3) ────────────────────────────────────────
    scored_candidates: list               # Candidates with similarity scores
    above_threshold: list                 # Candidates who pass the threshold
    below_threshold: list                 # Candidates who fail the threshold

    # ── Interview Scheduler (Node 4) ───────────────────────────────────────
    scheduled_interviews: list            # Booked slots per candidate

    # ── AI Interview Bot (Node 5) ──────────────────────────────────────────
    interview_scores: list                # Per-candidate interview score dicts

    # ── Evaluation & Ranking (Node 6) ──────────────────────────────────────
    final_ranking: list                   # Weighted final ranked candidate list

    # ── Bias / Fairness Audit (Node 7) ─────────────────────────────────────
    fairness_report: dict                 # Disparity metrics and audit summary

    # ── Recruiter Decision (Human-in-the-Loop) ─────────────────────────────
    recruiter_decision: str               # "hire" | "no_hire" | "pending"

    # ── Pipeline Metadata ──────────────────────────────────────────────────
    retries: int                          # Retry counter for the current node
    errors: list                          # Accumulated error messages


def initial_state(job_description: str, candidates: list) -> RecruitmentState:
    """Return a freshly initialized pipeline state."""
    return RecruitmentState(
        job_description=job_description,
        jd_structured={},
        jd_embedding=[],
        candidates=candidates,
        parsed_candidates=[],
        scored_candidates=[],
        above_threshold=[],
        below_threshold=[],
        scheduled_interviews=[],
        interview_scores=[],
        final_ranking=[],
        fairness_report={},
        recruiter_decision="pending",
        retries=0,
        errors=[],
    )

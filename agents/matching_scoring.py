"""
Agent 3 – Matching & Scoring
─────────────────────────────
Computes cosine similarity between JD embedding and each candidate
embedding, applies rule-based hard filters, and splits candidates
into above/below threshold buckets. Sends auto-rejection mock email
to below-threshold candidates.
"""

import logging
import os

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from graph.state import RecruitmentState

logger = logging.getLogger(__name__)

MATCH_THRESHOLD = float(os.getenv("MATCH_THRESHOLD", "0.65"))
MIN_EXPERIENCE = int(os.getenv("MIN_EXPERIENCE_YEARS", "2"))


def _cosine_score(jd_emb: list, cand_emb: list) -> float:
    """Returns cosine similarity score in [0, 1]."""
    a = np.array(jd_emb).reshape(1, -1)
    b = np.array(cand_emb).reshape(1, -1)
    return float(cosine_similarity(a, b)[0][0])


def _send_rejection_email(candidate: dict) -> None:
    """Mock rejection notification."""
    name = candidate.get("name", "Candidate")
    email = candidate.get("email", "unknown@example.com")
    logger.info(f"  📧 Rejection email sent to {name} <{email}>")


def matching_scoring_node(state: RecruitmentState) -> dict:
    """
    LangGraph node: Score and filter all parsed candidates.

    Reads : state["jd_embedding"], state["parsed_candidates"]
    Writes: state["scored_candidates"], state["above_threshold"],
            state["below_threshold"]
    """
    logger.info("▶ Matching & Scoring: Computing similarity scores...")
    jd_emb = state.get("jd_embedding", [])
    candidates = state.get("parsed_candidates", [])
    errors = list(state.get("errors", []))

    if not jd_emb:
        errors.append("matching_scoring: JD embedding missing.")
        return {"scored_candidates": [], "above_threshold": [], "below_threshold": [], "errors": errors}

    scored = []
    for cand in candidates:
        try:
            cand_emb = cand.get("embedding", [])
            sim_score = _cosine_score(jd_emb, cand_emb) if cand_emb else 0.0
            exp_ok = cand.get("experience_years", 0) >= MIN_EXPERIENCE

            # Hard filter: must meet minimum experience
            adjusted_score = sim_score if exp_ok else sim_score * 0.5

            scored.append(
                {
                    **cand,
                    "similarity_score": round(sim_score, 4),
                    "adjusted_score": round(adjusted_score, 4),
                    "meets_experience": exp_ok,
                }
            )
        except Exception as exc:
            logger.error(f"  ✘ Scoring error for {cand.get('id')}: {exc}")
            errors.append(f"matching_scoring[{cand.get('id')}]: {exc}")

    above = [c for c in scored if c["adjusted_score"] >= MATCH_THRESHOLD]
    below = [c for c in scored if c["adjusted_score"] < MATCH_THRESHOLD]

    # Auto-notify rejected candidates
    for cand in below:
        _send_rejection_email(cand)

    logger.info(f"  ✔ Above threshold: {len(above)} | Below threshold: {len(below)}")
    return {
        "scored_candidates": scored,
        "above_threshold": above,
        "below_threshold": below,
        "errors": errors,
    }

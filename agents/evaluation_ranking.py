"""
Agent 6 – Evaluation & Ranking
────────────────────────────────
Aggregates the matching/similarity score and the AI interview score
into a single weighted final score, then produces a ranked shortlist.

Weights (configurable via env):
  MATCH_SCORE_WEIGHT    (default 0.4)
  INTERVIEW_SCORE_WEIGHT (default 0.6)
"""
import os
import logging
from graph.state import RecruitmentState

logger = logging.getLogger(__name__)

MATCH_W = float(os.getenv("MATCH_SCORE_WEIGHT", "0.4"))
INTERVIEW_W = float(os.getenv("INTERVIEW_SCORE_WEIGHT", "0.6"))


def evaluation_ranking_node(state: RecruitmentState) -> dict:
    """
    LangGraph node: Compute final weighted scores and rank candidates.

    Reads : state["above_threshold"], state["interview_scores"]
    Writes: state["final_ranking"]
    """
    logger.info("▶ Evaluation & Ranking: Aggregating scores...")

    above = state.get("above_threshold", [])
    interview_map = {
        s["candidate_id"]: s
        for s in state.get("interview_scores", [])
    }
    errors = list(state.get("errors", []))
    ranked = []

    for cand in above:
        cid = cand.get("id", "unknown")
        match_score = cand.get("adjusted_score", 0.0)                    # 0–1
        interview_data = interview_map.get(cid, {})
        raw_interview = interview_data.get("overall_interview_score", 0)  # 0–10
        interview_score = raw_interview / 10.0                            # Normalize to 0–1

        final_score = round(MATCH_W * match_score + INTERVIEW_W * interview_score, 4)

        ranked.append({
            "id": cid,
            "name": cand.get("name", cid),
            "email": cand.get("email", ""),
            "match_score": round(match_score, 4),
            "interview_score": round(interview_score, 4),
            "final_score": final_score,
            "interview_summary": interview_data.get("summary", "N/A"),
            "skills": cand.get("skills", []),
            "experience_years": cand.get("experience_years", 0),
        })

    # Sort descending by final score
    ranked.sort(key=lambda x: x["final_score"], reverse=True)

    # Add rank position
    for i, r in enumerate(ranked):
        r["rank"] = i + 1

    logger.info(f"  ✔ Final ranking computed for {len(ranked)} candidates.")
    if ranked:
        logger.info(f"  🏆 Top candidate: {ranked[0]['name']} (score: {ranked[0]['final_score']})")

    return {"final_ranking": ranked, "errors": errors}

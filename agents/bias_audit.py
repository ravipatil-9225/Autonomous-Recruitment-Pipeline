"""
Agent 7 – Bias / Fairness Audit
────────────────────────────────
Statistically analyzes the final ranking for potential bias signals.
Checks score distribution and generates an explainability report.

In production, this would analyze demographic attributes if ethically
collected and consented. Here we perform a statistical distribution
analysis as a fairness proxy.
"""

import logging
import statistics

from graph.state import RecruitmentState

logger = logging.getLogger(__name__)


def _compute_distribution(scores: list) -> dict:
    if not scores:
        return {}
    return {
        "count": len(scores),
        "mean": round(statistics.mean(scores), 4),
        "median": round(statistics.median(scores), 4),
        "stdev": round(statistics.stdev(scores), 4) if len(scores) > 1 else 0.0,
        "min": round(min(scores), 4),
        "max": round(max(scores), 4),
    }


def _gini_coefficient(scores: list) -> float:
    """Gini coefficient as inequality metric (0=equal, 1=maximal inequality)."""
    if len(scores) < 2:
        return 0.0
    sorted_s = sorted(scores)
    n = len(sorted_s)
    cumulative = sum((i + 1) * v for i, v in enumerate(sorted_s))
    return round((2 * cumulative) / (n * sum(sorted_s)) - (n + 1) / n, 4)


def bias_audit_node(state: RecruitmentState) -> dict:
    """
    LangGraph node: Perform fairness audit on the final ranking.

    Reads : state["final_ranking"]
    Writes: state["fairness_report"]
    """
    logger.info("▶ Bias/Fairness Audit: Analyzing ranking for fairness...")
    ranking = state.get("final_ranking", [])
    errors = list(state.get("errors", []))

    if not ranking:
        report = {"status": "skipped", "reason": "No candidates in final ranking."}
        return {"fairness_report": report, "errors": errors}

    final_scores = [c["final_score"] for c in ranking]
    match_scores = [c["match_score"] for c in ranking]
    interview_scores = [c["interview_score"] for c in ranking]

    # Score gap analysis (top vs bottom)
    score_gap = round(final_scores[0] - final_scores[-1], 4) if len(final_scores) > 1 else 0.0
    gini = _gini_coefficient(final_scores)

    # Bias flag thresholds
    flags = []
    if score_gap > 0.5:
        flags.append("⚠️ Large score gap between top and bottom candidates (>0.5). Review criteria.")
    if gini > 0.3:
        flags.append("⚠️ High score inequality (Gini > 0.3). Possible concentrated preference.")

    report = {
        "status": "completed",
        "candidates_audited": len(ranking),
        "final_score_distribution": _compute_distribution(final_scores),
        "match_score_distribution": _compute_distribution(match_scores),
        "interview_score_distribution": _compute_distribution(interview_scores),
        "score_gap_top_to_bottom": score_gap,
        "gini_coefficient": gini,
        "bias_flags": flags if flags else ["✅ No significant bias signals detected."],
        "top_candidates": [
            {"rank": c["rank"], "name": c["name"], "final_score": c["final_score"]} for c in ranking[:3]
        ],
        "recommendation": (
            "Proceed with confidence." if not flags else "Manual review recommended before final decision."
        ),
    }

    logger.info(f"  ✔ Fairness Audit complete. Flags: {len(flags)}")
    return {"fairness_report": report, "errors": errors}

"""
Orchestrator – LangGraph Recruitment Pipeline
══════════════════════════════════════════════
Assembles the StateGraph that wires all 7 agent nodes with:
  • Conditional routing after Matching & Scoring
  • Human-in-the-loop (HITL) interrupt at recruiter review
  • SqliteSaver checkpointing for state persistence across HITL pauses
  • MLflow logging after recruiter decision

Graph flow:
  START
    → jd_analyzer
    → resume_parser
    → matching_scoring
    → [route_after_scoring]
        ↳ no candidates above threshold → END
        ↳ candidates exist → interview_scheduler
            → interview_bot
            → evaluation_ranking
            → bias_audit
            → recruiter_review  ← ⏸ HITL PAUSE
            → log_decision
            → END
"""
import logging
from langgraph.graph import StateGraph, END

from graph.state import RecruitmentState
from graph.checkpoints import get_checkpointer
from agents.jd_analyzer import jd_analyzer_node
from agents.resume_parser import resume_parser_node
from agents.matching_scoring import matching_scoring_node
from agents.interview_scheduler import interview_scheduler_node
from agents.interview_bot import interview_bot_node
from agents.evaluation_ranking import evaluation_ranking_node
from agents.bias_audit import bias_audit_node
from tools.mlflow_tracker import log_recruiter_decision

logger = logging.getLogger(__name__)


# ── Conditional Routing ────────────────────────────────────────────────────────

def route_after_scoring(state: RecruitmentState) -> str:
    """
    After Matching & Scoring:
    - If any candidates are above threshold → continue to interview scheduling
    - Otherwise → end the pipeline early
    """
    above = state.get("above_threshold", [])
    if above:
        logger.info(f"  ↳ Routing: {len(above)} candidates proceed to interview scheduling.")
        return "continue"
    else:
        logger.info("  ↳ Routing: No candidates above threshold. Pipeline ending early.")
        return "end"


# ── HITL Node: Recruiter Review ────────────────────────────────────────────────

def recruiter_review_node(state: RecruitmentState) -> dict:
    """
    Human-in-the-loop pause node.
    The graph will interrupt BEFORE this node, waiting for recruiter input.
    When resumed, the state already contains recruiter_decision from the caller.
    """
    decision = state.get("recruiter_decision", "pending")
    logger.info(f"▶ Recruiter Review: Decision received → '{decision}'")
    return {"recruiter_decision": decision}


# ── Post-Decision: MLflow Log ──────────────────────────────────────────────────

def log_decision_node(state: RecruitmentState) -> dict:
    """Logs recruiter decision and pipeline artifacts to MLflow."""
    logger.info("▶ MLflow Tracker: Logging decision for retraining pipeline...")
    log_recruiter_decision(dict(state))
    return {}


# ── Graph Builder ──────────────────────────────────────────────────────────────

def build_graph(use_checkpointer: bool = True):
    """
    Builds and compiles the LangGraph StateGraph for the recruitment pipeline.

    Args:
        use_checkpointer: If True, attaches SqliteSaver for HITL persistence.

    Returns:
        Compiled LangGraph app ready to invoke/stream.
    """
    graph = StateGraph(RecruitmentState)

    # ── Register all nodes ──
    graph.add_node("jd_analyzer",          jd_analyzer_node)
    graph.add_node("resume_parser",        resume_parser_node)
    graph.add_node("matching_scoring",     matching_scoring_node)
    graph.add_node("interview_scheduler",  interview_scheduler_node)
    graph.add_node("interview_bot",        interview_bot_node)
    graph.add_node("evaluation_ranking",   evaluation_ranking_node)
    graph.add_node("bias_audit",           bias_audit_node)
    graph.add_node("recruiter_review",     recruiter_review_node)
    graph.add_node("log_decision",         log_decision_node)

    # ── Define edges ──
    graph.set_entry_point("jd_analyzer")
    graph.add_edge("jd_analyzer",         "resume_parser")
    graph.add_edge("resume_parser",       "matching_scoring")

    # Conditional: route after scoring
    graph.add_conditional_edges(
        "matching_scoring",
        route_after_scoring,
        {
            "continue": "interview_scheduler",
            "end":      END,
        },
    )

    graph.add_edge("interview_scheduler", "interview_bot")
    graph.add_edge("interview_bot",       "evaluation_ranking")
    graph.add_edge("evaluation_ranking",  "bias_audit")
    graph.add_edge("bias_audit",          "recruiter_review")
    graph.add_edge("recruiter_review",    "log_decision")
    graph.add_edge("log_decision",        END)

    # ── Compile with optional HITL checkpointer ──
    if use_checkpointer:
        checkpointer = get_checkpointer()
        app = graph.compile(
            checkpointer=checkpointer,
            interrupt_before=["recruiter_review"],  # ⏸ Pause before HITL node
        )
        logger.info("✔ Graph compiled with SqliteSaver checkpointer (HITL enabled).")
    else:
        app = graph.compile()
        logger.info("✔ Graph compiled without checkpointer (dry-run mode).")

    return app

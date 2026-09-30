"""
Main Entry Point – AI Recruitment Pipeline
══════════════════════════════════════════
Usage:
  # Full pipeline (interactive HITL):
  python main.py

  # Dry-run with mock data (no HITL, no checkpointing):
  python main.py --dry-run
"""

import argparse
import io
import logging
import sys
import uuid

# ── Fix Windows console encoding (cp1252 can't render emoji/box-drawing chars) ──
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

from graph.orchestrator import build_graph
from graph.state import initial_state

# ── Mock Data ──────────────────────────────────────────────────────────────────

MOCK_JD = """
Senior Python Backend Engineer

We are looking for an experienced Python engineer to join our data platform team.

Requirements:
- 4+ years of Python backend development
- Strong knowledge of FastAPI or Django REST Framework
- Experience with PostgreSQL, Redis, and Celery
- Hands-on experience with Docker and Kubernetes
- Familiarity with LangChain, LLMs, or AI/ML pipelines is a strong plus
- Experience with CI/CD pipelines (GitHub Actions preferred)
- BSc or higher in Computer Science or related field

Responsibilities:
- Design and maintain scalable APIs
- Build data pipelines for ML feature engineering
- Collaborate with AI/ML teams on model deployment
"""

MOCK_CANDIDATES = [
    {
        "id": "C001",
        "resume_text": """
        Alice Johnson | alice@example.com | +1-555-0101
        Senior Software Engineer with 6 years of Python experience.
        Skills: Python, FastAPI, PostgreSQL, Redis, Docker, Kubernetes, LangChain, OpenAI
        Education: BSc Computer Science, MIT
        Previous roles: Backend Lead at TechCorp, SWE at StartupAI
        Built ML inference APIs serving 10M requests/day.
        """,
    },
    {
        "id": "C002",
        "resume_text": """
        Bob Martinez | bob@example.com | +1-555-0202
        Python Developer, 2 years experience.
        Skills: Python, Flask, MySQL, basic Docker
        Education: BSc Information Systems
        Previous roles: Junior Developer at WebAgency
        Built simple CRUD REST APIs for e-commerce clients.
        """,
    },
    {
        "id": "C003",
        "resume_text": """
        Carol Chen | carol@example.com | +1-555-0303
        5 years backend & ML pipeline engineering.
        Skills: Python, Django, FastAPI, PostgreSQL, Celery, Redis, Kubernetes, MLflow, LangChain
        Education: MSc Computer Science, Stanford
        Previous roles: ML Platform Engineer at DataCo, Backend Engineer at FinTech Inc.
        Designed end-to-end ML deployment pipelines on GCP.
        """,
    },
    {
        "id": "C004",
        "resume_text": """
        David Kim | david@example.com | +1-555-0404
        1 year Junior developer, mostly JavaScript/Node.js.
        Skills: Node.js, React, basic Python scripting
        Education: Bootcamp graduate
        No prior backend Python or cloud experience.
        """,
    },
]


# ── Pipeline Runner ────────────────────────────────────────────────────────────


def run_pipeline(dry_run: bool = False) -> None:
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    logger.info("═" * 60)
    logger.info("🚀 AI Recruitment Pipeline Starting")
    logger.info(f"   Thread ID : {thread_id}")
    logger.info(f"   Mode      : {'DRY-RUN' if dry_run else 'FULL (HITL enabled)'}")
    logger.info("═" * 60)

    app = build_graph(use_checkpointer=not dry_run)
    state = initial_state(job_description=MOCK_JD, candidates=MOCK_CANDIDATES)

    if dry_run:
        # ── DRY-RUN: inject a fake recruiter decision, run without HITL ──
        state["recruiter_decision"] = "hire"
        final_state = app.invoke(state, config=config)
        _print_summary(final_state)
        return

    # ── PHASE 1: Run until HITL interrupt ──
    logger.info("\n▶ Phase 1: Running pipeline until recruiter review...\n")
    for _ in app.stream(state, config=config, stream_mode="values"):
        pass  # Events are logged within each node

    # ── HITL: Get recruiter input ──
    print("\n" + "─" * 60)
    print("⏸  PIPELINE PAUSED — Recruiter Review Required")
    print("─" * 60)

    # Show the current state snapshot
    snapshot = app.get_state(config)
    current = snapshot.values
    ranking = current.get("final_ranking", [])
    fairness = current.get("fairness_report", {})

    print(f"\n📋 Final Ranking ({len(ranking)} candidates):")
    for r in ranking:
        print(f"  #{r['rank']} {r['name']:<20} Score: {r['final_score']:.4f}")

    print("\n🔍 Fairness Flags:")
    for flag in fairness.get("bias_flags", []):
        print(f"  {flag}")

    print(f"\n📄 Fairness Recommendation: {fairness.get('recommendation', 'N/A')}")
    print()

    while True:
        decision = input("Enter your decision [hire / no_hire]: ").strip().lower()
        if decision in ("hire", "no_hire"):
            break
        print("  ⚠️  Please enter 'hire' or 'no_hire'.")

    # ── PHASE 2: Resume after recruiter input ──
    logger.info(f"\n▶ Phase 2: Resuming with decision → '{decision}'...\n")
    app.update_state(config, {"recruiter_decision": decision})
    for _ in app.stream(None, config=config, stream_mode="values"):
        pass

    final_snapshot = app.get_state(config)
    _print_summary(final_snapshot.values)


def _print_summary(state: dict) -> None:
    print("\n" + "═" * 60)
    print("✅ PIPELINE COMPLETE")
    print("═" * 60)
    print(f"  Decision        : {state.get('recruiter_decision', 'N/A').upper()}")
    ranking = state.get("final_ranking", [])
    print(f"  Candidates Ranked: {len(ranking)}")
    if ranking:
        top = ranking[0]
        print(f"  Top Candidate   : {top['name']} (score: {top['final_score']:.4f})")
    errors = state.get("errors", [])
    if errors:
        print(f"\n  ⚠️  Pipeline Errors ({len(errors)}):")
        for e in errors:
            print(f"    • {e}")
    print("\n  📊 Full State Keys:")
    for k, v in state.items():
        if isinstance(v, list):
            print(f"    {k}: [{len(v)} items]")
        elif isinstance(v, dict):
            print(f"    {k}: {{...}}")
        else:
            print(f"    {k}: {v}")
    print("═" * 60)


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Recruitment Pipeline (LangGraph)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run with mock data and simulated recruiter decision (no HITL pause).",
    )
    args = parser.parse_args()
    run_pipeline(dry_run=args.dry_run)

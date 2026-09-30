"""
MLflow Tracking Integration
────────────────────────────
Logs recruiter decisions and pipeline metadata to MLflow for
model retraining tracking. Tracked via MLflow experiment runs.
"""
import os
import logging
import json
from datetime import datetime

logger = logging.getLogger(__name__)

MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db")
EXPERIMENT_NAME = "recruitment_pipeline"


def log_recruiter_decision(state: dict) -> None:
    """
    Logs the final recruiter decision and pipeline metrics to MLflow.

    This enables the retraining feedback loop: decisions feed back
    as labels to improve the matching and scoring models over time.
    """
    try:
        import mlflow  # Lazy import – optional dependency

        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        mlflow.set_experiment(EXPERIMENT_NAME)

        with mlflow.start_run(run_name=f"decision_{datetime.now().strftime('%Y%m%d_%H%M%S')}"):
            decision = state.get("recruiter_decision", "pending")
            ranking = state.get("final_ranking", [])
            fairness = state.get("fairness_report", {})

            # Log parameters
            mlflow.log_param("recruiter_decision", decision)
            mlflow.log_param("total_candidates", len(state.get("candidates", [])))
            mlflow.log_param("shortlisted_candidates", len(state.get("above_threshold", [])))
            mlflow.log_param("match_threshold", os.getenv("MATCH_THRESHOLD", "0.65"))

            # Log metrics
            if ranking:
                mlflow.log_metric("top_candidate_score", ranking[0]["final_score"])
                mlflow.log_metric("avg_final_score",
                                  sum(c["final_score"] for c in ranking) / len(ranking))
            if fairness:
                gini = fairness.get("gini_coefficient", 0)
                mlflow.log_metric("gini_coefficient", gini)

            # Log artifacts
            mlflow.log_text(json.dumps(ranking, indent=2), "final_ranking.json")
            mlflow.log_text(json.dumps(fairness, indent=2), "fairness_report.json")

            logger.info(f"  ✔ MLflow run logged: decision={decision}")

    except ImportError:
        logger.warning("  ⚠️ MLflow not installed. Skipping tracking.")
    except Exception as exc:
        logger.error(f"  ✘ MLflow logging failed: {exc}")

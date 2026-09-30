"""
LangGraph Checkpoint Configuration
────────────────────────────────────
Provides a checkpointer for human-in-the-loop (HITL) support.

Default: MemorySaver (always available, state lives in-process).
Optional: SqliteSaver for persistent cross-process state
          (install langgraph-checkpoint-sqlite and set USE_SQLITE_CHECKPOINT=true).
"""
import os
import logging

logger = logging.getLogger(__name__)

CHECKPOINT_DB_PATH = os.getenv("CHECKPOINT_DB_PATH", "./checkpoints.db")
USE_SQLITE = os.getenv("USE_SQLITE_CHECKPOINT", "false").lower() == "true"


def get_checkpointer():
    """
    Returns the configured checkpointer.

    - MemorySaver (default): in-memory, no extra install required.
    - SqliteSaver (opt-in):  set USE_SQLITE_CHECKPOINT=true in .env.
    """
    if USE_SQLITE:
        try:
            from langgraph.checkpoint.sqlite import SqliteSaver
            logger.info(f"  📁 Using SqliteSaver: {CHECKPOINT_DB_PATH}")
            return SqliteSaver.from_conn_string(CHECKPOINT_DB_PATH)
        except ImportError:
            logger.warning("  ⚠️  langgraph-checkpoint-sqlite not installed. Falling back to MemorySaver.")

    from langgraph.checkpoint.memory import MemorySaver
    logger.info("  🧠 Using MemorySaver (in-memory checkpointer).")
    return MemorySaver()

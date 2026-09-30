"""
Agent 1 – JD Analyzer
─────────────────────
Extracts structured requirements from raw job description text
and generates a vector embedding of the JD using Gemini.
"""
import json
import os
import logging
from tenacity import retry, stop_after_attempt, wait_exponential

from google import genai
from google.genai import types
from sentence_transformers import SentenceTransformer

from graph.state import RecruitmentState

logger = logging.getLogger(__name__)

# ── Model setup ────────────────────────────────────────────────────────────────
_client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
_MODEL = "gemini-2.5-flash"
_embedder = SentenceTransformer("all-MiniLM-L6-v2")

_SYSTEM_PROMPT = """You are an expert HR analyst. Given the job description below, 
extract the following as valid JSON with no markdown fences:
{
  "role_title": "...",
  "required_skills": ["skill1", "skill2"],
  "preferred_skills": ["skill3"],
  "min_experience_years": <integer>,
  "education_required": "...",
  "employment_type": "...",
  "key_responsibilities": ["..."]
}
Return ONLY the JSON object."""


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _call_gemini(jd_text: str) -> dict:
    response = _client.models.generate_content(
        model=_MODEL,
        contents=f"{_SYSTEM_PROMPT}\n\nJob Description:\n{jd_text}",
    )
    raw = response.text.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:-1])
    return json.loads(raw)


def jd_analyzer_node(state: RecruitmentState) -> dict:
    """
    LangGraph node: Analyze the job description.

    Reads : state["job_description"]
    Writes: state["jd_structured"], state["jd_embedding"]
    """
    logger.info("▶ JD Analyzer: Extracting structured requirements...")
    try:
        jd_text = state["job_description"]

        # Step 1 – LLM extraction
        jd_structured = _call_gemini(jd_text)
        logger.info(f"  ✔ Extracted role: {jd_structured.get('role_title')}")

        # Step 2 – Embedding
        embedding = _embedder.encode(jd_text).tolist()
        logger.info(f"  ✔ JD embedding size: {len(embedding)}")

        return {
            "jd_structured": jd_structured,
            "jd_embedding": embedding,
        }
    except Exception as exc:
        logger.error(f"  ✘ JD Analyzer failed: {exc}")
        errors = list(state.get("errors", []))
        errors.append(f"jd_analyzer: {exc}")
        return {"jd_structured": {}, "jd_embedding": [], "errors": errors}

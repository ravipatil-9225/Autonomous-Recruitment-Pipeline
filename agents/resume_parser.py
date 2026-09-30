"""
Agent 2 – Resume Parser
────────────────────────
Bulk-parses candidate resumes (plain text / PDF) using Gemini
and extracts structured candidate profiles.
"""

import json
import logging
import os

from google import genai
from sentence_transformers import SentenceTransformer
from tenacity import retry, stop_after_attempt, wait_exponential

from graph.state import RecruitmentState

logger = logging.getLogger(__name__)

_client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
_MODEL = "gemini-2.5-flash"
_embedder = SentenceTransformer("all-MiniLM-L6-v2")

_PARSE_PROMPT = """You are an expert resume parser. Given the resume text below,
extract the following as valid JSON with no markdown fences:
{
  "name": "...",
  "email": "...",
  "phone": "...",
  "skills": ["skill1", "skill2"],
  "experience_years": <integer>,
  "education": "...",
  "previous_roles": ["role1", "role2"],
  "summary": "..."
}
Return ONLY the JSON object."""


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _parse_single(resume_text: str) -> dict:
    response = _client.models.generate_content(
        model=_MODEL,
        contents=f"{_PARSE_PROMPT}\n\nResume:\n{resume_text}",
    )
    raw = response.text.strip()
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:-1])
    return json.loads(raw)


def resume_parser_node(state: RecruitmentState) -> dict:
    """
    LangGraph node: Parse all candidate resumes.

    Reads : state["candidates"]  (list of {"id": ..., "resume_text": ...})
    Writes: state["parsed_candidates"]
    """
    logger.info("▶ Resume Parser: Parsing candidate resumes...")
    raw_candidates = state.get("candidates", [])
    parsed = []
    errors = list(state.get("errors", []))

    for candidate in raw_candidates:
        cid = candidate.get("id", "unknown")
        resume_text = candidate.get("resume_text", "")
        try:
            profile = _parse_single(resume_text)
            profile["id"] = cid
            # Generate candidate embedding from their full summary + skills
            embed_text = f"{profile.get('summary', '')} {' '.join(profile.get('skills', []))}"
            profile["embedding"] = _embedder.encode(embed_text).tolist()
            parsed.append(profile)
            logger.info(f"  ✔ Parsed: {profile.get('name', cid)}")
        except Exception as exc:
            logger.error(f"  ✘ Failed to parse candidate {cid}: {exc}")
            errors.append(f"resume_parser[{cid}]: {exc}")

    logger.info(f"  ✔ Total parsed: {len(parsed)}/{len(raw_candidates)}")
    return {"parsed_candidates": parsed, "errors": errors}

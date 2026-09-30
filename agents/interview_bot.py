"""
Agent 5 – AI Interview Bot
───────────────────────────
Conducts a structured first-round screening Q&A for each scheduled
candidate using Gemini and scores their responses on:
  • Technical depth (0–10)
  • Communication clarity (0–10)
  • Relevance to JD (0–10)
"""

import json
import logging
import os
import time

from google import genai
from tenacity import retry, stop_after_attempt, wait_exponential

from graph.state import RecruitmentState

logger = logging.getLogger(__name__)

_client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
_MODEL = "gemini-2.5-flash"

_QUESTION_PROMPT = """You are a technical interviewer. Given this job role and candidate profile,
generate 3 concise screening interview questions. Return as JSON array:
["question 1", "question 2", "question 3"]
No markdown fences. Role: {role}. Candidate skills: {skills}."""

_SCORE_PROMPT = """You are a hiring expert. Score these interview answers out of 10 each.
Return ONLY valid JSON (no markdown):
{{
  "technical_depth": <0-10>,
  "communication_clarity": <0-10>,
  "relevance_to_jd": <0-10>,
  "overall_interview_score": <0-10>,
  "summary": "..."
}}

Job Role: {role}
Questions & Answers:
{qa_pairs}"""


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, min=4, max=30))
def _generate_questions(role: str, skills: list) -> list:
    prompt = _QUESTION_PROMPT.format(role=role, skills=", ".join(skills))
    response = _client.models.generate_content(model=_MODEL, contents=prompt)
    raw = response.text.strip()
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:-1])
    return json.loads(raw)


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, min=4, max=30))
def _score_answers(role: str, qa_pairs: str) -> dict:
    prompt = _SCORE_PROMPT.format(role=role, qa_pairs=qa_pairs)
    response = _client.models.generate_content(model=_MODEL, contents=prompt)
    raw = response.text.strip()
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:-1])
    return json.loads(raw)


def _simulate_candidate_answers(questions: list, candidate: dict) -> list:
    """
    In a real system this would be a multi-turn chat session with the candidate.
    Here we ask Gemini to simulate plausible candidate responses for demo/testing.
    """
    answers = []
    for q in questions:
        prompt = (
            f"You are a job candidate with these skills: {candidate.get('skills', [])} "
            f"and {candidate.get('experience_years', 0)} years of experience. "
            f"Answer this interview question in 2–3 sentences:\n{q}"
        )
        try:
            time.sleep(2)  # avoid 429 rate limit on free tier
            resp = _client.models.generate_content(model=_MODEL, contents=prompt)
            answers.append(resp.text.strip())
        except Exception:
            answers.append("I am unable to answer at this time.")
    return answers


def interview_bot_node(state: RecruitmentState) -> dict:
    """
    LangGraph node: Conduct structured AI interview for each scheduled candidate.

    Reads : state["scheduled_interviews"], state["jd_structured"]
    Writes: state["interview_scores"]
    """
    logger.info("▶ AI Interview Bot: Conducting screening interviews...")
    candidates = state.get("scheduled_interviews", [])
    jd = state.get("jd_structured", {})
    role = jd.get("role_title", "the role")
    errors = list(state.get("errors", []))
    all_scores = []

    for cand in candidates:
        cid = cand.get("id", "unknown")
        name = cand.get("name", cid)
        skills = cand.get("skills", [])
        try:
            questions = _generate_questions(role, skills)
            answers = _simulate_candidate_answers(questions, cand)

            qa_pairs = "\n".join(
                [f"Q{i+1}: {q}\nA{i+1}: {a}" for i, (q, a) in enumerate(zip(questions, answers, strict=False))]
            )
            scores = _score_answers(role, qa_pairs)

            scores["candidate_id"] = cid
            scores["candidate_name"] = name
            scores["questions"] = questions
            scores["answers"] = answers
            all_scores.append(scores)
            logger.info(f"  ✔ Interview scored for {name}: {scores.get('overall_interview_score')}/10")
        except Exception as exc:
            logger.error(f"  ✘ Interview failed for {name}: {exc}")
            errors.append(f"interview_bot[{cid}]: {exc}")

    return {"interview_scores": all_scores, "errors": errors}

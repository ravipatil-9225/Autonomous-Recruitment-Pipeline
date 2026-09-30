"""
Resume Parsing Pipeline  (§11.2 — rule-based first pass)
──────────────────────────────────────────────────────────
Two-stage extraction:
  Stage 1 — Rule-based (spaCy NER + regex + keyword matching)
             Always runs, zero LLM cost.
  Stage 2 — LLM enrichment (calls Phase-1 Gemini agent if available)
             Optional; activated by passing enrich=True.

Supports PDF (via PyMuPDF / pdfplumber fallback) and DOCX.
"""

import io
import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)

# ── Regex patterns ────────────────────────────────────────────────────────────
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
_PHONE_RE = re.compile(r"(\+?1?\s?)?(\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4})")
_DATE_RANGE_RE = re.compile(
    r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4})"
    r"\s*(?:–|-|to)\s*"
    r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}|Present|Current|Now)",
    re.IGNORECASE,
)

# Common tech skills vocabulary (extensible)
_SKILL_VOCAB: set[str] = {
    "python",
    "java",
    "javascript",
    "typescript",
    "go",
    "rust",
    "c++",
    "c#",
    "ruby",
    "fastapi",
    "django",
    "flask",
    "spring",
    "express",
    "react",
    "vue",
    "angular",
    "postgresql",
    "mysql",
    "mongodb",
    "redis",
    "elasticsearch",
    "cassandra",
    "docker",
    "kubernetes",
    "terraform",
    "ansible",
    "aws",
    "gcp",
    "azure",
    "celery",
    "kafka",
    "rabbitmq",
    "airflow",
    "spark",
    "pandas",
    "numpy",
    "scikit-learn",
    "tensorflow",
    "pytorch",
    "langchain",
    "langgraph",
    "mlflow",
    "dvc",
    "git",
    "github",
    "gitlab",
    "jenkins",
    "github actions",
    "rest",
    "graphql",
    "grpc",
    "websocket",
    "microservices",
    "ci/cd",
    "nlp",
    "llm",
    "openai",
    "gemini",
    "hugging face",
    "spacy",
    "sql",
    "nosql",
    "vector database",
    "chroma",
    "pinecone",
    "weaviate",
}

_EDUCATION_KEYWORDS = {
    "bsc",
    "b.sc",
    "bachelor",
    "b.e",
    "b.tech",
    "msc",
    "m.sc",
    "master",
    "m.e",
    "m.tech",
    "mba",
    "phd",
    "ph.d",
    "doctorate",
    "bootcamp",
    "certification",
    "certificate",
}

_SECTION_HEADERS = re.compile(
    r"^(experience|work experience|employment|education|skills|"
    r"certifications?|projects?|summary|objective|profile)[\s:]*$",
    re.IGNORECASE | re.MULTILINE,
)


# ── Text extraction ───────────────────────────────────────────────────────────


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from PDF using PyMuPDF (fitz), fall back to pdfplumber."""
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(stream=file_bytes, filetype="pdf")
        text = "\n".join(page.get_text() for page in doc)
        doc.close()
        if text.strip():
            return text
    except Exception as exc:
        logger.warning(f"PyMuPDF extraction failed ({exc}), trying pdfplumber…")

    try:
        import pdfplumber

        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception as exc:
        logger.error(f"pdfplumber also failed: {exc}")
        return ""


def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extract text from DOCX using python-docx."""
    from docx import Document

    doc = Document(io.BytesIO(file_bytes))
    return "\n".join(para.text for para in doc.paragraphs)


def extract_text(file_bytes: bytes, content_type: str) -> str:
    """Route to correct extractor based on MIME type."""
    if "pdf" in content_type:
        return extract_text_from_pdf(file_bytes)
    elif "wordprocessingml" in content_type or "msword" in content_type:
        return extract_text_from_docx(file_bytes)
    else:
        # Try plain text
        return file_bytes.decode("utf-8", errors="replace")


# ── Rule-based extraction ─────────────────────────────────────────────────────


def _extract_email(text: str) -> str | None:
    m = _EMAIL_RE.search(text)
    return m.group(0) if m else None


def _extract_phone(text: str) -> str | None:
    m = _PHONE_RE.search(text)
    return m.group(0).strip() if m else None


def _extract_name(text: str) -> str:
    """
    Heuristic: first non-empty line that doesn't look like a header or email.
    Falls back to spaCy PERSON entity if available.
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for line in lines[:5]:
        if not _EMAIL_RE.search(line) and not _PHONE_RE.search(line) and len(line.split()) <= 5:
            return line
    # spaCy fallback
    try:
        import spacy

        nlp = spacy.load("en_core_web_sm")
        doc = nlp(text[:2000])
        for ent in doc.ents:
            if ent.label_ == "PERSON":
                return ent.text
    except Exception:
        pass
    return "Unknown"


def _extract_skills(text: str) -> list[str]:
    """Match skill vocabulary words/phrases against lowercased resume text."""
    lower = text.lower()
    found = []
    for skill in sorted(_SKILL_VOCAB):
        # word-boundary aware matching
        pattern = r"\b" + re.escape(skill) + r"\b"
        if re.search(pattern, lower):
            found.append(skill)
    return found


def _estimate_experience_years(text: str) -> int:
    """
    Sum non-overlapping date ranges in the resume text.
    Returns integer years (rounded down).
    """
    total_months = 0
    for m in _DATE_RANGE_RE.finditer(text):
        start_str, end_str = m.group(1), m.group(2)
        try:
            start = datetime.strptime(start_str.strip(), "%B %Y")
        except ValueError:
            try:
                start = datetime.strptime(start_str.strip(), "%b %Y")
            except ValueError:
                continue
        if end_str.strip().lower() in ("present", "current", "now"):
            end = datetime.now()
        else:
            try:
                end = datetime.strptime(end_str.strip(), "%B %Y")
            except ValueError:
                try:
                    end = datetime.strptime(end_str.strip(), "%b %Y")
                except ValueError:
                    continue
        diff_months = (end.year - start.year) * 12 + (end.month - start.month)
        total_months += max(0, diff_months)
    return total_months // 12


def _extract_education(text: str) -> str:
    """Extract the first line mentioning an education keyword."""
    for line in text.splitlines():
        lower_line = line.lower()
        for kw in _EDUCATION_KEYWORDS:
            if kw in lower_line:
                return line.strip()
    return ""


def _extract_previous_roles(text: str) -> list[str]:
    """
    Extract job titles using spaCy if available, else return empty list.
    Phase 3 can enhance this with fine-tuned NER.
    """
    try:
        import spacy

        nlp = spacy.load("en_core_web_sm")
        doc = nlp(text[:5000])
        roles = []
        for ent in doc.ents:
            if ent.label_ in ("ORG", "WORK_OF_ART") and len(ent.text.split()) >= 2:
                roles.append(ent.text)
        return list(dict.fromkeys(roles))[:5]  # deduplicate, keep top 5
    except Exception:
        return []


def parse_resume_rule_based(file_bytes: bytes, content_type: str) -> dict:
    """
    Rule-based first-pass resume parser.

    Returns a structured dict with:
      name, email, phone, skills, experience_years,
      education, previous_roles, raw_text, summary
    """
    raw_text = extract_text(file_bytes, content_type)

    profile = {
        "name": _extract_name(raw_text),
        "email": _extract_email(raw_text),
        "phone": _extract_phone(raw_text),
        "skills": _extract_skills(raw_text),
        "experience_years": _estimate_experience_years(raw_text),
        "education": _extract_education(raw_text),
        "previous_roles": _extract_previous_roles(raw_text),
        "raw_text": raw_text,
        # Summary = first 500 chars of meaningful text (Phase 3: LLM-generated)
        "summary": raw_text.strip()[:500],
        "parse_method": "rule_based",
    }
    logger.info(
        f"Rule-based parse complete: name={profile['name']!r}, "
        f"skills={len(profile['skills'])}, exp={profile['experience_years']}y"
    )
    return profile


class ParsedContactInfo:
    def __init__(self, email: str | None, phone: str | None, name: str):
        self.email = email
        self.phone = phone
        self.name = name


class ParsedResumeResult:
    def __init__(self, data: dict):
        self.data = data
        self.contact_info = ParsedContactInfo(
            email=data.get("email"),
            phone=data.get("phone"),
            name=data.get("name", "Unknown"),
        )
        self.skills = data.get("skills", [])
        self.summary = data.get("summary", "")
        self.total_experience_years = float(data.get("experience_years", 0))
        self.education = data.get("education", "")
        self.previous_roles = data.get("previous_roles", [])
        self.raw_text = data.get("raw_text", "")


class ResumeParsingPipeline:
    """Object-oriented wrapper for the two-stage resume parser."""

    def parse(self, text_or_bytes: str | bytes, content_type: str = "text/plain") -> ParsedResumeResult:
        file_bytes = text_or_bytes.encode("utf-8") if isinstance(text_or_bytes, str) else text_or_bytes
        data = parse_resume_rule_based(file_bytes, content_type)
        return ParsedResumeResult(data)

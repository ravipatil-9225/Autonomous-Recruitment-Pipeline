"""
Celery Task Queue & Resume Parsing Unit Tests (§10.2, §11.2)
──────────────────────────────────────────────────────────────
"""

from backend.app.services.parsing_pipeline import ResumeParsingPipeline


def test_parsing_pipeline_contact_extraction():
    pipeline = ResumeParsingPipeline()
    sample_text = (
        "John Doe\n"
        "Senior Software Engineer\n"
        "Email: john.doe@example.com\n"
        "Phone: (555) 123-4567\n"
        "LinkedIn: linkedin.com/in/johndoe\n\n"
        "Skills:\n"
        "Python, FastAPI, Docker, PostgreSQL, React, Machine Learning\n\n"
        "Experience:\n"
        "Senior Developer at Tech Corp (Jan 2020 - Present)\n"
        "Built backend microservices using Python and FastAPI.\n\n"
        "Education:\n"
        "Bachelor of Science in Computer Science, Stanford University (2016 - 2020)\n"
    )

    parsed = pipeline.parse(sample_text)

    assert parsed.contact_info.email == "john.doe@example.com"
    assert parsed.contact_info.phone is not None
    assert "python" in parsed.skills
    assert "fastapi" in parsed.skills
    assert "docker" in parsed.skills
    assert parsed.summary is not None
    assert parsed.total_experience_years >= 3.0


def test_parsing_pipeline_empty_text():
    pipeline = ResumeParsingPipeline()
    parsed = pipeline.parse("")
    assert parsed.contact_info.email is None
    assert parsed.skills == []
    assert parsed.total_experience_years == 0.0

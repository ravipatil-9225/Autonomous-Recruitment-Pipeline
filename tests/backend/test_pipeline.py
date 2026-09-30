"""
Pipeline API Tests
──────────────────
Tests for §11.3 Pipeline Triggering & HITL Recruiter Decision submission.
"""
import uuid
from unittest.mock import patch, MagicMock
import pytest
from httpx import AsyncClient

from backend.app.models.application import PipelineRun, PipelineStatus


@pytest.mark.asyncio
async def test_trigger_pipeline_no_resumes(async_client: AsyncClient, recruiter_headers):
    headers = {"Authorization": recruiter_headers["Authorization"]}
    job_id = str(uuid.uuid4())

    response = await async_client.post(
        "/api/v1/pipeline/run",
        json={"job_id": job_id, "resume_ids": []},
        headers=headers,
    )
    # 400 Bad Request when no parsed resumes are found
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_trigger_and_get_pipeline_run(async_client: AsyncClient, recruiter_headers):
    headers = {"Authorization": recruiter_headers["Authorization"]}
    job_id = str(uuid.uuid4())
    dummy_resume_id = str(uuid.uuid4())

    mock_task = MagicMock()
    mock_task.id = "celery-pipeline-task-1"

    with patch("backend.app.tasks.pipeline_tasks.run_pipeline_task.delay", return_value=mock_task):
        response = await async_client.post(
            "/api/v1/pipeline/run",
            json={"job_id": job_id, "resume_ids": [dummy_resume_id]},
            headers=headers,
        )

    assert response.status_code == 202
    data = response.json()
    assert data["job_id"] == job_id
    assert data["celery_task_id"] == "celery-pipeline-task-1"
    run_id = data["run_id"]

    # Status check
    status_resp = await async_client.get(f"/api/v1/pipeline/{run_id}", headers=headers)
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["id"] == run_id
    assert status_data["status"] == "queued"
